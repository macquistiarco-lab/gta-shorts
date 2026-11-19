# GTA Shorts - working notes

Clips from GTA 6 streams turned into vertical Shorts for the owner's GTA YouTube channel
(see README.md). Owner speaks Italian: reply in short Italian. This is NOT the finance channel:
never use `YT_*` variables or `shorts-agent` scripts here; publisher.py only reads `GTA_*`.

## Publish pending clips ("pubblica le clip GTA")
1. `pip install -q -r requirements.txt` if needed; `git pull origin main`.
2. `python clip.py <names>` for every clip in clips.json not in published.json (the source
   downloads from Drive by itself; ~1 min per clip). Look at 1-2 frames per clip.
3. `python publisher.py --all --slot auto`. If GTA_* variables are missing, stop and say so;
   never ask for tokens in chat.
4. Commit `published.json` on main and push. Final message: titles, links, scheduled times (Rome).

## New stream ("nuove clip da <drive link>")
1. Check the Drive file is shared "anyone with the link"; add it to data/streams.json
   (look at a frame to set the facecam `cam` and `game` crop boxes, 1280x720 coordinates).
2. `python transcribe.py <stream>` (background, ~15 min), commit the transcript.
3. Pick 4-6 moments where the streamer reacts (shouting, laughing, "bro what"), 30-60 s,
   add them to clips.json with `drop` ranges for lines spoken by game characters.
4. Render, check frames, send the mp4s with SendUserFile. Publish only after the owner says so.
