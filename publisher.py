#!/usr/bin/env python3
"""Publish the GTA clips (out/<name>.mp4, made by clip.py) on the GTA YouTube channel.

  python publisher.py --auth                 # once, on a PC: prints the refresh token
  python publisher.py --whoami               # which channel the token belongs to
  python publisher.py 01_tiger --slot auto   # schedule one clip at the next free slot
  python publisher.py --all --slot auto      # every clip not in published.json
  python publisher.py --all --dry-run        # only print title / description / tags

Credentials (environment variables, deliberately NOT the YT_* names of the finance channel):
  GTA_YT_CLIENT_ID, GTA_YT_CLIENT_SECRET, GTA_YT_REFRESH_TOKEN
  GTA_CHANNEL_ID   the GTA channel id (UC...): uploads are refused on any other channel.
Published clips are recorded in published.json (committed), so nothing is uploaded twice.
"""
import argparse
import datetime as dt
import http.server
import json
import os
import sys
import urllib.parse
import webbrowser

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
SCOPE = ("https://www.googleapis.com/auth/youtube.upload "
         "https://www.googleapis.com/auth/youtube.force-ssl")
TOKEN_URL = "https://oauth2.googleapis.com/token"
API = "https://www.googleapis.com/youtube/v3"
UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"
CATEGORY_GAMING = "20"
SLOTS = ["14:00", "18:00"]          # Rome time = 8am and noon US Eastern
SLOT_TZ = "Europe/Rome"
MIN_LEAD = dt.timedelta(minutes=20)
BASE_TAGS = ["shorts", "gta6", "gta", "gaming"]
CTA = "Follow for the best GTA 6 moments every day."
PUBLISHED = os.path.join(HERE, "published.json")


def log(msg):
    print(f"[publisher] {msg}", flush=True)


def env(name, required=True):
    v = os.environ.get(name)
    if not v and required:
        sys.exit(f"missing environment variable {name} (see README)")
    return v


# ---------- metadata ----------

def build_metadata(name, c, stream):
    tags = []
    for t in ["shorts"] + c.get("hashtags", []) + BASE_TAGS:
        t = "".join(ch for ch in t.lstrip("#") if ch.isalnum()).lower()
        if t and t not in tags:
            tags.append(t)
    tags = tags[:12]
    title = c["title"].strip()
    if "#shorts" not in title.lower() and len(title) + 8 <= 100:
        title += " #shorts"
    credit = f"Clip from {stream['streamer']}'s stream \"{stream['title']}\": {stream['source_url']}"
    description = (f"{c['description'].strip()}\n\n{credit}\nAll rights to the original creator.\n\n"
                   f"{CTA}\n\n" + " ".join("#" + t for t in tags))
    return {"title": title[:100], "description": description[:5000], "tags": tags}


# ---------- OAuth ----------

def auth_flow():
    cid, secret = env("GTA_YT_CLIENT_ID"), env("GTA_YT_CLIENT_SECRET")
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({
        "client_id": cid, "redirect_uri": "REDIRECT", "response_type": "code",
        "scope": SCOPE, "access_type": "offline", "prompt": "consent"})
    got = {}

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            if "code" in q or "error" in q:
                got["code"] = (q.get("code") or [None])[0]
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK, you can close this tab.")

        def log_message(self, *a):
            pass

    srv = http.server.HTTPServer(("127.0.0.1", 0), H)
    redirect = f"http://127.0.0.1:{srv.server_address[1]}"
    url = url.replace("REDIRECT", urllib.parse.quote(redirect, safe=""))
    print("Open this link, log in and CHOOSE THE GTA CHANNEL:\n" + url)
    webbrowser.open(url)
    while "code" not in got:
        srv.handle_request()
    if not got["code"]:
        sys.exit("authorization denied")
    r = requests.post(TOKEN_URL, data={
        "code": got["code"], "client_id": cid, "client_secret": secret,
        "redirect_uri": redirect, "grant_type": "authorization_code"}, timeout=30)
    r.raise_for_status()
    tok = r.json()["refresh_token"]
    ch = channel(access(tok))
    print(f"\nChannel: {ch['title']}  id: {ch['id']}")
    print("Add these to the gta-shorts cloud environment (Environment variables):")
    print(f"GTA_YT_REFRESH_TOKEN={tok}\nGTA_CHANNEL_ID={ch['id']}")


def access(refresh=None):
    r = requests.post(TOKEN_URL, data={
        "client_id": env("GTA_YT_CLIENT_ID"), "client_secret": env("GTA_YT_CLIENT_SECRET"),
        "refresh_token": refresh or env("GTA_YT_REFRESH_TOKEN"),
        "grant_type": "refresh_token"}, timeout=30)
    if r.status_code != 200:
        sys.exit(f"token refresh failed: {r.status_code} {r.text}")
    return r.json()["access_token"]


def channel(token):
    r = requests.get(f"{API}/channels", params={"part": "snippet,contentDetails", "mine": "true"},
                     headers={"Authorization": f"Bearer {token}"}, timeout=30)
    r.raise_for_status()
    it = r.json()["items"][0]
    return {"id": it["id"], "title": it["snippet"]["title"],
            "uploads": it["contentDetails"]["relatedPlaylists"]["uploads"]}


def checked_channel(token):
    """Refuse to go on unless the token belongs to GTA_CHANNEL_ID (never the finance channel)."""
    ch = channel(token)
    want = env("GTA_CHANNEL_ID")
    if ch["id"] != want:
        sys.exit(f"STOP: token is for channel '{ch['title']}' ({ch['id']}), not GTA_CHANNEL_ID {want}")
    return ch


