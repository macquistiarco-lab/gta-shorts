# GTA Shorts - working notes

Clips from GTA 6 streams turned into vertical Shorts for the owner's GTA YouTube channel
(see README.md). Owner speaks Italian: reply in short Italian. This is NOT the finance channel:
never use `YT_*` variables or `shorts-agent` scripts here; publisher.py only reads `GTA_*`.

## Publish pending clips ("pubblica le clip GTA")
1. `pip install -q -r requirements.txt` if needed; `git pull origin main`.
2. `python clip.py <names>` for every clip in clips.json not in published.json (sources
   download by themselves; ~1 min per clip). Look at 1-2 frames per clip.
3. Queue order wanted by the owner: campaign clips first (YourRAGE, then LACY), Speed clips
   after them. `python publisher.py --queue` shows it; use `--at` / `--move` to place clips,
   `--slot auto` only when no slot must stay empty (or with `--after`).
   If GTA_* variables are missing, stop and say so; never ask for tokens in chat.
   Exit code 3 = upload limit: schedule a retry with send_later, do not shift other clips yet.
4. Commit `published.json` on main and push. For campaign clips, a send_later reminder one
   minute after each one goes public: the owner submits the link within 30 minutes.
   Final message: titles, links, scheduled times (Rome).

## New stream ("nuove clip da <link>")
1. Twitch VOD: find the id (`yt-dlp --flat-playlist -J "https://www.twitch.tv/<user>/videos?filter=archives"`),
   check its CloudFront host is allowed, add it to data/streams.json. Drive: the file must be
   shared "anyone with the link". Look at frames at several times to set `cam` / `game`.
2. Audio + `python transcribe.py <stream> base.en` in the background (commands in README);
   commit the transcript every few chunks. Never kill it mid-run with a tool that might
   match its own command line (`pgrep -f` matches the shell running it).
3. Pick moments where the streamer reacts (shouting, laughing, "bro what"), 30-90 s.
   Score 30 s windows by reaction words, then read the text and look at a frame: skip
   cutscenes where only game characters talk, IRL segments, licensed radio music, slur-heavy
   or negative moments. `--refine` the window, add it to clips.json with the streamer's
   name in the hook and title and the campaign hashtag.
4. Render, check frames, send the mp4s plus a zip with TikTok captions (SendUserFile).
   Publish only after the owner says so.
