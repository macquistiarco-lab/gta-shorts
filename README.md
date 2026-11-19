# gta-shorts

Turns GTA 6 streams into vertical YouTube Shorts: facecam on top, gameplay below,
word-by-word captions of what the streamer says (swear words masked, slurs muted in the audio).
Separate from the finance channel (`shorts-agent`): own repo, own cloud environment, own credentials.

## Pipeline

1. **Source**, in `data/streams.json`:
   - a **Twitch VOD** (`twitch_vod` id): only the windows that are needed are downloaded (`hls.py`);
   - or an mp4 on **Google Drive** shared as "anyone with the link" (`drive_id`).
   Each stream also has the facecam (`cam`) and gameplay (`game`) crop boxes, `x, y, w, h` in
   the 1280x720 source, and `cam_w` (facecam width on screen). Layouts change during a stream:
   a clip can override `cam` / `game`.
2. **Transcribe**: `python transcribe.py <stream> [model]` -> `data/<stream>.transcript.json`.
   30-minute chunks, resumable, rewritten after every chunk so clips can be picked while it runs.
   `base.en` for long VODs (~2 min per hour of audio), `small` (default) for short ones.
   For a Twitch VOD, first get the audio:
   `python hls.py <vod> 0 200000 src/<stream>.audio.mp4 Audio_Only` then
   `ffmpeg -i src/<stream>.audio.mp4 -ac 1 -ar 16000 src/<stream>.wav`.
3. **Pick clips**: add entries to `clips.json` (start/end in seconds, hook text, `drop` ranges
   for game dialogue, title, description, hashtags, optional `cam` / `game`).
   `python transcribe.py <stream> --refine <start> <end>` re-transcribes the window with the
   better model into `data/<stream>.refined.json`, which `clip.py` prefers for captions.
4. **Render**: `python clip.py <name> ...` or `--all` -> `out/<name>.mp4`.
5. **Publish**: `python publisher.py --all --slot auto` schedules every clip not yet in
   `published.json` at the next free slot (14:00 / 18:00 Rome time) on the GTA channel.
   `--at` (exact time), `--after` (keep earlier slots empty), `--move NAME AT` (reschedule)
   and `--queue` (show the schedule) handle reordering. Exit code 3 means YouTube's rolling
   24-hour upload limit was hit: nothing was uploaded, retry later.

`src/`, `out/`, `models/` are not committed.

## Network (cloud environment `gta-shorts`)

Twitch VODs need `www.twitch.tv`, `gql.twitch.tv`, `usher.ttvnw.net` and the VOD's CloudFront
host (it differs per streamer, e.g. `d2nvs31859zcd8.cloudfront.net`,
`d2vi6trrdongqn.cloudfront.net`; `yt-dlp -f Audio_Only -g <vod url>` shows it).
ffmpeg ignores the HTTPS proxy, which is why `hls.py` fetches segments with requests.

## Clipping campaigns

`campaigns/*.md` holds each campaign's rules (Content Rewards / Reach). They decide the hook
text and hashtags (streamer's name, e.g. #LACY, #yourrage). Each posted link must be submitted
in the Content Rewards app within 30 minutes of going public.

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

## Copyright and content

Clips come from other creators' streams. Every description credits the streamer and links
the original, but that is not a licence: prefer streamers who allow clipping (campaigns).
Skip moments with licensed music on the in-game radio (Content ID claims), IRL segments,
and anything that shows the streamer or real people in a negative light.