# ---------- slots ----------

def _utc(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


def taken_times(token, uploads):
    h = {"Authorization": f"Bearer {token}"}
    r = requests.get(f"{API}/playlistItems", params={
        "part": "contentDetails", "playlistId": uploads, "maxResults": 20}, headers=h, timeout=30)
    if r.status_code == 404:  # brand-new channel: no uploads playlist yet
        return []
    r.raise_for_status()
    ids = [i["contentDetails"]["videoId"] for i in r.json()["items"]]
    if not ids:
        return []
    r = requests.get(f"{API}/videos", params={"part": "status,snippet", "id": ",".join(ids)},
                     headers=h, timeout=30)
    r.raise_for_status()
    out = []
    for v in r.json()["items"]:
        st = v["status"]
        if st.get("publishAt"):
            out.append(_utc(st["publishAt"]))
        elif st.get("privacyStatus") == "public":
            out.append(_utc(v["snippet"]["publishedAt"]))
    return out


def next_slot(taken):
    from zoneinfo import ZoneInfo
    tz = ZoneInfo(SLOT_TZ)
    now = dt.datetime.now(dt.timezone.utc)
    day = now.astimezone(tz).date()
    for d in range(30):
        for s in SLOTS:
            hh, mm = map(int, s.split(":"))
            t = dt.datetime(day.year, day.month, day.day, hh, mm, tzinfo=tz) + dt.timedelta(days=d)
            t = t.astimezone(dt.timezone.utc)
            if t - now >= MIN_LEAD and all(abs(t - x) > dt.timedelta(minutes=90) for x in taken):
                return t
    sys.exit("no free slot in the next 30 days")


# ---------- upload ----------

def upload(video, meta, privacy, publish_at, token):
    status = {"privacyStatus": privacy, "selfDeclaredMadeForKids": False,
              "containsSyntheticMedia": False}
    if publish_at:
        status["privacyStatus"] = "private"
        status["publishAt"] = publish_at
    body = {"snippet": {**meta, "categoryId": CATEGORY_GAMING,
                        "defaultLanguage": "en", "defaultAudioLanguage": "en"}, "status": status}
    size = os.path.getsize(video)
    h = {"Authorization": f"Bearer {token}"}
    r = requests.post(UPLOAD_URL, params={"uploadType": "resumable", "part": "snippet,status"},
                      headers={**h, "Content-Type": "application/json; charset=UTF-8",
                               "X-Upload-Content-Type": "video/mp4",
                               "X-Upload-Content-Length": str(size)},
                      data=json.dumps(body), timeout=60)
    if r.status_code != 200:
        sys.exit(f"upload init failed: {r.status_code} {r.text}")
    with open(video, "rb") as f:
        r = requests.put(r.headers["Location"], headers={**h, "Content-Type": "video/mp4"},
                         data=f, timeout=900)
    if r.status_code not in (200, 201):
        sys.exit(f"upload failed: {r.status_code} {r.text}")
    return r.json()["id"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("names", nargs="*", help="clip names from clips.json")
    ap.add_argument("--all", action="store_true", help="every clip not in published.json")
    ap.add_argument("--auth", action="store_true")
    ap.add_argument("--whoami", action="store_true")
    ap.add_argument("--privacy", default="public", choices=["public", "unlisted", "private"])
    ap.add_argument("--slot", choices=["auto"], help="schedule at the next free slot (Rome time)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if a.auth:
        return auth_flow()
    clips = json.load(open(os.path.join(HERE, "clips.json")))
    streams = json.load(open(os.path.join(HERE, "data", "streams.json")))
    published = json.load(open(PUBLISHED))
    if a.whoami:
        ch = channel(access())
        return print(f"{ch['title']} {ch['id']} (GTA_CHANNEL_ID={env('GTA_CHANNEL_ID', False)})")
    names = [n for n in clips if n not in published] if a.all else a.names
    if not names:
        sys.exit("nothing to publish")
    token = ch = None
    if not a.dry_run:
        token = access()
        ch = checked_channel(token)
        log(f"channel OK: {ch['title']}")
    for n in names:
        if n in published:
            log(f"skip {n}: already published {published[n]['url']}")
            continue
        meta = build_metadata(n, clips[n], streams[clips[n]["stream"]])
        if a.dry_run:
            print(f"\n== {n}\nTITLE: {meta['title']}\n\n{meta['description']}\n")
            continue
        video = os.path.join(HERE, "out", f"{n}.mp4")
        if not os.path.exists(video):
            sys.exit(f"{video} missing: run python clip.py {n}")
        at = None
        if a.slot:
            # the uploads playlist lags behind fresh uploads, so also count our own records
            taken = taken_times(token, ch["uploads"]) + [
                _utc(p["publish_at"]) for p in published.values() if p.get("publish_at")]
            at = next_slot(taken).strftime("%Y-%m-%dT%H:%M:%SZ")
        log(f"uploading {n} ({os.path.getsize(video) / 1e6:.1f} MB, {at or a.privacy})")
        vid = upload(video, meta, a.privacy, at, token)
        published[n] = {"id": vid, "url": f"https://youtube.com/shorts/{vid}",
                        "publish_at": at, "title": meta["title"]}
        json.dump(published, open(PUBLISHED, "w"), indent=1)
        log(f"{'scheduled ' + at if at else 'published'}: {published[n]['url']}")


if __name__ == "__main__":
    main()
