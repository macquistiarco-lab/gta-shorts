"""Transcribe a stream with word timestamps -> data/<stream>.transcript.json

  python transcribe.py ishowspeed_gta6_day1

Runs on CPU (faster-whisper "small", int8): about 15 minutes for 35 minutes of audio.
The model downloads from huggingface the first time (HF_HUB_DISABLE_XET=1 is set because
the xet host is not on the environment's allowlist).
"""
import json, os, subprocess, sys, wave
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
import numpy as np
from faster_whisper import WhisperModel
from clip import HERE, source

stream = sys.argv[1]
info = json.load(open(os.path.join(HERE, "data", "streams.json")))[stream]
wav = os.path.join(HERE, "src", f"{stream}.wav")
if not os.path.exists(wav):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", source(stream, info), "-vn", "-ac", "1",
                    "-ar", "16000", wav], check=True)
wf = wave.open(wav)
audio = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
m = WhisperModel("small", download_root=os.path.join(HERE, "models"), device="cpu",
                 compute_type="int8", cpu_threads=os.cpu_count())
segs, _ = m.transcribe(audio, language="en", word_timestamps=True, vad_filter=True, beam_size=1)
out = []
for s in segs:
    out.append({"start": s.start, "end": s.end, "text": s.text.strip(),
                "words": [{"w": w.word, "s": w.start, "e": w.end} for w in s.words]})
    print(f"[{s.start:7.1f}] {s.text.strip()}", flush=True)
json.dump(out, open(os.path.join(HERE, "data", f"{stream}.transcript.json"), "w"))
print("DONE")
