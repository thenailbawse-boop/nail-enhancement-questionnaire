#!/usr/bin/env python3
"""Post one finished video to Instagram through Publer, the way Tiff does it by hand (2026-10-30):

  1. a blue "How To ..." cover, every word one font, one size, filling the middle of the cover
  2. the regular Reel on her page, its caption ending in her call to action ("Comment SCALE ...")
  3. a Trial Reel set to MANUAL (it never jumps to her page by itself, so no duplicate), ending "Follow for more."
  4. both read back from Instagram itself, then the video and cover move to Posted with the date

Publer's API key and workspace live in the keys file the dashboard already reads. Nothing here goes out
without the person pressing Post on the page.
"""
import datetime, json, os, re, shutil, subprocess, time

from PIL import Image, ImageDraw, ImageFont

API = "https://app.publer.com/api/v1"
DIRECT_MAX = 195e6          # Publer refuses a direct upload over 200 MB


def cover(title, out, accent, fontfile):
    """1080x1920 cover. The words stay inside the middle 1080x1440 band: the IG grid crops to 3:4."""
    lines = split_title(title)
    W, H = 1080, 1920
    img = Image.new("RGB", (W, H), "#" + accent.lstrip("#"))
    d = ImageDraw.Draw(img)
    for size in range(400, 50, -2):
        f = ImageFont.truetype(fontfile, size)
        gap = int(size * 0.1)
        boxes = [d.textbbox((0, 0), t, font=f) for t in lines]
        hts = [b[3] - b[1] for b in boxes]
        tot = sum(hts) + gap * (len(lines) - 1)
        if max(b[2] - b[0] for b in boxes) <= 940 and tot <= 1280:
            break
    y = (H - tot) / 2
    for t, b, h in zip(lines, boxes, hts):
        d.text(((W - (b[2] - b[0])) / 2 - b[0], y - b[1]), t, font=f, fill="white")
        y += h + gap
    img.save(out)
    img.crop((0, 240, 1080, 1680)).resize((360, 480)).save(out.replace(".png", "-grid.png"))
    return out


def split_title(title):
    """HOW TO stays together on the first line; the rest breaks into short lines of one or two words."""
    words = title.upper().split()
    if words[:2] == ["HOW", "TO"]:
        lines, words = ["HOW TO"], words[2:]
    else:
        lines = []
    # a small word rides with the word after it: GET / BOOKED / TO SPEAK / WITH AI (her approved cover)
    small = {"TO", "IN", "WITH", "A", "AN", "THE", "OF", "FOR", "ON", "AT", "BY", "AND", "OR", "YOUR", "MY"}
    i = 0
    while i < len(words):
        if words[i] in small and i + 1 < len(words):
            lines.append(words[i] + " " + words[i + 1])
            i += 2
        else:
            lines.append(words[i])
            i += 1
    return lines


