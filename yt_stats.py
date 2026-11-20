"""Read the GTA channel's public numbers for the HUD dashboard.

    python yt_stats.py > /tmp/yt.json

Uses the same GTA_* credentials as publisher.py and refuses any channel other than
GTA_CHANNEL_ID. Read-only: channels.list and videos.list (YouTube Data API, ~3 quota units).
Then write it with ArtifactData: `set` hud/youtube from the file, and add one
`ythist/<YYYYMMDDHHMM>` doc {at, subscribers, views, videos} for the trend line.
"""
import datetime as dt
import json
import re

import requests

import publisher as pub


def seconds(iso):
    m = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso or "")
    if not m:
        return None
    h, mi, s = (int(x or 0) for x in m.groups())
    return h * 3600 + mi * 60 + s


def main():
    token = pub.access()
    ch = pub.checked_channel(token)
    h = {"Authorization": f"Bearer {token}"}
    r = requests.get(f"{pub.API}/channels", params={"part": "statistics", "id": ch["id"]}, headers=h, timeout=30)
    r.raise_for_status()
    st = r.json()["items"][0]["statistics"]

    ids = []
    r = requests.get(f"{pub.API}/playlistItems", params={
        "part": "contentDetails", "playlistId": ch["uploads"], "maxResults": 50}, headers=h, timeout=30)
    if r.status_code != 404:
        r.raise_for_status()
        ids = [i["contentDetails"]["videoId"] for i in r.json()["items"]]
    items = []
    if ids:
        r = requests.get(f"{pub.API}/videos", params={
            "part": "snippet,statistics,status,contentDetails", "id": ",".join(ids)}, headers=h, timeout=30)
        r.raise_for_status()
        for v in r.json()["items"]:
            s, vs = v["status"], v.get("statistics", {})
            items.append({
                "id": v["id"],
                "title": v["snippet"]["title"],
                "url": f"https://youtube.com/shorts/{v['id']}",
                "published_at": v["snippet"].get("publishedAt"),
                "privacy": s.get("privacyStatus"),
                "publish_at": s.get("publishAt"),
                "views": int(vs.get("viewCount", 0)),
                "likes": int(vs.get("likeCount", 0)),
                "comments": int(vs.get("commentCount", 0)),
                "seconds": seconds(v["contentDetails"].get("duration")),
            })
    items.sort(key=lambda x: x["views"], reverse=True)
    out = {
        "fetched_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "channel": {
            "title": ch["title"],
            "subscribers": None if st.get("hiddenSubscriberCount") else int(st.get("subscriberCount", 0)),
            "views": int(st.get("viewCount", 0)),
            "videos": int(st.get("videoCount", 0)),
        },
        "items": items,
    }
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
