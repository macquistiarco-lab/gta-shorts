"""Render vertical Shorts (1080x1920) from a stream: facecam on top, gameplay below,
word-by-word captions of what the streamer says.

  python clip.py 01_tiger        # one clip -> out/01_tiger.mp4
  python clip.py --all           # every clip in clips.json

clips.json: {"<name>": {"stream", "start", "end", "hook", "drop": [[a, b], ...], ...}}
data/streams.json: per stream the Drive file id and the layout (cam / game crop boxes,
x, y, w, h in the 1280x720 source). Captions come from data/<stream>.transcript.json;
"drop" removes words in those absolute time ranges (game dialogue, not the streamer).
The source video is downloaded from Drive into src/ the first time.
"""
import json, subprocess, sys, os

HERE = os.path.dirname(os.path.abspath(__file__))
W, H = 1080, 1920
CAM_Y = 230
SPLIT_Y = 770  # split layout: height of the webcam band (40% of 1920, as in the reference Short)
OVERLAY_W = 620  # campaign badge width on screen (split layout)


def source(stream, info, a=None, b=None):
    """Local video for the stream and the time of its first frame in the stream.
    Twitch VODs: only the window [a, b] is downloaded (hls.py). Drive: the whole file."""
    if info.get("twitch_vod"):
        from hls import cut
        a0, b0 = max(0, int(a) - 2), int(b) + 2
        path = os.path.join(HERE, "src", f"{stream}_{a0}_{b0}.mp4")
        meta = path + ".start"
        if not os.path.exists(meta):
            os.makedirs(os.path.dirname(path), exist_ok=True)
            open(meta, "w").write(str(cut(info["twitch_vod"], a0, b0, path, info.get("quality", "720p60"))))
        return path, float(open(meta).read())
    path = os.path.join(HERE, "src", f"{stream}.mp4")
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        url = ("https://drive.usercontent.google.com/download?id="
               f"{info['drive_id']}&export=download&confirm=t")
        print(f"downloading {stream} from Drive...", flush=True)
        subprocess.run(["curl", "-sSLf", "--max-time", "1800", "-o", path + ".part", url], check=True)
        os.rename(path + ".part", path)
    return path, 0.0


# words muted in the audio and replaced by **** in the captions (slurs, not plain swearing)
SLURS = ("nigga", "nigger", "niggas", "retard", "faggot", "fag")


def mute_filter(mutes):
    return "".join(f"volume=enable='between(t,{x:.2f},{y:.2f})':volume=0," for x, y in mutes)