def ig_copy(video, work, ff, fp):
    """Publer takes 200 MB at most. A bigger 4K file is re-made as 4K HEVC that fits, then its bitrate is read back."""
    if os.path.getsize(video) <= DIRECT_MAX:
        return video
    secs = float(subprocess.run([fp, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", video],
                                capture_output=True, text=True).stdout.strip())
    kbps = int(DIRECT_MAX * 8 / secs / 1000 * 0.92) - 192
    out = os.path.join(work, "instagram.mp4")
    if shutil.disk_usage(work).free < DIRECT_MAX * 2:
        raise RuntimeError("Not enough free disk space to make the Instagram copy.")
    subprocess.run([ff, "-v", "error", "-y", "-i", video, "-map", "0:v:0", "-map", "0:a:0?", "-c:v", "hevc_videotoolbox",
                    "-tag:v", "hvc1", "-b:v", f"{kbps}k", "-maxrate", f"{int(kbps * 1.3)}k", "-c:a", "aac", "-b:a", "192k",
                    "-movflags", "+faststart", out], check=True)
    if os.path.getsize(out) > DIRECT_MAX * 1.02:
        raise RuntimeError("The Instagram copy came out too big for Publer.")
    return out


class Publer:
    def __init__(self, api_key, workspace):
        if not api_key or not workspace:
            raise RuntimeError("Publer isn't connected yet. Add your Publer API key in the setup boxes.")
        self.h = ["-H", f"Authorization: Bearer-API {api_key}", "-H", f"Publer-Workspace-Id: {workspace}"]

    def call(self, method, path, body=None, form=None):
        cmd = ["curl", "-s", "-X", method, *self.h, API + path]
        if body is not None:
            cmd += ["-H", "Content-Type: application/json", "-d", json.dumps(body)]
        for k, v in (form or {}).items():
            cmd += ["-F", f"{k}={v}"]
        out = subprocess.run(cmd, capture_output=True, text=True).stdout
        try:
            return json.loads(out)
        except ValueError:
            raise RuntimeError(f"Publer answered something I couldn't read: {out[:160]}")

    def instagram(self):
        acc = [a for a in self.call("GET", "/accounts") if a.get("provider") == "instagram"]
        if not acc:
            raise RuntimeError("No Instagram account is connected in Publer.")
        return acc[0]["id"]

    def upload(self, path):
        # the type has to be said out loud: without it Publer answers "File is not supported" (2026-10-30)
        kind = {".mp4": "video/mp4", ".png": "image/png", ".jpg": "image/jpeg"}.get(os.path.splitext(path)[1].lower(), "")
        r = self.call("POST", "/media", form={"file": f"@{path};type={kind}" if kind else f"@{path}", "in_library": "true"})
        if not r.get("id"):
            raise RuntimeError(f"Publer didn't take {os.path.basename(path)}: {r.get('errors') or r}")
        return r

    def wait(self, job_id, say, what, limit=1800):
        t0 = time.time()
        while time.time() - t0 < limit:
            r = self.call("GET", f"/job_status/{job_id}")
            if r.get("status") != "working":
                fails = [p.get("failure", {}).get("message") for p in (r.get("payload") or [])
                         if isinstance(p, dict) and p.get("status") == "failed"] if isinstance(r.get("payload"), list) else []
                if r.get("status") == "failed" or fails:
                    raise RuntimeError(f"Publer said no to the {what}: {fails[0] if fails else r}")
                return r
            say(f"Instagram is still taking in the {what} ({int(time.time() - t0) // 60} min so far)")
            time.sleep(20)
        raise RuntimeError(f"The {what} was still going after {limit // 60} minutes. Check Publer.")

    def live_link(self, text_start, after, limit=1800):
        """Read the post back: its state and Instagram link, never the job's word for it."""
        t0 = time.time()
        while time.time() - t0 < limit:
            for p in self.call("GET", "/posts?limit=10").get("posts", []):
                if (p.get("text") or "").startswith(text_start) and p.get("id") not in after:
                    if p.get("state") == "published" and p.get("post_link"):
                        return p["id"], p["post_link"]
                    if p.get("state") == "failed":
                        raise RuntimeError(f"The post failed in Publer: {p.get('error')}")
            time.sleep(20)
        raise RuntimeError("The post never showed as published. Check Publer.")


def post_both(video, title, body, ending, trial_ending, hashtags, work, keys, accent, fontfile, ff, fp, say, posted_dir=None):
    pub = Publer(keys.get("PUBLER_API_KEY"), keys.get("PUBLER_WORKSPACE_ID"))
    account = pub.instagram()
    say("Making the cover")
    cov = cover(title, os.path.join(work, "cover.png"), accent, fontfile)
    say("Getting the video ready for Publer")
    up_video = ig_copy(video, work, ff, fp)
    say("Sending the video to Publer")
    med = pub.upload(up_video)
    if not med.get("validity", {}).get("instagram", {}).get("reel"):
        raise RuntimeError("Publer says this video can't be an Instagram Reel (length or shape).")
    cv = pub.upload(cov)
    thumbs = [{k: t[k] for k in ("id", "small", "real")} for t in med.get("thumbnails", [])]
    thumbs.append({"id": cv["id"], "small": cv.get("thumbnail") or cv["path"], "real": cv["path"]})

    def caption(end):
        return "\n\n".join(x.strip() for x in (body, end, hashtags) if x and x.strip())

    def payload(text, trial, at=None):
        details = {"type": "reel"}
        if trial:
            details["trial_reel"] = "MANUAL"
        acc = {"id": account}
        if at:
            acc["scheduled_at"] = at
        return {"bulk": {"state": "scheduled", "posts": [{"networks": {"instagram": {
            "type": "video", "text": text, "details": details,
            "media": [{"id": med["id"], "path": med["path"], "type": "video", "thumbnails": thumbs,
                       "default_thumbnail": len(thumbs) - 1}]}}, "accounts": [acc]}]}}

    before = {p["id"] for p in pub.call("GET", "/posts?limit=10").get("posts", [])}
    say("Posting the Reel to your page")
    r = pub.call("POST", "/posts/schedule/publish", payload(caption(ending), False))
    pub.wait(r["job_id"], say, "Reel")
    reg_id, reg_link = pub.live_link(body.strip()[:40], before)
    say(f"Your Reel is live: {reg_link}")

    # Publer needs a gap of at least a minute between two posts on one account (2026-10-30)
    at = (datetime.datetime.now().astimezone() + datetime.timedelta(minutes=2)).replace(second=0, microsecond=0).isoformat()
    say("Posting the Trial Reel (Manual, it stays a trial)")
    r = pub.call("POST", "/posts/schedule", payload(caption(trial_ending), True, at))
    pub.wait(r["job_id"], say, "Trial Reel")
    tri_id, tri_link = pub.live_link(body.strip()[:40], before | {reg_id})
    say(f"Your Trial Reel is live: {tri_link}")

    moved = []
    if posted_dir and os.path.isdir(posted_dir):
        stamp = time.strftime("%Y-%m-%d")
        name = re.sub(r"[^\w &'-]", "", title).strip()[:80] or "Instagram Reel"
        for src, dst in ((video, f"{stamp} {name}.mp4"), (cov, f"{stamp} {name} COVER.png")):
            out = os.path.join(posted_dir, dst)
            size = os.path.getsize(src)
            # same drive: a real move. Anywhere else: a copy, and the original stays where it was
            if src == video and os.stat(src).st_dev == os.stat(posted_dir).st_dev:
                os.rename(src, out)
            else:
                shutil.copy2(src, out)
            if os.path.getsize(out) != size:
                raise RuntimeError(f"{dst} came out the wrong size in Posted.")
            moved.append(out)
        say(f"Moved the video and cover to Posted with today's date")
    return {"reel": reg_link, "trial": tri_link, "moved": moved}
