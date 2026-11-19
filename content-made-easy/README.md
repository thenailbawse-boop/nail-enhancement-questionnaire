# Content Made Easy

My video editor. It cleans up a talking video (sound, dead air, repeats, ums), adds captions, puts edits on it
(Digital Zoom, Orbit, Pop Out, Info Cards, Tier List and more), and copies the edit of a reel I love, all in my brand.

## From my phone (no laptop, no Wi-Fi)

1. Open the Claude app, go to **Code**, and start a session on this repo, in the `nail-enhancement-questionnaire` environment.
2. Attach a video and type `/contentmadeeasy put Digital Zoom on it`, or just `/contentmadeeasy`.
3. Claude edits it in the cloud and sends the finished video back into the chat, phone-size so it's light on data.

To copy an edit: attach the reel (saved or screen-recorded) or paste its link, and say "copy this edit onto my video".

The editing runs on a cloud machine with its own internet: my hotspot only carries my video up and the finished one
back down.

## What's in here

| Folder or file | What it is |
| --- | --- |
| `.claude/skills/contentmadeeasy/` | The `/contentmadeeasy` steps Claude follows on the phone |
| `editor/` | The editor itself (also runs on a Mac: see `editor/READ-ME-FIRST.txt`) |
| `kit/` | The editing kit: caption fonts, caption styles, face finder |
| `brand/` | My brand (name, color, font, ending, logo), so every session remembers it |
| `my-copied-edits/` | Edits I copied from reels and saved |
| `setup-cloud.sh` | Gets a fresh cloud machine ready (the cloud environment runs it by itself) |
| `start-cloud.sh` | Turns the editor on in a cloud session |
| `phone-copy.sh` | Makes the 1080p copy that's quick to download |

## Credits

Content Made Easy is Tiff The AI Princess's free video editor. All credit for it goes to her: this folder is my
personalized copy that runs from my phone. The editing kit is Vibe Editing (MIT license, in `kit/`). The cloud
version reads on-screen text with RapidOCR.
