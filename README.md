# gta-shorts

Turns GTA 6 streams into vertical YouTube Shorts: facecam on top, gameplay below,
word-by-word captions of what the streamer says (swear words masked). Separate from the
finance channel (`shorts-agent`): own repo, own cloud environment, own credentials.

## Pipeline

1. **Source**: the stream mp4 on Google Drive, shared as "anyone with the link".
   Add it to `data/streams.json` (Drive file id, streamer, original URL, facecam/game crop boxes).
2. **Transcribe**: `python transcribe.py <stream>` -> `data/<stream>.transcript.json`
   (faster-whisper small on CPU, ~15 min for 35 min of stream; committed, so it runs once).
3. **Pick clips**: add entries to `clips.json` (start/end in seconds, hook text, `drop` ranges
   for game dialogue, title, description, hashtags).
4. **Render**: `python clip.py --all` (or one name) -> `out/<name>.mp4`. Downloads the source
   into `src/` the first time.
5. **Publish**: `python publisher.py --all --slot auto` schedules every clip not yet in
   `published.json` at the next free slot (19:00 / 23:00 Rome time) on the GTA channel.

`src/`, `out/`, `models/` are not committed.

## YouTube credentials (GTA channel)

Variables of the `gta-shorts` cloud environment, deliberately different from the finance
channel's `YT_*` so the two can never be mixed up:

| variable | value |
|---|---|
| `GTA_YT_CLIENT_ID` | OAuth client id (the same Google Cloud client as the finance channel is fine) |
| `GTA_YT_CLIENT_SECRET` | its secret |
| `GTA_YT_REFRESH_TOKEN` | from `python publisher.py --auth`, logging in and choosing the GTA channel |
| `GTA_CHANNEL_ID` | printed by `--auth` (UC...). Uploads to any other channel are refused. |

Get the token on your PC:

```bash
git clone https://github.com/macquistiarco-lab/gta-shorts && cd gta-shorts
pip install requests
GTA_YT_CLIENT_ID=... GTA_YT_CLIENT_SECRET=... python publisher.py --auth
```

## Copyright

Clips come from other creators' streams. Every description credits the streamer and links
the original, but that is not a licence: claims or strikes are possible. Prefer streamers who
allow clip channels.
