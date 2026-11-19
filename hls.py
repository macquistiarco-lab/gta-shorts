"""Download only a time window of a Twitch VOD (HLS), through the HTTPS proxy.

ffmpeg cannot reach the CDN here (it ignores the proxy), so the playlist and the
.ts segments are fetched with requests and only joined locally by ffmpeg.

  python hls.py <vod_id> <start_s> <end_s> <out.mp4> [quality]   # quality: 720p60, Audio_Only...
"""
import os, subprocess, sys, tempfile, urllib.parse
from concurrent.futures import ThreadPoolExecutor

import requests


def playlist_url(vod, quality="720p60"):
    r = subprocess.run(["yt-dlp", "-q", "--no-warnings", "-f", quality, "-g",
                        f"https://www.twitch.tv/videos/{vod}"], capture_output=True, text=True, check=True)
    return r.stdout.strip().splitlines()[-1]


def _get(u):
    for attempt in range(4):
        try:
            r = requests.get(u, timeout=60)
            r.raise_for_status()
            return r.content
        except requests.RequestException:
            if attempt == 3:
                raise


def cut(vod, start, end, out, quality="720p60"):
    """Writes out (mp4) covering [start, end]; returns the real start time of the file."""
    url = playlist_url(vod, quality)
    segs, t, dur, init = [], 0.0, None, None
    for ln in requests.get(url, timeout=60).text.splitlines():
        if ln.startswith("#EXT-X-MAP:"):  # fMP4 playlists: init segment comes first
            init = urllib.parse.urljoin(url, ln.split('URI="')[1].split('"')[0])
        elif ln.startswith("#EXTINF:"):
            dur = float(ln[8:].split(",")[0])
        elif ln and not ln.startswith("#") and dur is not None:
            if t + dur > start and t < end:
                segs.append((t, urllib.parse.urljoin(url, ln)))
            t += dur
            dur = None
    if not segs:
        sys.exit(f"no segments for {start}-{end}")
    with tempfile.TemporaryDirectory() as d:
        raw = os.path.join(d, "raw.mp4" if init else "raw.ts")
        with open(raw, "wb") as f, ThreadPoolExecutor(8) as ex:
            if init:
                f.write(_get(init))
            for data in ex.map(_get, [u for _, u in segs]):  # map keeps the order
                f.write(data)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", raw, "-c", "copy",
                        "-movflags", "+faststart", out], check=True)
    return segs[0][0]


if __name__ == "__main__":
    vod, a, b, out = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), sys.argv[4]
    q = sys.argv[5] if len(sys.argv) > 5 else "720p60"
    print(cut(vod, a, b, out, q))
