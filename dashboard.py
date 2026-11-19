"""Build the state document shown on the GTA HUD dashboard (a claude.ai artifact).

    python dashboard.py > /tmp/hud_state.json

Then write it to the dashboard's store with the ArtifactData tool:
`set` on doc `hud/state` with `file_path` = that file. Live events go in
`feed/<id>` documents: {"at": ISO time, "kind": "publish|clip|stream|warn|info", "text": "..."}.
Reads only files in this repo; no network, no credentials.
"""
import datetime as dt
import glob
import json
import os
import re
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))


def load(path, default=None):
    try:
        with open(os.path.join(HERE, path)) as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def clip_seconds(c):
    total = c["end"] - c["start"]
    for a, b in c.get("drop", []):
        total -= b - a
    return round(total, 1)


def transcript_hours(stream):
    segs = load(f"data/{stream}.transcript.json", [])
    return round(segs[-1]["end"] / 3600, 2) if segs else 0


def commits(n=12):
    try:
        out = subprocess.run(["git", "log", f"-{n}", "--format=%h%x09%cI%x09%s"], cwd=HERE,
                             capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return []
    rows = []
    for line in out.splitlines():
        h, at, msg = line.split("\t", 2)
        rows.append({"hash": h, "at": at, "text": msg})
    return rows


def campaign_info():
    rows = []
    for path in sorted(glob.glob(os.path.join(HERE, "campaigns", "*.md"))):
        text = open(path).read()
        title = text.splitlines()[0].lstrip("# ").strip()
        pool = re.search(r"Pool \$([\d,]+)", text)
        mvr = re.search(r"minimum ([\d,]+) total approved views", text)
        tag = re.search(r"use #(\w+)", text)
        rows.append({
            "id": os.path.basename(path)[:-3],
            "title": title,
            "pool": int(pool.group(1).replace(",", "")) if pool else None,
            "mvr": int(mvr.group(1).replace(",", "")) if mvr else None,
            "hashtag": "#" + tag.group(1) if tag else None,
        })
    return rows


def main():
    clips = load("clips.json", {})
    published = load("published.json", {})
    streams = load("data/streams.json", {})
    out_clips = []
    for name, c in clips.items():
        st = streams.get(c["stream"], {})
        p = published.get(name)
        out_clips.append({
            "name": name,
            "stream": c["stream"],
            "streamer": st.get("streamer", "?"),
            "campaign": bool(st.get("campaign")),
            "title": c["title"],
            "seconds": clip_seconds(c),
            "uploaded": bool(p),
            "url": p["url"] if p else None,
            "publish_at": p.get("publish_at") if p else None,
        })
    out_streams = []
    for sid, st in streams.items():
        out_streams.append({
            "id": sid,
            "streamer": st.get("streamer"),
            "title": st.get("title"),
            "source": "Twitch" if st.get("twitch_vod") else "Drive",
            "source_url": st.get("source_url"),
            "campaign": bool(st.get("campaign")),
            "transcript_hours": transcript_hours(sid),
            "clips": sum(1 for c in clips.values() if c["stream"] == sid),
        })
    state = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "slots_rome": ["14:00", "18:00"],
        "clips": out_clips,
        "streams": out_streams,
        "campaigns": campaign_info(),
        "commits": commits(),
    }
    print(json.dumps(state, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