def ts(t):
    h = int(t // 3600); m = int(t % 3600 // 60); s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def ass(words, hook, dur, path, capy, credit=None):
    """hook: title bar at the top (classic layout) or None; credit: small "via <streamer>"
    line under the captions (split layout)."""
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,Inter Display,72,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,7,3,5,50,50,0,1
Style: Hook,Inter Display,64,&H00FFFFFF,&H00FFFFFF,&H00000000,&HC0000000,-1,0,0,0,100,100,0,0,3,16,0,8,50,50,60,1
Style: Credit,Inter Display,38,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,3,1,5,50,50,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    ev = []
    if hook:
        ev.append(f"Dialogue: 1,{ts(0)},{ts(dur)},Hook,,0,0,0,,{hook}")
    if credit:
        ev.append(f"Dialogue: 1,{ts(0)},{ts(dur)},Credit,,0,0,0,,{{\\pos({W//2},{capy + 105})}}{credit}")
    # chunks of up to 3 words and ~19 characters (one line at 72 px), break on long pauses
    chunks, cur = [], []
    for w in words:
        width = sum(len(x["w"]) + 1 for x in cur) + len(w["w"])
        if cur and (len(cur) == 3 or width > 19 or w["s"] - cur[-1]["e"] > 0.6):
            chunks.append(cur); cur = []
        cur.append(w)
    if cur: chunks.append(cur)
    for ci, ch in enumerate(chunks):
        end_chunk = ch[-1]["e"] + 0.25
        if ci + 1 < len(chunks): end_chunk = min(end_chunk, chunks[ci + 1][0]["s"])
        for i, w in enumerate(ch):
            st = w["s"]; en = ch[i + 1]["s"] if i + 1 < len(ch) else end_chunk
            if en <= st: continue
            txt = " ".join(
                ("{\\c&H00E5FF&\\fscx110\\fscy110}" + x["w"].upper() + "{\\r}") if j == i else x["w"].upper()
                for j, x in enumerate(ch))
            ev.append(f"Dialogue: 0,{ts(st)},{ts(en)},Cap,,0,0,0,,{{\\pos({W//2},{capy})}}{txt}")
    open(path, "w").write(head + "\n".join(ev) + "\n")


def render(name, c):
    info = json.load(open(os.path.join(HERE, "data", "streams.json")))[c["stream"]]
    src, src_t0 = source(c["stream"], info, c["start"], c["end"])
    CAM, GAME = c.get("cam", info["cam"]), c.get("game", info["game"])  # layouts change during a stream
    global CAM_H, GAME_Y, GAME_H
    CAM_W = info.get("cam_w", W)  # facecam width on screen (centered)
    GAME_W = W
    CAM_H = round(CAM_W * CAM[3] / CAM[2] / 2) * 2
    GAME_H = round(GAME_W * GAME[3] / GAME[2] / 2) * 2
    GAME_Y = CAM_Y + CAM_H + 12
    a, b = c["start"], c["end"]; dur = b - a
    tr = json.load(open(os.path.join(HERE, "data", f"{c['stream']}.transcript.json")))
    ref_path = os.path.join(HERE, "data", f"{c['stream']}.refined.json")
    for r in (json.load(open(ref_path)) if os.path.exists(ref_path) else []):
        if r["start"] <= a and r["end"] >= b:  # better transcription of this window
            tr = [{"words": r["words"]}]
            break
    drop = c.get("drop", [])
    words, mutes = [], []
    for seg in tr:
        for w in seg["words"]:
            if w["s"] >= a and w["e"] <= b and not any(x <= w["s"] < y for x, y in drop):
                t = w["w"].strip()
                if any(sl in t.lower() for sl in SLURS):  # bleep in the audio, hide in captions
                    mutes.append((max(0, w["s"] - a - 0.05), w["e"] - a + 0.05))
                    t = "****"
                for bad, ok in (("motherfucker", "MOTHERF*CKER"), ("fucking", "F*CKING"), ("fuck", "F*CK"),
                                ("shit", "SH*T"), ("bitch", "B*TCH"), ("dick", "D*CK"), ("ass", "A*S")):
                    if bad in t.lower() and not (bad == "ass" and t.lower().strip(",.!?") != "ass"):
                        t = ok + t[t.lower().find(bad) + len(bad):]
                        break
                if t: words.append({"w": t.replace("{", "").replace("}", ""), "s": w["s"] - a, "e": w["e"] - a})
    os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
    sub = os.path.join(HERE, "out", f"{name}.ass")
    cx, cy, cw, ch = CAM; gx, gy, gw, gh = GAME
    layout = c.get("layout", info.get("layout", "split"))
    if layout == "split":
        # owner's reference layout: webcam full width on top (40%), gameplay filling the rest,
        # no blurred background and no title bar; captions on the gameplay with a small
        # "via <streamer>" credit under them (campaigns want the name on screen)
        overlay = info.get("overlay")  # campaign badge (e.g. Twitch handle), required on screen
        # with a badge the streamer's name is already on screen: no "via" credit
        ass(words, None, dur, sub, SPLIT_Y + 410, credit=None if overlay else f"via {info['streamer']}")
        fc = (f"[0:v]split=2[b][c];"
              f"[b]crop={cw}:{ch}:{cx}:{cy},scale={W}:{SPLIT_Y}:force_original_aspect_ratio=increase:"
              f"flags=lanczos,crop={W}:{SPLIT_Y},unsharp=5:5:0.8[cam];"
              f"[c]crop={gw}:{gh}:{gx}:{gy},scale={W}:{H - SPLIT_Y}:force_original_aspect_ratio=increase:"
              f"flags=lanczos,crop={W}:{H - SPLIT_Y}[game];"
              f"[cam][game]vstack,subtitles={sub}[st];")
        if overlay:  # centred on the seam between webcam and gameplay, visible the whole clip
            fc += (f"[1:v]scale={OVERLAY_W}:-2[ov];"
                   f"[st][ov]overlay=(W-w)/2:{SPLIT_Y}-h/2[v];")
        else:
            fc += "[st]null[v];"
        fc += f"[0:a]{mute_filter(mutes)}loudnorm=I=-14:TP=-1.5:LRA=11[au]"
    else:  # classic: blurred background, centered facecam, title bar, captions under the webcam
        ass(words, c["hook"], dur, sub, GAME_Y + 70)
        fc = (f"[0:v]split=3[a][b][c];"
              f"[a]crop={gw}:{gh}:{gx}:{gy},scale=-2:{H},crop={W}:{H},boxblur=20:2,eq=brightness=-0.25[bg];"
              f"[b]crop={cw}:{ch}:{cx}:{cy},scale={CAM_W}:{CAM_H}:flags=lanczos,unsharp=5:5:0.8[cam];"
              f"[c]crop={gw}:{gh}:{gx}:{gy},scale={GAME_W}:{GAME_H}:flags=lanczos[game];"
              f"[bg][cam]overlay={(W - CAM_W) // 2}:{CAM_Y}[t1];[t1][game]overlay=0:{GAME_Y},subtitles={sub}[v];"
              f"[0:a]{mute_filter(mutes)}loudnorm=I=-14:TP=-1.5:LRA=11[au]")
    out = os.path.join(HERE, "out", f"{name}.mp4")
    extra = ["-i", os.path.join(HERE, info["overlay"])] if layout == "split" and info.get("overlay") else []
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{a - src_t0:.3f}", "-t", str(dur), "-i", src,
                    *extra, "-filter_complex", fc, "-map", "[v]", "-map", "[au]",
                    "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-r", "30",
                    "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", out], check=True)
    print(out, flush=True)
    return out


def main():
    clips = json.load(open(os.path.join(HERE, "clips.json")))
    names = list(clips) if sys.argv[1:] == ["--all"] else sys.argv[1:]
    if not names:
        sys.exit("usage: python clip.py <name> [...] | --all")
    for n in names:
        render(n, clips[n])


if __name__ == "__main__":
    main()
