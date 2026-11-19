"""Transcribe a stream with word timestamps -> data/<stream>.transcript.json

  python transcribe.py ishowspeed_gta6_day1 [model]   # model: small (default), base.en for long VODs
  python transcribe.py <stream> base.en --resume-from 8400   # live VOD grew: redo from 8400 s on

Works in 30-minute chunks: memory stays low on 9-hour VODs (the whole file at once
was OOM-killed), the JSON is rewritten after every chunk so clips can be picked while it
runs, and a rerun resumes after the last finished chunk.
The model downloads from huggingface the first time (HF_HUB_DISABLE_XET=1 is set because
the xet host is not on the environment's allowlist).
"""
import json, os, subprocess, sys, wave
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
import numpy as np
from faster_whisper import WhisperModel
from clip import HERE, source

CHUNK = 1800  # seconds


def refine(stream, a, b, model="small"):
    """Re-transcribe [a, b] with a better model into data/<stream>.refined.json
    (a separate file, so it never races with a long run rewriting the main transcript).
    clip.py uses refined words for any clip window a refined range covers."""
    wav = os.path.join(HERE, "src", f"{stream}.wav")
    wf = wave.open(wav)
    rate = wf.getframerate()
    wf.setpos(int(a * rate))
    audio = np.frombuffer(wf.readframes(int((b - a) * rate)), dtype=np.int16).astype(np.float32) / 32768.0
    m = WhisperModel(model, download_root=os.path.join(HERE, "models"), device="cpu",
                     compute_type="int8", cpu_threads=os.cpu_count())
    segs, _ = m.transcribe(audio, language="en", word_timestamps=True, vad_filter=True, beam_size=5)
    words = [{"w": w.word, "s": a + w.start, "e": a + w.end} for s in segs for w in s.words]
    path = os.path.join(HERE, "data", f"{stream}.refined.json")
    ref = json.load(open(path)) if os.path.exists(path) else []
    ref = [r for r in ref if not (r["start"] <= a and r["end"] >= b)] + [{"start": a, "end": b, "words": words}]
    json.dump(ref, open(path, "w"))
    print(" ".join(w["w"].strip() for w in words))


if len(sys.argv) > 2 and sys.argv[2] == "--refine":  # transcribe.py <stream> --refine <a> <b>
    refine(sys.argv[1], float(sys.argv[3]), float(sys.argv[4]))
    sys.exit()

stream = sys.argv[1]
model = sys.argv[2] if len(sys.argv) > 2 else "small"
info = json.load(open(os.path.join(HERE, "data", "streams.json")))[stream]
wav = os.path.join(HERE, "src", f"{stream}.wav")
if not os.path.exists(wav):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", source(stream, info)[0], "-vn", "-ac", "1",
                    "-ar", "16000", wav], check=True)
out_path = os.path.join(HERE, "data", f"{stream}.transcript.json")
state_path = out_path + ".progress"
out = json.load(open(out_path)) if os.path.exists(state_path) else []
done_until = float(open(state_path).read()) if os.path.exists(state_path) else 0.0
if "--resume-from" in sys.argv:  # a live VOD grew: keep segments before X, transcribe from X on
    done_until = float(sys.argv[sys.argv.index("--resume-from") + 1])
    out = [s for s in json.load(open(out_path)) if s["start"] < done_until]

m = WhisperModel(model, download_root=os.path.join(HERE, "models"), device="cpu",
                 compute_type="int8", cpu_threads=os.cpu_count())
wf = wave.open(wav)
rate, total = wf.getframerate(), wf.getnframes() / wf.getframerate()
t0 = done_until
while t0 < total:
    wf.setpos(int(t0 * rate))
    n = int(min(CHUNK, total - t0) * rate)
    if n <= 0:  # less than one sample left: done (without this it looped forever)
        break
    audio = np.frombuffer(wf.readframes(n), dtype=np.int16).astype(np.float32) / 32768.0
    segs, _ = m.transcribe(audio, language="en", word_timestamps=True, vad_filter=True, beam_size=1)
    for s in segs:
        out.append({"start": t0 + s.start, "end": t0 + s.end, "text": s.text.strip(),
                    "words": [{"w": w.word, "s": t0 + w.start, "e": t0 + w.end} for w in s.words]})
        print(f"[{t0 + s.start:7.1f}] {s.text.strip()}", flush=True)
    t0 += n / rate
    json.dump(out, open(out_path + ".tmp", "w"))  # write then rename: a kill never leaves half a file
    os.replace(out_path + ".tmp", out_path)
    open(state_path, "w").write(str(t0))
    print(f"CHUNK {t0:.0f}/{total:.0f}", flush=True)
os.remove(state_path)
print("DONE")
