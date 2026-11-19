#!/usr/bin/env python3
"""Content Dashboard: drop in a long video, pick a template, get finished shorts.

Runs only on this Mac (http://127.0.0.1:8787). Nothing posts, sends or spends: every result
lands in jobs/<id>/out/ for a person to look at. Stop it with Ctrl-C or by closing its window.

It needs the Vibe Editing kit (Box 1) and DeepFilterNet (Box 2). Its own copies of the steps live in
engine/, so it does not depend on Tiff's personal files:
  transcribe   engine/transcribe.py   (free Groq key, else this computer)
  pick moments Groq's free chat model, rules from the hook-and-script method, then a person picks the hooks
  clean sound  engine/clean_audio.py  (DeepFilterNet)
  finish       engine/finisher.py     (9:16, captions and hook in the owner's brand from brand.json)
Then it READS THE LEDGER on every short before calling it done (see ledger()).
"""
import hashlib, json, os, re, shutil, subprocess, sys, tempfile, threading, time, traceback, uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

HOME = os.path.expanduser("~")
HERE = os.path.dirname(os.path.abspath(__file__))
JOBS = os.path.join(HERE, "jobs")
BIN = os.path.join(HOME, ".local/bin")
# a .command started from Finder gets a bare PATH; Homebrew and the kit put tools in these places
os.environ["PATH"] = os.pathsep.join([BIN, "/opt/homebrew/bin", "/usr/local/bin", os.environ.get("PATH", "/usr/bin:/bin")])
FF = shutil.which("ffmpeg") or os.path.join(BIN, "ffmpeg")
FP = shutil.which("ffprobe") or os.path.join(BIN, "ffprobe")
VENV_PY = os.path.join(HOME, "vibe-editing/.venv/bin/python")
ENGINE = os.path.join(HERE, "engine")
FINISHER = os.path.join(ENGINE, "finisher.py")
CLEANER = os.path.join(ENGINE, "clean_audio.py")
KIT = os.path.join(HOME, "vibe-editing/plugins/vibe-editing")
YUNET = os.path.join(KIT, "skills/horizontal-to-vertical/scripts/yunet.onnx")
CAPTIONS = os.path.join(KIT, "skills/caption-clips")
SAVED = os.path.join(HOME, "Content Made Easy Brand")
os.makedirs(SAVED, exist_ok=True)
BRAND_FILE = os.path.join(SAVED, "brand.json")
FONTS = {"Bold Caps": "Montserrat-ExtraBold.ttf", "Tall": "Anton.ttf", "Clean": "Poppins-Black.ttf", "Classic": "BebasNeue.ttf",
         "Elegant Serif": "DMSerifDisplay.ttf", "Script": "Pacifico.ttf", "Simple": "Inter-SemiBold-static.ttf"}
# CapCut's most used free caption fonts that the kit already ships, fixed weight so they draw bold.
# The brand finder only measures against FONTS above; these are for the person to pick by eye.
CAPCUT = {"Bangers": "Bangers.ttf", "Archivo Black": "ArchivoBlack.ttf", "Titan One": "TitanOne.ttf",
          "Passion One": "PassionOne-Bold.ttf", "Kanit": "Kanit-ExtraBold.ttf", "Russo One": "RussoOne.ttf",
          "Staatliches": "Staatliches.ttf", "Alfa Slab One": "AlfaSlabOne.ttf", "Bowlby One": "BowlbyOneSC.ttf",
          "Black Ops One": "BlackOpsOne.ttf", "Lato Black": "Lato-Black.ttf", "Poppins ExtraBold": "Poppins-ExtraBold.ttf"}
ALL_FONTS = {**FONTS, **CAPCUT}
OWN_FONT = "My own font"     # Tiff's copy: her TiffCaps file, saved in brand.json as fontfile
FONT_LABELS = {"Bold Caps": "Montserrat", "Tall": "Anton", "Clean": "Poppins Black", "Classic": "Bebas Neue",
               "Elegant Serif": "DM Serif", "Script": "Pacifico", "Simple": "Inter"}
FONT_LOOKS = {"Bold Caps": "heavy wide geometric sans, like Montserrat ExtraBold or Arial Black",
              "Tall": "very tall, tightly condensed heavy sans, like Anton, Impact or League Gothic",
              "Clean": "round, friendly, heavy sans, like Poppins Black or Proxima Nova Black",
              "Classic": "thin-stroked tall condensed all-caps, like Bebas Neue or Oswald",
              "Elegant Serif": "high-contrast fashion serif, like Playfair, DM Serif or Didot",
              "Script": "handwritten or brush script, like Pacifico or a signature font",
              "Simple": "clean everyday sans, medium weight, mixed case, like the iPhone or Instagram's own text"}
VISION_MODEL = "qwen/qwen3.8-27b"     # Groq's free model that can look at pictures
KEYS = os.path.join(HOME, "vibe-editing/plugins/vibe-editing/config/keys.env")
PICK_MODEL = "openai/gpt-oss-120b"
WINDOW = 480          # seconds of transcript per moment-picking call (free plan: 8,000 tokens a minute)
FPS = 30              # tiff_short.py feeds its frames at 30 a second, so every cut is made at 30
os.makedirs(JOBS, exist_ok=True)
# 2026-11-02, Tiff: the AI Editor Package goes under Ajene Pinnock Styles. Her copy only: build-member-copy.sh never ships this folder.
AJENE_PACK = os.path.join(HERE, "ajene-pack")
AJENE_STUDIO = os.path.join(HOME, ".claude/skills/edit-studio/scripts/start_studio.sh")
# previews from the Claude Video FX Kit (AI Employee Lab). Its license is for members' own videos.
FX_KIT = os.path.join(HOME, "Claude-Video-FX")
FX_DIR = os.path.join(FX_KIT, "examples")

TEMPLATES = [
    {"id": "shorts", "name": "Long Video to Shorts", "live": True,
     "what": "A replay, a live or a long talk goes in. Your best 20 to 45 second moments come out as vertical shorts with captions and a hook on top."},
    {"id": "copycat", "name": "IG Reels Copycat", "live": True,
     "what": "Paste a creator's Instagram or a reel. It reads their edit frame by frame: cuts, zooms, headline, captions, call to action. Pick one and your video gets that edit, with your words and your call to action."},
    {"id": "mystyle", "name": "Your Own Style", "live": True,
     "what": "Paste YOUR Instagram. It learns how you edit once, saves it, and every video you drop after that comes out in your style. Endless content."},
    {"id": "ajene", "name": "Ajene Pinnock Styles", "live": False,
     "what": "47 editing templates: reels, YouTube and captions. Tap to see them all, then open Edit Studio and pick one."},
    {"id": "carousel", "name": "Carousel Ideas", "live": False,
     "what": "Pick one of 25 carousel shapes, type your idea, get the slides back."},
    {"id": "showreel", "name": "Showreel", "live": False, "example": "/showreel-example.mp4",
     "what": "Show off what you offer. Your screens, your clips and your words, each with a big title in your font on your brand color, cut into one short video. This one is the Marketing Dashboard's."},
    {"id": "split", "name": "Split Screen", "live": False, "example": "/split-example.mp4",
     "what": "You on one half, custom graphics for what you're saying on the other. Drop your video, get a finished split screen short."},
]


def key(name):
    try:
        m = re.search(rf"^{name}=(\S+)", open(KEYS).read(), re.M)
        return m.group(1) if m else ""
    except OSError:
        return ""


def probe(path, count=True):
    """count=True reads every packet (the ledger). Never on a long source: it reads the whole file."""
    out = subprocess.run([FP, "-v", "error", *(["-count_packets"] if count else []), "-show_entries",
                          "stream=index,codec_type,codec_name,width,height,r_frame_rate,sample_rate,nb_read_packets,duration"
                          ":format=duration", "-of", "json", path], capture_output=True, text=True)
    if out.returncode:
        raise RuntimeError(f"ffprobe could not read {os.path.basename(path)}: {out.stderr[-200:]}")
    return json.loads(out.stdout)


def video_secs(path):
    """Length in seconds for the page (it tells people effects land best on 30 to 90 s), 0 if unreadable."""
    try:
        return round(float(probe(path, count=False)["format"]["duration"]), 1)
    except Exception:
        return 0


def stream(info, kind):
    return next((s for s in info["streams"] if s["codec_type"] == kind), None)


def deep_filter():
    p = os.path.join(BIN, "deep-filter")
    return p if os.path.exists(p) else shutil.which("deep-filter")


def brand():
    """The owner's look. Tiff's copy points at her own preset and font; a member's starts from the kit's."""
    b = {"name": "", "accent": "00A6FF", "font": "Bold Caps", "preset": "", "fontfile": ""}
    try:
        b.update(json.load(open(BRAND_FILE)))
    except (OSError, ValueError):
        pass
    return b


# Logo and music from the brand section, saved once on this computer and added to every finished video.
ASSETS = os.path.join(SAVED, "brand-assets")


def brand_finish(job, out):
    """Their logo small in the top-right corner and their music softly under their voice, when they gave
    us those in the brand interview. One re-encode, then it is counted again like everything else."""
    b = brand()
    logo = b.get("logo") if b.get("logo") and os.path.exists(b["logo"]) else None
    music = b.get("music") if b.get("music") and os.path.exists(b["music"]) else None
    if not (logo or music):
        return
    d = float(probe(out, count=False)["format"]["duration"])
    ins, fc, vmap, amap = ["-i", out], [], "0:v", "0:a"
    if logo:
        ins += ["-i", logo]
        fc.append(f"[1:v]scale=150:-1,format=rgba,colorchannelmixer=aa=0.9[lg];[0:v][lg]overlay=W-w-48:60[v]")
        vmap = "[v]"
    if music:
        ins += ["-stream_loop", "-1", "-i", music]
        k = 2 if logo else 1
        fc.append(f"[{k}:a]aresample=48000,volume=0.12,afade=t=in:d=1,afade=t=out:st={max(0.0, d - 1.5):.2f}:d=1.5[m];"
                  f"[0:a][m]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[a]")
        amap = "[a]"
    tmp = out[:-4] + ".brand.mp4"
    subprocess.run([FF, "-v", "error", *ins, "-filter_complex", ";".join(fc), "-map", vmap, "-map", amap, "-t", f"{d:.3f}",
                    *(["-c:v", "libx264", "-crf", "17", "-preset", "fast", "-pix_fmt", "yuv420p"] if logo else ["-c:v", "copy"]),
                    "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-y", tmp], check=True)
    os.replace(tmp, out)
    job.say("Added your " + " and ".join(x for x, y in (("logo", logo), ("music", music)) if y))


def brand_files(b):
    """(preset path, hook font path). A member's preset is the kit's spice look with numbers in their color."""
    if b.get("preset") and os.path.exists(b["preset"]) and os.path.exists(b.get("fontfile", "")):
        # her own caption look stays; the hook font is her own file unless she picked another one
        return b["preset"], b["fontfile"] if b.get("font") in (OWN_FONT, None) or b.get("font") not in ALL_FONTS \
            else os.path.join(CAPTIONS, "fonts", ALL_FONTS[b["font"]])
    p = json.load(open(os.path.join(CAPTIONS, "presets/spice.json")))
    p["number_color"] = b["accent"].lstrip("#").upper()
    p["font_size_px"] = 250          # the kit default (150) reads tiny on a phone; same size as Tiff's own look
    p["colors"]["guest"] = p["number_color"]
    from PIL import ImageFont
    ensure_simple_font()
    cap_file = ALL_FONTS.get(b.get("font"), FONTS["Bold Caps"])
    if not os.path.exists(os.path.join(CAPTIONS, "fonts", cap_file)):
        cap_file = FONTS["Bold Caps"]
    fam, sty = ImageFont.truetype(os.path.join(CAPTIONS, "fonts", cap_file), 20).getname()
    fam = fam if sty in ("Regular", "Book", "") else f"{fam} {sty}"   # the burner finds fonts by name
    cap_dir = os.path.join(CAPTIONS, "fonts", "dashboard_brand")
    os.makedirs(cap_dir, exist_ok=True)
    if sorted(os.listdir(cap_dir)) != [cap_file]:
        for old in os.listdir(cap_dir):
            os.remove(os.path.join(cap_dir, old))
        shutil.copy(os.path.join(CAPTIONS, "fonts", cap_file), cap_dir)
    p["fonts_dir"] = "fonts/dashboard_brand"
    p["weights"] = {k: fam for k in p["weights"]}
    p["uppercase"] = b.get("font") not in ("Script", "Elegant Serif")
    p["italic_fax"] = 0
    p["emphasis_color"] = p["number_color"]
    path = os.path.join(CAPTIONS, "presets/dashboard_brand.json")
    json.dump(p, open(path, "w"), indent=1)
    return path, os.path.join(CAPTIONS, "fonts", ALL_FONTS.get(b.get("font"), FONTS["Bold Caps"]))


BRAND_ASK = """These are 6 frames from one short video. The person wants their videos to look like this.
Look at the text ON the video: the big hook or title text, and the captions.
1. hook_font: which of these is CLOSEST to the hook or title text? {fonts}
2. caption_font: which is closest to the caption text? Same list.
3. accent: the main brand color used on the text, highlights, bars or emphasized words, as #RRGGBB.
   Never pick plain white, black or grey if any real color is used. If the text is only white, say #FFFFFF.
4. text_color: the main caption color as #RRGGBB.
5. all_caps: true if the text is mostly ALL CAPS.
6. notes: one short sentence describing the look in plain words.
Return ONLY JSON: {{"hook_font": "", "caption_font": "", "accent": "#", "text_color": "#", "all_caps": true, "notes": ""}}"""


def ask_vision(text, jpg):
    """Ask Groq's free picture reader. The free plan allows 200,000 tokens a DAY and a big picture costs
    thousands (2026-10-26 testing used the day up), so pictures go small, the answer is kept short,
    and every caller copes with this returning {} instead of an answer."""
    import base64, requests
    small = jpg + ".small.jpg"
    subprocess.run([FF, "-v", "error", "-i", jpg, "-vf", "scale='min(900,iw)':-2", "-q:v", "5", "-y", small], capture_output=True)
    b64 = base64.b64encode(open(small if os.path.exists(small) else jpg, "rb").read()).decode()
    for attempt in range(8):           # the free plan says "wait" when two things use it at once
        r = requests.post("https://api.groq.com/openai/v1/chat/completions", timeout=(30, 120),
                          headers={"Authorization": f"Bearer {key('GROQ_API_KEY')}"},
                          json={"model": VISION_MODEL, "max_tokens": 600, "messages": [{"role": "user", "content": [
                              {"type": "text", "text": text},
                              {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + b64}}]}]})
        if r.status_code == 200:
            out = r.json()["choices"][0]["message"]["content"]
            m = re.search(r"\{.*\}", out, re.S)
            if m:
                return json.loads(m.group(0))
        elif r.status_code == 429:
            if "per day" in r.text or "TPD" in r.text:
                return {}                      # out for today: carry on with what the Mac measured
            try:
                wait = float(r.headers.get("retry-after") or 15)
            except ValueError:
                wait = 15
            if wait > 90:
                return {}
            time.sleep(wait + 1); continue
        time.sleep(5)
    return {}


def font_sheet(path):
    """One labeled sample of every font option, so the model compares shapes instead of guessing names."""
    from PIL import Image, ImageDraw, ImageFont
    names = list(FONTS)
    img = Image.new("RGB", (1440, 110 * len(names)), (30, 30, 30))
    d = ImageDraw.Draw(img)
    lab = ImageFont.truetype(os.path.join(CAPTIONS, "fonts", "Inter.ttf"), 30)
    for i, n in enumerate(names):
        d.text((20, 110 * i + 38), n, font=lab, fill=(255, 210, 0))
        d.text((330, 110 * i + 15), "MAKE MONEY with AI 123", font=ImageFont.truetype(os.path.join(CAPTIONS, "fonts", FONTS[n]), 70), fill=(255, 255, 255))
    img.save(path, quality=90)


def true_color(frames, hexcode):
    """The model's color is a guess. Group the strongly colored pixels in the frames and take the group
    closest to the guess, so the hex is what is really on screen."""
    import cv2, numpy as np
    try:
        want = np.array([int(hexcode.lstrip("#")[i:i + 2], 16) for i in (4, 2, 0)], dtype=np.float32)   # BGR
    except ValueError:
        return hexcode, 0
    px = []
    for f in frames:
        img = cv2.imread(f)
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV).reshape(-1, 3)
        keep = (hsv[:, 1] > 110) & (hsv[:, 2] > 110)
        px.append(img.reshape(-1, 3)[keep])
    px = np.concatenate(px).astype(np.float32) if px else np.zeros((0, 3), np.float32)
    if max(want) - min(want) < 40:
        # the model saw no brand color. Guessing one from the picture picked skin and background colors
        # in testing (2026-10-26), so say "none found" and let the person tap theirs.
        return "#FFFFFF", 0
    if len(px) < 200:                                    # no strong color anywhere on screen
        return "#" + hexcode.lstrip("#").upper(), int(len(px))
    k = min(6, len(px) // 50)
    _, labels, centers = cv2.kmeans(px, k, None, (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0), 3, cv2.KMEANS_PP_CENTERS)
    best = int(np.argmin(np.linalg.norm(centers - want, axis=1)))
    if np.linalg.norm(centers[best] - want) > 120:
        return "#" + hexcode.lstrip("#").upper(), 0
    grp = px[labels.ravel() == best]
    grp = grp[grp.sum(axis=1) >= np.percentile(grp.sum(axis=1), 60)]     # the solid fill, not the soft edges
    b, g, r = np.median(grp, axis=0)
    return f"#{int(r):02X}{int(g):02X}{int(b):02X}", int((labels.ravel() == best).sum())


def stroke(mask):
    """How thick the letter strokes are, in pixels: twice the typical distance from the middle of a stroke to its edge."""
    import cv2, numpy as np
    dt = cv2.distanceTransform(mask.astype(np.uint8), cv2.DIST_L2, 3)
    v = dt[dt > 0]
    return 2 * float(np.percentile(v, 90)) if len(v) else 0.0



def ocr_cmd():
    """The text reader: macOS's own (ocr.swift) on a Mac, RapidOCR (engine/ocr.py) everywhere else,
    so Copy an edit you love works on Linux, Windows and in a cloud session too."""
    if sys.platform == "darwin":
        ocr = os.path.join(ENGINE, "ocr")
        if not os.path.exists(ocr):
            subprocess.run(["swiftc", "-O", os.path.join(ENGINE, "ocr.swift"), "-o", ocr], capture_output=True)
        if os.path.exists(ocr):
            return [ocr]
    return [VENV_PY, os.path.join(ENGINE, "ocr.py")]


def match_font(frames_big, zone="top"):
    """Measure, don't guess: read the on-screen text with macOS's own text reader, write the same words in
    every font option at the same height, and pick the font whose width and thickness match best.
    Returns (hook_font, how_many_lines_measured) or (None, 0) when there is no text to read."""
    import cv2, numpy as np
    from PIL import Image, ImageDraw, ImageFont
    ensure_simple_font()
    ocr = ocr_cmd()
    score, lines = {k: [] for k in FONTS}, 0
    for f in frames_big:
        try:
            found = json.loads(subprocess.run([*ocr, f], capture_output=True, text=True, timeout=60).stdout or "[]")
        except Exception:
            continue
        img = cv2.imread(f)
        H, W = img.shape[:2]
        # the hook is the biggest text in the top third of the frame
        if zone == "top":     # the hook is the biggest text in the top third of the frame
            tops = sorted([o for o in found if o["conf"] > 0.8 and len(o["text"].strip()) >= 4 and o["y"] < 0.33],
                          key=lambda o: -o["h"])[:2]
        else:                 # captions: centered text in the middle band, not app or screenshot text
            tops = [o for o in found if o["conf"] > 0.8 and len(o["text"].strip()) >= 4 and 0.3 < o["y"] + o["h"] / 2 < 0.88
                    and o["h"] >= 0.022 and abs(o["x"] + o["w"] / 2 - 0.5) < 0.12][:3]
        for o in tops:
            pad = int(o["h"] * H * 0.3)       # the reader's box can clip the first and last letters
            x0, y0 = int(o["x"] * W) - pad, int(o["y"] * H) - 6
            crop = img[max(0, y0):int((o["y"] + o["h"]) * H) + 6, max(0, x0):int((o["x"] + o["w"]) * W) + pad]
            hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
            ink = (hsv[..., 2] > 190) & (hsv[..., 1] < 80)
            ys, xs = np.nonzero(ink)
            if len(xs) < 80:
                continue
            ow, oh = xs.max() - xs.min() + 1, ys.max() - ys.min() + 1
            box = ink[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
            od = box.mean()
            ost = stroke(box) / oh
            for name, ttf in FONTS.items():
                ft = ImageFont.truetype(os.path.join(CAPTIONS, "fonts", ttf), 160)
                canvas = Image.new("L", (3000, 400), 0)
                ImageDraw.Draw(canvas).text((20, 60), o["text"], font=ft, fill=255)
                a = np.array(canvas) > 128
                ry, rx = np.nonzero(a)
                if len(rx) == 0:
                    score[name].append(9); continue
                rw, rh = rx.max() - rx.min() + 1, ry.max() - ry.min() + 1
                rbox = a[ry.min():ry.max() + 1, rx.min():rx.max() + 1]
                rd = rbox.mean()
                score[name].append(abs(np.log((rw * oh / rh) / ow)) + 1.5 * abs(rd - od) + 6 * abs(stroke(rbox) / rh - ost))
            lines += 1
    if not lines:
        return None, 0
    med = {k: float(np.median(v)) for k, v in score.items()}
    return min(med, key=med.get), lines


def brand_from_site(url):
    """Read a person's own website: its name, main color, heading font and logo. Whatever isn't there comes back
    empty, and the page asks for it. Nothing is guessed."""
    import requests, colorsys, collections, html as H
    from urllib.parse import urljoin
    if not re.match(r"https?://", url):
        url = "https://" + url
    head = {"User-Agent": "Mozilla/5.0 (Macintosh) Content Made Easy brand reader"}
    page = requests.get(url, headers=head, timeout=20)
    page.raise_for_status()
    doc = page.text
    css = "\n".join(re.findall(r"<style[^>]*>(.*?)</style>", doc, re.S | re.I))
    links = re.findall(r"<link[^>]+>", doc, re.I)
    for tag in links:
        if re.search(r"rel=[\"']?stylesheet", tag, re.I):
            m = re.search(r"href=[\"']([^\"']+)", tag)
            if m:
                try:
                    css += "\n" + requests.get(urljoin(page.url, H.unescape(m.group(1))), headers=head, timeout=15).text[:1500000]
                except requests.RequestException:
                    pass
    def meta(*names):
        for n in names:
            for t in re.findall(r"<meta[^>]+>", doc, re.I):
                if re.search(rf"(?:name|property)=[\"']{n}[\"']", t, re.I):
                    c = re.search(r"content=[\"']([^\"']+)", t)
                    if c:
                        return H.unescape(c.group(1)).strip()
        return ""

    def colorful(h):
        r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
        _, l, sat = colorsys.rgb_to_hls(r, g, b)
        return sat > 0.3 and 0.15 < l < 0.8
    accent, theme = "", meta("theme-color").lstrip("#")
    if re.fullmatch(r"[0-9A-Fa-f]{6}", theme) and colorful(theme):
        accent = theme.upper()
    else:
        seen = collections.Counter(x.upper() for x in re.findall(r"#([0-9A-Fa-f]{6})\b", css + doc) if colorful(x))
        if seen:
            accent = seen.most_common(1)[0][0]
    names = {v.lower(): k for k, v in FONT_LABELS.items()}
    names.update({k.lower(): k for k in ALL_FONTS})
    fams = collections.Counter(f.strip(" \"'").lower() for x in re.findall(r"font-family:\s*([^;}]+)", css) for f in x.split(",")[:1])
    gf = [x.replace("+", " ").lower() for x in re.findall(r"fonts\.googleapis\.com/css2?\?family=([^:&\"']+)", doc)]
    font = next((names[f] for f in gf + [x for x, _ in fams.most_common()] if f in names), "")
    logo = ""
    imgs = re.findall(r"<img[^>]+>", doc, re.I)
    for t in imgs:
        if re.search(r"logo", t, re.I):
            m = re.search(r"src=[\"']([^\"']+)", t)
            if m and not m.group(1).lower().split("?")[0].endswith(".svg"):
                logo = urljoin(page.url, H.unescape(m.group(1)))
                break
    if not logo:
        for t in links:
            if re.search(r"apple-touch-icon", t, re.I):
                m = re.search(r"href=[\"']([^\"']+)", t)
                if m:
                    logo = urljoin(page.url, H.unescape(m.group(1)))
                    break
    has_logo = False
    if logo:
        try:
            r = requests.get(logo, headers=head, timeout=15)
            ext = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}.get(r.headers.get("content-type", "").split(";")[0].strip())
            if r.ok and ext and 200 < len(r.content) < 20e6:
                os.makedirs(ASSETS, exist_ok=True)
                for old in os.listdir(ASSETS):
                    if old.startswith("logo."):
                        os.remove(os.path.join(ASSETS, old))
                dst = os.path.join(ASSETS, "logo" + ext)
                open(dst, "wb").write(r.content)
                b = brand(); b["logo"] = dst
                json.dump(b, open(BRAND_FILE, "w"), indent=1)
                has_logo = True
        except requests.RequestException:
            pass
    title = re.search(r"<title[^>]*>(.*?)</title>", doc, re.S | re.I)
    name = meta("og:site_name") or (re.split(r"\s[|\-:\\]\s", H.unescape(title.group(1)).strip())[-1 if "\\" in title.group(1) else 0] if title else "")
    return {"name": name[:60], "accent": "#" + accent if accent else "", "font": font, "logo": has_logo}


def brand_from_video(path, work):
    """Look at 8 frames of a video in the style the person wants and suggest their brand."""
    d = float(probe(path, count=False)["format"]["duration"])
    frames = []
    for k in range(8):
        f = os.path.join(work, f"f{k}.jpg")
        subprocess.run([FF, "-v", "error", "-ss", f"{d * (0.05 + 0.9 * k / 7):.2f}", "-i", path, "-frames:v", "1",
                        "-vf", "scale=360:640:force_original_aspect_ratio=decrease,pad=360:640:(ow-iw)/2:(oh-ih)/2", "-y", f],
                       capture_output=True)
        if os.path.exists(f):
            frames.append(f)
    if len(frames) < 4:
        raise RuntimeError("Couldn't read frames from that video. Try an .mp4 or .mov.")
    grid = os.path.join(work, "grid.jpg")
    subprocess.run([FF, "-v", "error", *sum([["-i", f] for f in frames], []), "-filter_complex",
                    "".join(f"[{i}:v]" for i in range(len(frames))) + f"xstack=inputs={len(frames)}:layout=" +
                    "|".join(f"{(i % 4) * 360}_{(i // 4) * 640}" for i in range(len(frames))) + ":fill=black",
                    "-y", grid], capture_output=True)
    big = []
    for k in range(4):
        f = os.path.join(work, f"big{k}.png")
        subprocess.run([FF, "-v", "error", "-ss", f"{d * (0.1 + 0.8 * k / 3):.2f}", "-i", path, "-frames:v", "1",
                        "-vf", "scale=1080:-2", "-y", f], capture_output=True)
        if os.path.exists(f):
            big.append(f)
    measured, n_lines = match_font(big)
    sheet = os.path.join(work, "fonts.jpg")
    font_sheet(sheet)
    both = os.path.join(work, "both.jpg")
    subprocess.run([FF, "-v", "error", "-i", grid, "-i", sheet, "-filter_complex", "[0:v]pad=1440:ih[a];[a][1:v]vstack", "-y", both],
                   capture_output=True)
    fonts = "; ".join(f"{k} ({v})" for k, v in FONT_LOOKS.items())
    got = {} if not key("GROQ_API_KEY") else ask_vision(BRAND_ASK.format(fonts=fonts) + "\nThe TOP of the picture is 8 frames of the video. The BOTTOM strip shows a "
                     "sample of each font option with its name in yellow on the left. Compare letter shapes to pick the fonts.", both)
    pick = lambda name: name if name in FONTS else next((k for k in FONTS if k.lower() in str(name).lower()), "Bold Caps")
    accent, seen = true_color(frames, str(got.get("accent", "#FFFFFF")))   # no answer = "none found", never a made-up blue
    return {"font": measured or pick(got.get("hook_font")), "font_measured_lines": n_lines,
            "caption_font": pick(got.get("caption_font")), "accent": accent, "accent_pixels": seen, "text_color": str(got.get("text_color", "#FFFFFF")), "all_caps": bool(got.get("all_caps")),
            "notes": str(got.get("notes", ""))[:200]}


# ---------------------------------------------------------------- IG Reels Copycat

STYLES = os.path.join(JOBS, "_styles")
REEL_ASK = """These are 8 frames from one short vertical video. Describe its EDITING STYLE, not its topic.
"accent" is the main color used on the text, highlights, bars or emphasized words, as #RRGGBB; say #FFFFFF if the text is only white.
Return ONLY JSON: {"name": "3 to 5 plain words naming the style, like Talking Head With Big Captions",
"layout": one of "close-up talking head", "wide talking head", "split screen", "screen recording", "b-roll montage", "text on screen",
"look": "one short sentence on how the text looks and where it sits", "accent": "#RRGGBB"}"""


def reel_link(text):
    """Pull reel links out of whatever was pasted. A profile page can't be read without signing in."""
    links = re.findall(r"https?://(?:www\.)?(?:instagram\.com/(?:[\w.]+/)?(?:reel|reels|p)/[\w-]+|tiktok\.com/@[\w.]+/video/\d+|"
                       r"(?:youtube\.com/shorts/|youtu\.be/)[\w-]+)", text)
    # a reel saved or screen-recorded on a phone and handed over as a file: no download, so it works even
    # where Instagram won't let a computer in
    links += [l.strip() for l in text.splitlines() if re.search(r"\.(mp4|mov|m4v)$", l.strip(), re.I) and os.path.isfile(l.strip())]
    seen = []
    for l in links:
        if l not in seen:
            seen.append(l)
    return seen[:10]


def chrome():
    for p in ("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
              os.path.join(HOME, "Applications/Google Chrome.app/Contents/MacOS/Google Chrome")):
        if os.path.exists(p):
            return p
    import glob
    hs = glob.glob(os.path.join(HOME, ".claude-video-fx/.remotion/chrome-headless-shell/*/*/chrome-headless-shell"))
    return hs[0] if hs else None


def profile_reels(text, top=4):
    """A creator's page, read the way a visitor sees it: Chrome in the background with a fresh, empty profile
    (never the person's own logins). Returns their most watched reel links. Instagram's data API wants a
    sign-in (401, 2026-10-26), but the public page lists every reel with its view count."""
    import html as H
    m = re.search(r"instagram\.com/([A-Za-z0-9_.]+)/?", text)
    if not m or m.group(1) in ("reel", "reels", "p", "explore", "stories"):
        return []
    handle = m.group(1)
    exe = chrome()
    if not exe:
        raise RuntimeError("Google Chrome is needed to read a creator's page. Install it from google.com/chrome.")
    prof = tempfile.mkdtemp(prefix="igpage_")
    try:
        r = subprocess.run([exe, "--headless=new", "--disable-gpu", "--no-first-run", f"--user-data-dir={prof}",
                            "--virtual-time-budget=9000", "--window-size=1280,2000",
                            "--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
                            "--dump-dom", f"https://www.instagram.com/{handle}/reels/"], capture_output=True, text=True, timeout=60)
    finally:
        shutil.rmtree(prof, ignore_errors=True)
    found = []
    for a in re.finditer(r'<a[^>]+href="(/[\w.]+/reel/[\w-]+)/?"[^>]*>(.*?)</a>', r.stdout, re.S):
        txt = H.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", a.group(2))))
        v = re.search(r"View Count Icon\s*([\d.,]+)\s*([KM]?)", txt)
        views = 0.0
        if v:
            views = float(v.group(1).replace(",", "")) * {"K": 1e3, "M": 1e6}.get(v.group(2), 1)
        url = "https://www.instagram.com" + a.group(1)
        if url not in [f[0] for f in found]:
            found.append((url, views))
    found.sort(key=lambda f: -f[1])
    return [f[0] for f in found[:top]]


def fetch_reel(url, dst):
    if os.path.isfile(url):      # a reel they saved and handed over themselves
        shutil.copy(url, dst)
        return
    ytdlp = shutil.which("yt-dlp") or os.path.join(BIN, "yt-dlp")
    r = subprocess.run([ytdlp, "-q", "--no-warnings", "--no-playlist", "-f", "b[height<=1080]/bv*[height<=1080]+ba/b",
                        "--merge-output-format", "mp4", "-o", dst, url], capture_output=True, text=True, timeout=300)
    if r.returncode or not os.path.exists(dst):
        raise RuntimeError(f"Couldn't download {url} ({(r.stderr or '').strip().splitlines()[-1][:120] if r.stderr else 'no file'})")


def study_reel(path, work):
    """Measure one reel: cuts, where the text sits and how big, caps, words per line, font, color, framing."""
    import cv2, numpy as np
    info = probe(path, count=False)
    d = float(info["format"]["duration"])
    # cuts: ffmpeg's scene score above 0.3
    r = subprocess.run([FF, "-v", "info", "-i", path, "-vf", "scale=180:-2,select='gt(scene,0.3)',showinfo", "-an", "-f", "null", "-"],
                       capture_output=True, text=True)
    cuts = len(re.findall(r"pts_time", r.stderr))
    frames = []
    for k in range(8):
        f = os.path.join(work, f"s{k}.png")
        subprocess.run([FF, "-v", "error", "-ss", f"{d * (0.06 + 0.88 * k / 7):.2f}", "-i", path, "-frames:v", "1",
                        "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2", "-y", f],
                       capture_output=True)
        if os.path.exists(f):
            frames.append(f)
    ocr = ocr_cmd()
    seen, lines = {}, []
    for f in frames:
        try:
            found = json.loads(subprocess.run([*ocr, f], capture_output=True, text=True, timeout=60).stdout or "[]")
        except Exception:
            found = []
        for o in found:
            t = o["text"].strip()
            if o["conf"] < 0.6 or len(t) < 3 or o["h"] < 0.022:      # smaller is app or screen text, not captions
                continue
            o["text"] = t
            lines.append(o)
            seen[t.lower()] = seen.get(t.lower(), 0) + 1
    headline = [o for o in lines if seen[o["text"].lower()] >= 3 and len(o["text"].split()) >= 2]   # same words on 3+ frames
    caps_lines = [o for o in lines if o not in headline]
    cy = lambda o: o["y"] + o["h"] / 2
    faces = []
    det = None
    for f in frames:
        img = cv2.imread(f)
        if det is None:
            det = cv2.FaceDetectorYN.create(YUNET, "", (img.shape[1], img.shape[0]), 0.6)
        _, fc = det.detect(img)
        faces.append(0 if fc is None else max(b[3] for b in fc) / img.shape[0])
    sheet = os.path.join(work, "grid.jpg")
    subprocess.run([FF, "-v", "error", *sum([["-i", f] for f in frames], []), "-filter_complex",
                    "".join(f"[{i}:v]scale=270:480[v{i}];" for i in range(len(frames))) +
                    "".join(f"[v{i}]" for i in range(len(frames))) + f"xstack=inputs={len(frames)}:layout=" +
                    "|".join(f"{(i % 4) * 270}_{(i // 4) * 480}" for i in range(len(frames))), "-y", sheet], capture_output=True)
    try:
        look = ask_vision(REEL_ASK, sheet)
    except Exception:
        look = {}
    font, _ = match_font(frames, "captions" if caps_lines else "top")
    hook_font = match_font(frames, "top")[0] if headline else None
    accent, _ = true_color(frames, str(look.get("accent", "#FFFFFF"))) if lines else ("#FFFFFF", 0)
    words = [len(o["text"].split()) for o in caps_lines]
    return {
        "seconds": round(d, 1), "cut_every": round(d / (cuts + 1), 1),
        "headline": bool(headline), "headline_top": round(float(np.median([o["y"] for o in headline])), 3) if headline else None,
        "headline_text": headline[0]["text"] if headline else "",
        "captions": len(caps_lines) >= 3,
        "caption_y": round(float(np.median([cy(o) for o in caps_lines])), 3) if caps_lines else 0.5,
        "caption_h": round(float(np.median([o["h"] for o in caps_lines])), 4) if caps_lines else 0.045,
        "caps": bool(caps_lines) and sum(o["text"].isupper() for o in caps_lines) >= 0.6 * len(caps_lines),
        "words_per_line": int(round(float(np.median(words)))) if words else 3,
        "font": font or "Simple", "hook_font": hook_font or font or "Bold Caps", "accent": accent,
        "face": round(float(np.median(faces)), 3),
        "name": str(look.get("name") or measured_name(faces, headline, words))[:40], "layout": str(look.get("layout", "")),
        "look": str(look.get("look", ""))[:160],
    }


CTA_RE = re.compile(r"\b(follow(ing)?|comment|link in (my )?bio|dm me|subscribe|save (this|it)|share (this|it)|download|"
                    r"free (guide|training|class)|join|sign up|book (a|your) call|shop|use code|grab)\b|@[\w.]+|https?://|"
                    r"\b[\w-]+\.(com|io|ai|co|app|net|org)\b|\$\s?\d", re.I)
PRICE_RE = re.compile(r"\$\s?\d")


def study_moves(path, work, handle=""):
    """Read the EDIT off the reel itself, 2 frames a second (2026-10-27, Tiff: "make the IG reels copy cat
    actually work ... use the edits"). Every cut with its time and what it did to the framing (punch in,
    punch out, a switch to two people), every punch-in inside a shot, and every piece of text that STAYS on
    screen: the headline, labels, a call to action, an end card, with when and where it sits.
    Text that names the creator (their handle, a link, a price, a follow/comment ask) is marked theirs:
    it is never put on anyone else's video, the person is asked what goes there instead."""
    import cv2, numpy as np
    from concurrent.futures import ThreadPoolExecutor
    d = float(probe(path, count=False)["format"]["duration"])
    r = subprocess.run([FF, "-v", "info", "-i", path, "-vf", "scale=180:-2,select='gt(scene,0.3)',showinfo", "-an", "-f", "null", "-"],
                       capture_output=True, text=True)
    cut_t = [round(float(x), 2) for x in re.findall(r"pts_time:([\d.]+)", r.stderr) if 0.3 < float(x) < d - 0.3]
    fdir = os.path.join(work, "m")
    os.makedirs(fdir, exist_ok=True)
    subprocess.run([FF, "-v", "error", "-i", path, "-vf", "fps=2,scale=1080:1920:force_original_aspect_ratio=decrease,"
                    "pad=1080:1920:(ow-iw)/2:(oh-ih)/2", "-q:v", "3", os.path.join(fdir, "%04d.jpg")], capture_output=True)
    files = sorted(os.listdir(fdir))
    ts = [i * 0.5 for i in range(len(files))]
    ocr = ocr_cmd()

    def read(f):
        try:
            return json.loads(subprocess.run([*ocr, os.path.join(fdir, f)], capture_output=True, text=True, timeout=60).stdout or "[]")
        except Exception:
            return []
    with ThreadPoolExecutor(4) as ex:
        texts = list(ex.map(read, files))
    det, faces = None, []
    for f in files:
        img = cv2.imread(os.path.join(fdir, f))
        if det is None:
            det = cv2.FaceDetectorYN.create(YUNET, "", (img.shape[1], img.shape[0]), 0.6)
        _, fc = det.detect(img)
        fc = [] if fc is None else [b for b in fc if b[3] > 0.05 * img.shape[0]]
        faces.append({"n": len(fc), "h": max((b[3] for b in fc), default=0) / img.shape[0],
                      "y": (max(fc, key=lambda b: b[3])[1] + max(fc, key=lambda b: b[3])[3] / 2) / img.shape[0] if fc else 0.4})
    shutil.rmtree(fdir, ignore_errors=True)

    # framing: what each cut did, and punch-ins inside one shot
    def shot_face(a, b):
        hs = [faces[k]["h"] for k in range(len(ts)) if a <= ts[k] < b and faces[k]["h"]]
        ns = [faces[k]["n"] for k in range(len(ts)) if a <= ts[k] < b]
        return (float(np.median(hs)) if hs else 0.0), (max(set(ns), key=ns.count) if ns else 0)
    bounds = [0.0] + cut_t + [d]
    cuts, ratios = [], []
    for i, t in enumerate(cut_t):
        (h0, n0), (h1, n1) = shot_face(bounds[i], t), shot_face(t, bounds[i + 2])
        kind = "cut"
        if n0 != n1 and max(n0, n1) >= 2:
            kind = "two people" if n1 >= 2 else "back to one person"
        elif h0 and h1 and h1 / h0 > 1.12:
            kind = "punch in"
        elif h0 and h1 and h0 / h1 > 1.12:
            kind = "punch out"
        if h0 and h1:
            ratios.append(max(h0, h1) / min(h0, h1))
        cuts.append({"t": t, "kind": kind})
    for k in range(1, len(ts)):
        a, b = faces[k - 1]["h"], faces[k]["h"]
        if a and b and faces[k]["n"] == faces[k - 1]["n"] and not any(abs(ts[k] - c) < 0.75 for c in cut_t) and max(a, b) / min(a, b) > 1.15:
            cuts.append({"t": ts[k], "kind": "punch in" if b > a else "punch out"})
            ratios.append(max(a, b) / min(a, b))
    cuts.sort(key=lambda c: c["t"])

    # text that stays on screen: the same words at about the same height on 2+ frames in a row
    key_ = lambda s: re.sub(r"[^a-z0-9$@.]", "", s.lower())
    runs = []
    for k, found in enumerate(texts):
        for o in found:
            t = o["text"].strip()
            if o["conf"] < 0.5 or len(key_(t)) < 2:
                continue
            # 2026-10-30: words inside an app window or a thumbnail on screen are tiny ("0:08 Other",
            # "TRENDING AUDIO"); the creator's own words are big. Tiny text only counts when it names someone
            # or asks for something (a handle, a link, "comment", "follow").
            if o["h"] < 0.022 and not (CTA_RE.search(t) and not PRICE_RE.search(t)) and not (handle and handle.lower() in key_(t)):
                continue
            hit = next((r_ for r_ in runs if r_["key"] == key_(t) and abs(r_["y"] - o["y"]) < 0.03 and k - r_["last"] <= 2), None)
            if hit:
                hit.update(last=k, n=hit["n"] + 1)
            else:
                runs.append({"key": key_(t), "text": t, "y": o["y"], "h": o["h"], "first": k, "last": k, "n": 1})
    hold = [r_ for r_ in runs if r_["n"] >= 3 or (r_["n"] >= 2 and (CTA_RE.search(r_["text"]) or (handle and handle.lower() in r_["key"])))]
    blocks = []
    for r_ in sorted(hold, key=lambda r_: (r_["first"], r_["y"])):       # lines shown together are one block
        b = next((b for b in blocks if abs(b["first"] - r_["first"]) <= 2 and abs(b["last"] - r_["last"]) <= 2
                  and abs(b["y1"] - r_["y"]) < 0.07), None)
        if b:
            b["lines"].append(r_["text"]); b["y1"] = max(b["y1"], r_["y"] + r_["h"])
        else:
            blocks.append({"first": r_["first"], "last": r_["last"], "y": r_["y"], "y1": r_["y"] + r_["h"], "lines": [r_["text"]]})
    text = []
    for b in blocks:
        s, e = ts[b["first"]], min(d, ts[b["last"]] + 0.5)
        words = " ".join(b["lines"])
        names = bool(re.search(r"@[\w.]+|https?://|\b[\w-]+\.(com|io|ai|co|app)\b|\bfollow", words, re.I)
                     or (handle and handle.lower() in key_(words)))
        asks = bool(re.search(r"\b(comment|dm|link in (my )?bio|subscribe)\b", words, re.I))
        if len(words.split()) <= 2 and not names and not asks:
            continue          # a caption word that sat still for a second ("$8K", "70K"), not a text box
        theirs = names or bool(CTA_RE.search(words))
        kind = ("end card" if s >= 0.85 * d and e >= d - 1.0 else "headline" if s <= 1.0 and not names else
                "call to action" if theirs else "label")
        theirs = theirs and kind != "headline"      # their headline is always swapped for one in the person's own words
        text.append({"kind": kind, "start": round(s, 2), "end": round(e, 2), "y": round(b["y"], 3), "lines": b["lines"],
                     "theirs": theirs or kind == "end card", "follow": bool(re.search(r"\bfollow", words, re.I))})
    two = sum(1 for f in faces if f["n"] >= 2) >= 0.25 * len(faces)
    text = merge_text(text)
    return {"seconds": round(d, 1), "cuts": cuts, "text": text, "two_people": two,
            "zoom": round(float(min(1.35, max(1.18, np.median(ratios)))) if ratios else 1.2, 2)}


def merge_text(text):
    """A banner pinned on screen for the whole reel ("COMMENT NYC TO LOCK IN") reads as dozens of short pieces,
    because the reader drops a frame here and there and misreads a letter (2026-10-30: 28 pieces). Pieces of
    the same kind at the same height with under 2 seconds between them are one piece."""
    import difflib
    out = []
    for x in sorted(text, key=lambda x: x["start"]):
        prev = next((o for o in reversed(out) if o["kind"] in (x["kind"], "end card") and abs(o["y"] - x["y"]) < 0.04
                     and x["start"] - o["end"] <= 2.0 and (o["theirs"] == x["theirs"])
                     and difflib.SequenceMatcher(None, " ".join(o["lines"]).lower(), " ".join(x["lines"]).lower()).ratio() > 0.5), None)
        if prev:
            prev["end"] = max(prev["end"], x["end"])
            if x["kind"] == "end card":
                prev["kind"] = "end card"
        else:
            out.append(dict(x))
    return out


def ask_list(moves):
    """What the person has to answer before their video is made: one question per thing that belongs to
    the creator. Their words are shown so the person knows what it is, and never offered as the answer."""
    out = []
    for i, x in enumerate(moves.get("text", [])):
        if not x["theirs"]:
            continue
        at = f"{x['start']:.0f} s" if x["kind"] != "end card" else "the end"
        what = {"end card": "an end card", "call to action": "a follow button" if x["follow"] else "a call to action"}.get(x["kind"], "text")
        q = (f"At {at} they show {what} that's theirs (\"{' / '.join(x['lines'])[:60]}\"). What should yours say?")
        hint = "Your handle, like @yourname" if x["follow"] else "Your call to action, like Comment GUIDE and I'll send it"
        out.append({"id": f"t{i}", "q": q, "hint": hint, "kind": x["kind"], "theirs": " ".join(x["lines"])})
    return out


def edit_plan(moves, length, answers):
    """Lay the reel's moves onto a video `length` seconds long: the same rhythm of cuts (as jump-zooms on
    one take), the headline for as long as theirs stays up, and the person's own call to action where
    theirs pops up. Returns (zooms [[t, z]], hook_until or None, ctas [{start, end, y, text, button}])."""
    zooms, d = [], max(1.0, moves.get("seconds", 1.0))
    times = [c["t"] for c in moves.get("cuts", [])]
    gaps = [b - a for a, b in zip([0.0] + times, times + [d]) if b - a >= 1.2] or ([] if not times else [d / (len(times) + 1)])
    z, t, i, tight = moves.get("zoom", 1.2), 0.0, 0, False
    kinds = [c["kind"] for c in moves.get("cuts", [])]
    while gaps and t + gaps[i % len(gaps)] < length - 1.0:      # their rhythm, repeated over the whole video
        t += gaps[i % len(gaps)]
        k = kinds[i % len(kinds)] if kinds else "cut"
        want = True if k in ("punch in", "back to one person") else False if k in ("punch out", "two people") else not tight
        tight = want if want != tight else not tight       # one person on screen: every cut has to show
        zooms.append([round(t, 2), z if tight else 1.0])
        i += 1
    head = next((x for x in moves.get("text", []) if x["kind"] == "headline"), None)
    ctas = []
    for k, x in enumerate(moves.get("text", [])):
        txt = (answers.get(f"t{k}") or "").strip()
        if not x["theirs"] or not txt:
            continue
        dur = min(4.0, max(2.0, x["end"] - x["start"]))
        s = length - dur if x["kind"] == "end card" else min(length - dur, x["start"] / d * length)
        ctas.append({"start": round(max(0.0, s), 2), "end": round(min(length, s + dur), 2), "y": x["y"], "text": txt[:40],
                     "button": "Follow" if x["follow"] else ""})
    keep = []           # never more than 3 pop-ups, never two on screen at once
    for c in sorted(ctas, key=lambda c: c["start"]):
        if not keep or c["start"] >= keep[-1]["end"] + 1.0:
            keep.append(c)
    if len(keep) > 3:
        keep = [keep[0], keep[len(keep) // 2], keep[-1]]
    ctas = keep
    return zooms, (round(head["end"], 2) if head else None), ctas


def move_traits(moves, settings):
    """What gets copied and with which of your effects, in plain words for the card."""
    out = []
    cuts = moves.get("cuts", [])
    if cuts:
        kinds = {c["kind"] for c in cuts}
        out.append(f"{len(cuts)} cuts in {moves['seconds']:.0f} s ({', '.join(sorted(kinds))}): copied as jump-zooms "
                   f"on your video at the same rhythm, {moves['zoom']:.2f}x in")
    head = next((x for x in moves.get("text", []) if x["kind"] == "headline"), None)
    if head:
        out.append(f"Headline for the first {head['end']:.0f} s: yours, from your own words")
    for x in moves.get("text", []):
        if x["theirs"]:
            out.append(f"Their {'follow button' if x['follow'] else x['kind']} at {x['start']:.0f} s: your own, with your Call To Action Pop")
    labels = [x for x in moves.get("text", []) if x["kind"] == "label"]
    if labels:
        out.append(f"{len(labels)} extra text label(s) mid-video: not copied, your captions carry the words")
    if moves.get("two_people"):
        out.append("Two people stacked on screen: not copied (your video has one person); the switches become zooms")
    return out


def measured_name(faces, headline, words):
    """A plain name built from the measurements, for when the picture reader is out for the day."""
    import numpy as np
    n = int(round(float(np.median(words)))) if words else 0
    parts = ["Close-Up" if faces and float(np.median(faces)) >= 0.18 else "Wide Shot"]
    if headline:
        parts.append("With Headline")
    parts.append(f"{n}-Word Captions" if n else "No Captions")
    return " ".join(parts)


def group_styles(reels):
    """One creator is often several styles. Reels with the same framing, headline and caption spot are one style."""
    groups = {}
    for r in reels:
        zone = "top" if r["caption_y"] < 0.33 else "middle" if r["caption_y"] < 0.66 else "bottom"
        words = "1" if r["words_per_line"] <= 1 else "2-3" if r["words_per_line"] <= 3 else "4+"
        key = (r["face"] >= 0.18, r["headline"], zone if r["captions"] else "none", words)
        groups.setdefault(key, []).append(r)
    styles = []
    for i, (key, rs) in enumerate(sorted(groups.items(), key=lambda kv: -len(kv[1]))):
        base = dict(rs[0])
        fonts = [x["font"] for x in rs]
        base["font"] = max(set(fonts), key=fonts.count)      # the font most of these reels share
        styles.append({"id": f"s{i + 1}", "name": base["name"], "layout": base["layout"], "reels": [x["reel"] for x in rs], "count": len(rs),
                       "refs": sum((x.get("refs", []) for x in rs), [])[:8],
                       "preview": base["preview"], "thumb": base["thumb"], "look": base["look"],
                       "moves": base.get("moves", {}), "ask": ask_list(base.get("moves", {})),
                       "settings": {k: base.get(k) for k in ("headline", "headline_top", "captions", "caption_y", "caption_h",
                                                             "caps", "words_per_line", "font", "hook_font", "accent", "face", "cut_every", "headline_until")}})
    return styles


STYLE_LIB = os.path.join(ASSETS, "styles")     # inside brand-assets, so an update never removes them


STARTER_DIR = os.path.join(HERE, "starter-styles")   # Tiff's 6 styles, shipped in the member copy only


def style_dir(sid):
    """Where a style's preview lives: the person's own library first, then the starter styles."""
    return STYLE_LIB if os.path.exists(os.path.join(STYLE_LIB, sid + ".mp4")) else STARTER_DIR


def saved_styles():
    """2026-10-31, Tiff: her 6 saved styles go to members too. A member gets them as starter styles, in their own
    brand color, and anything they save themselves sits next to them."""
    own = [x for x in brand().get("saved_styles", []) if os.path.exists(os.path.join(STYLE_LIB, x["id"] + ".mp4"))]
    seen = {x["id"] for x in own}
    starters = []
    try:
        for x in json.load(open(os.path.join(STARTER_DIR, "styles.json"))):
            if x["id"] not in seen and os.path.exists(os.path.join(STARTER_DIR, x["id"] + ".mp4")):
                x["settings"]["accent"] = brand().get("accent") or x["settings"]["accent"]
                starters.append(x)
    except (OSError, ValueError, KeyError):
        pass
    return starters + own


def save_styles(src_job, picks, source):
    """2026-10-30, Tiff: "grab all of your videos and then pinpoint whatever your 5 or 6 are, name them, and add
    them to your effects library under your own". Each picked style becomes an effect under Yours: its own
    name, a short preview, and everything needed to put it on any video. What belonged to the creator (their
    handle, their call to action, their words) is not kept as text to use; their call-to-action spots get the
    person's own call to action from their brand settings."""
    b = brand()
    lib = {x["id"]: x for x in b.get("saved_styles", [])}
    os.makedirs(STYLE_LIB, exist_ok=True)
    out = []
    for st in src_job.styles:
        if st["id"] not in picks:
            continue
        name = re.sub(r"[^\w &'+-]", "", str(picks[st["id"]] or st["name"])).strip()[:40] or st["name"]
        sid = "style-" + (re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40] or uuid.uuid4().hex[:6])
        for ext, f in ((".mp4", st["preview"]), (".jpg", st["thumb"])):
            srcf = os.path.join(src_job.dir, "out", f)
            if os.path.exists(srcf):
                shutil.copy(srcf, os.path.join(STYLE_LIB, sid + ext))
        uses = (st.get("copies") or [])[:2] + st.get("traits", [])[:3]
        moves = dict(st.get("moves") or {})
        moves["text"] = merge_text(moves.get("text", []))      # styles studied before the merge rule get it here
        lib[sid] = {"id": sid, "name": name, "uses": [f"Saved from {source}"[:80]] + uses, "settings": st["settings"],
                    "moves": moves, "saved": time.strftime("%Y-%m-%d")}
        out.append(lib[sid])
    b["saved_styles"] = list(lib.values())
    json.dump(b, open(BRAND_FILE, "w"), indent=1)
    return out


HOOK_ASK = """Below are the words of a short talking video. Write a 2-line headline for the top of the screen using
ONLY the speaker's own words (copy them, never invent). Each line 1 to 3 words, at most 20 characters, the most
scroll-stopping idea they say. Return ONLY JSON: {"hook": ["LINE ONE", "LINE TWO"]}
Words:
"""


def run_saved_style(job, style_id, opts):
    """A saved style on any video: clean sound, pauses cut, then the style's captions, framing, headline and the
    creator's cut rhythm as jump-zooms, with the person's own call to action where the creator had theirs."""
    st = next(x for x in saved_styles() if x["id"] == style_id)
    tight, tlen, tw = prepare_talking(job, opts or {})
    settings, moves = dict(st["settings"]), st.get("moves") or {}
    settings.update(accent=brand()["accent"], font=brand()["font"], hook_font=brand()["font"])
    sr = style_render(settings)
    hook_lines = ["", ""]
    if not sr["no_hook"]:
        job.state = "writing your headline from your own words"
        try:
            h = ask_groq(HOOK_ASK + " ".join(w["word"].strip() for w in tw)[:6000]).get("hook") or []
        except Exception:
            h = []
        words = [w["word"].strip() for w in tw]
        hook_lines = [safe_hook(x) for x in (h + [" ".join(words[:3]), " ".join(words[3:6])])[:2]]
        typed = [x.strip() for x in str((opts or {}).get("words") or "").split("\n") if x.strip()][:2]
        if typed:
            hook_lines = [safe_hook(x) for x in typed] + [""] * (2 - len(typed))
    cta = (brand().get("cta") or "").strip()
    answers = {q["id"]: cta for q in ask_list(moves)} if cta else {}
    zooms, until, ctas = edit_plan(moves, tlen, answers)
    if until and not sr["no_hook"]:
        for c in ctas:
            if c["start"] < until:
                c["end"] = round(min(tlen, c["end"] + until - c["start"]), 2)
                c["start"] = round(until, 2)
    cy_ = settings.get("caption_y", 0.5)
    for c in ctas:
        if -0.08 < cy_ - c["y"] < 0.1:
            c["y"] = round(max(0.1, cy_ - 0.12), 3)
    mf = os.path.join(job.dir, "moves.json")
    json.dump({"zooms": zooms, "hook_until": until}, open(mf, "w"))
    job.say(f"{st['name']}: {len(zooms)} jump-zooms at their rhythm" + (f", headline for {until:.1f} s" if until else "")
            + (f", your call to action \"{cta}\" {len(ctas)} time(s)" if ctas else
               ("" if not ask_list(moves) else ", no call to action (add yours in Your brand to put one where they had theirs)")))
    job.state = f"putting {st['name']} on your video"
    name = re.sub(r"[^\w &-]", "", os.path.splitext(job.name)[0]).strip()[:50]
    out = os.path.join(job.dir, "out", f"{name} - {st['name']}.mp4")
    os.environ["CME_HOOK"] = st.get("hook_style", "")
    r = subprocess.run([VENV_PY, FINISHER, tight, out, "--hook", *[h or " " for h in hook_lines], "--layout", sr["layout"],
                        "--preset", sr["preset"], "--font", sr["font"], "--accent", sr["accent"],
                        *(["--no-hook"] if sr["no_hook"] else []), *(["--caps"] if sr["caps"] else []),
                        "--hook-top", str(sr["hook_top"]), "--moves", mf], capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(f"{st['name']} didn't render: {(r.stderr or r.stdout)[-300:]}")
    rep = json.loads(r.stdout[r.stdout.index("{"):])
    shutil.rmtree(rep.get("work", ""), ignore_errors=True)
    if st.get("post") == "glass-meter":
        job.state = f"adding {st['name']}"
        layered = out[:-4] + ".glass.mp4"
        mine = [x.strip() for x in re.split(r"[\n,]", str((opts or {}).get("words") or "")) if x.strip()]
        marks = pop_words(tw, tlen)
        if mine:
            marks = [{"w": m[:18], "t": marks[i % max(1, len(marks))]["t"] if marks else 0.0} for i, m in enumerate(mine)]
            marks.sort(key=lambda x: x["t"])
        rr = subprocess.run([VENV_PY, MYFX, "glass-meter", out, layered, "--start", "0", "--end", f"{tlen:.3f}", "--config",
                             json.dumps({"accent": "#" + brand()["accent"], "font": brand_files(brand())[1], "words": marks})], capture_output=True, text=True)
        if rr.returncode or not os.path.exists(layered):
            raise RuntimeError(f"{st['name']} didn't render: " + (rr.stderr or rr.stdout)[-200:])
        os.replace(layered, out)
    for c in ctas:
        tmp = out[:-4] + ".cta.mp4"
        rc = subprocess.run([VENV_PY, MYFX, "cta-pop", out, tmp, "--start", f"{c['start']:.2f}", "--end", f"{c['end']:.2f}",
                             "--config", json.dumps({"accent": "#" + sr["accent"], "font": sr["font"], **c})], capture_output=True, text=True)
        if rc.returncode or not os.path.exists(tmp):
            raise RuntimeError("Your call to action didn't render: " + (rc.stderr or rc.stdout).strip()[-200:])
        os.replace(tmp, out)
    brand_finish(job, out)
    ok, checks = ledger(out, "1080x1920", tlen)
    import difflib
    nrm = lambda x: [FIX_WORDS.get(y, y) for y in re.sub(r"[^a-z0-9 ]", " ", x.lower()).split()]
    match = round(100 * difflib.SequenceMatcher(None, nrm(" ".join(w["word"] for w in tw)), nrm(rep.get("captions", ""))).ratio())
    checks["captions match the words"] = [f"{match}%", ">= 80%", match >= 80]
    checks["their edit copied (jump-zooms, your call to action)"] = [f"{rep.get('zooms', 0)} zooms, {len(ctas)} CTA", "as planned", True]
    ok = ok and match >= 80
    sheet = out[:-4] + " frames.jpg"
    contact_sheet(out, sheet)
    for f in (tight, mf):
        if os.path.exists(f):
            os.remove(f)
    job.shorts.append({"file": os.path.basename(out), "sheet": os.path.basename(sheet), "ok": ok, "seconds": round(tlen, 1),
                       "from": "0:00", "hook": hook_lines if not sr["no_hook"] else [],
                       "why": f"Your saved style {st['name']}: pauses cut, sound cleaned, their edit with your words.", "checks": checks})
    job.say(f"{st['name']} {'PASSED' if ok else 'FAILED'} the checks")
    job.save()


def plain_traits(st):
    """The style in words a person can read on the card."""
    s = st["settings"]
    out = []
    out.append("Close-up on the face" if s["face"] >= 0.18 else "Whole picture, not zoomed in")
    out.append("One long take, no cuts" if s["cut_every"] >= 20 else f"A cut about every {s['cut_every']:g} seconds")
    out.append((f"Headline for the first {s['headline_until']:.0f} s" if s.get("headline_until") else "Headline stays on top")
               if s["headline"] else "No headline on top")
    if s["captions"]:
        zone = "top" if s["caption_y"] < 0.33 else "middle" if s["caption_y"] < 0.66 else "bottom"
        n = s["words_per_line"]
        out.append(f"Captions in the {zone}, {'1 word' if n == 1 else f'{n} words'} at a time{', ALL CAPS' if s['caps'] else ''}")
    else:
        out.append("No word-by-word captions")
    out.append(f"{s['font']} style font" + (f" (headline in {s['hook_font']})" if s.get("headline") and s.get("hook_font") and s["hook_font"] != s["font"] else "")
               + (f", color {s['accent']}" if s["accent"].upper() != "#FFFFFF" else ", white text"))
    return out


def kit_one_word_fix():
    """The kit's caption tool glues single words onto their neighbors, so a 1-word style can't happen.
    Same one-line fix as on Tiff's Mac (2026-10-26): keep single words when the preset asks for 1 per screen.
    Saves the original next to it first. Does nothing if already fixed."""
    p = os.path.join(CAPTIONS, "scripts", "generate_spice.py")
    try:
        s = open(p).read()
    except OSError:
        return
    old = "    if len(chunks) > 1:\n        merged = []"
    if old in s and s.count(old) == 1:
        shutil.copy(p, p + ".before-dashboard")
        open(p, "w").write(s.replace(old, "    if len(chunks) > 1 and MAXW > 1:\n        merged = []", 1))


def style_render(settings):
    """Turn a copied style into the finisher's settings: a caption preset, a hook font, and switches."""
    from PIL import ImageFont
    if settings.get("words_per_line", 3) <= 1:
        kit_one_word_fix()
    ensure_simple_font()
    p = json.load(open(os.path.join(CAPTIONS, "presets/spice.json")))
    font_file = ALL_FONTS.get(settings["font"], FONTS["Simple"])
    fam, sty = ImageFont.truetype(os.path.join(CAPTIONS, "fonts", font_file), 20).getname()
    # the caption burner picks fonts by name; a family name alone ("Montserrat") picks the regular weight
    fam = fam if sty in ("Regular", "Book", "") else f"{fam} {sty}"
    d = os.path.join(CAPTIONS, "fonts", "dashboard_style")
    os.makedirs(d, exist_ok=True)
    for old in os.listdir(d):
        os.remove(os.path.join(d, old))
    shutil.copy(os.path.join(CAPTIONS, "fonts", font_file), d)
    p["fonts_dir"] = "fonts/dashboard_style"
    p["weights"] = {k: fam for k in p["weights"]}
    # measured 2026-10-26: 218 px in the preset reads as text 0.0352 of the frame tall on screen
    p["font_size_px"] = int(max(150, min(420, settings["caption_h"] * 218 / 0.0352)))
    p["layout"]["y_percent_from_top"] = int(round(100 * min(0.85, max(0.15, settings["caption_y"]))))
    p["layout"]["max_words_per_screen"] = max(1, min(5, settings["words_per_line"]))
    accent = settings["accent"].lstrip("#").upper()
    if accent != "FFFFFF":
        p["number_color"] = accent
        p["colors"]["guest"] = accent
    path = os.path.join(CAPTIONS, "presets", "dashboard_style.json")
    json.dump(p, open(path, "w"), indent=1)
    hook_top = int(1920 * settings["headline_top"]) if settings.get("headline_top") is not None else 150
    hook_file = ALL_FONTS.get(settings.get("hook_font") or settings["font"], FONTS["Bold Caps"])
    return {"preset": path, "font": os.path.join(CAPTIONS, "fonts", hook_file), "accent": accent if accent != "FFFFFF" else brand()["accent"],
            "no_hook": not settings["headline"], "hook_top": max(40, min(1500, hook_top)), "caps": settings["caps"],
            "layout": "face" if settings["face"] >= 0.18 else "full"}


def run_copycat_study(job, text):
    links = reel_link(text)
    if not links and "instagram.com/" in text:
        job.state = "opening their Instagram page"
        links = profile_reels(text, top=10)      # 2026-10-30, Tiff: "grab all of your videos", find their 5 or 6
        if links:
            job.say(f"Found their page. Studying their {len(links)} most watched reels.")
        else:
            raise RuntimeError("Couldn't see any reels on that page. Check the account is public, or paste reel links instead.")
    if not links:
        raise RuntimeError("Paste an Instagram page, or 1 to 10 reel links (Instagram, TikTok or YouTube Shorts), one per line. "
                           "Or hand over the reel itself as a video file.")
    reels = []
    for i, url in enumerate(links, 1):
        job.state = f"studying reel {i} of {len(links)}"
        work = tempfile.mkdtemp(prefix="reel_", dir=job.dir)
        src = os.path.join(work, "reel.mp4")
        try:
            fetch_reel(url, src)
            r = study_reel(src, work)
            if os.path.isfile(url):
                url = os.path.basename(url)      # only the file's name is kept, never where it sat
            hm = re.search(r"instagram\.com/([\w.]+)/(?:reel|reels|p)/|tiktok\.com/@([\w.]+)", url)
            job.state = f"reading the edit of reel {i}, frame by frame"
            r["moves"] = study_moves(src, work, (hm.group(1) or hm.group(2)) if hm else "")
            head = next((x for x in r["moves"]["text"] if x["kind"] == "headline"), None)
            if head and not r["headline"]:      # 8 stills miss a headline that is only up for the first seconds
                r.update(headline=True, headline_top=head["y"])
            if head:
                r["headline_until"] = head["end"]
        except Exception as e:
            job.say(f"   skipped {url}: {e}")
            shutil.rmtree(work, ignore_errors=True)
            continue
        # keep only a short silent preview and one still for the card; their footage is never reused
        prev = os.path.join(job.dir, "out", f"style-preview-{i}.mp4")
        thumb = os.path.join(job.dir, "out", f"style-thumb-{i}.jpg")
        subprocess.run([FF, "-v", "error", "-i", src, "-t", "8", "-an", "-vf", "scale=360:-2", "-c:v", "libx264", "-crf", "28",
                        "-movflags", "+faststart", "-y", prev], capture_output=True)
        shutil.copy(os.path.join(work, "s2.png"), thumb) if os.path.exists(os.path.join(work, "s2.png")) else None
        refs = []
        for k in (1, 3, 5, 7):          # a few real frames, for the AI edit to study when copying every edit
            f = os.path.join(work, f"s{k}.png")
            if os.path.exists(f):
                dst = os.path.join(job.dir, "out", f"style-ref-{i}-{k}.jpg")
                subprocess.run([FF, "-v", "error", "-i", f, "-vf", "scale=540:-2", "-y", dst], capture_output=True)
                refs.append(dst)
        r.update(reel=url, preview=os.path.basename(prev), thumb=os.path.basename(thumb), refs=refs)
        reels.append(r)
        shutil.rmtree(work, ignore_errors=True)
        job.say(f"Studied reel {i}: {r['name']}")
    if not reels:
        raise RuntimeError("None of those reels could be downloaded. Check the links are public reels.")
    styles = group_styles(reels)[:6]       # their 5 or 6 looks, the most used first
    used = set()
    for st in styles:
        n, k = st["name"].strip() or "Their Style", 2
        while n.lower() in used:
            n = f"{st['name']} {k}"; k += 1
        used.add(n.lower()); st["name"] = n
    for st in styles:
        st["traits"] = plain_traits(st)
        st["copies"] = move_traits(st["moves"], st["settings"]) if st.get("moves") else []
    job.styles = styles
    os.makedirs(STYLES, exist_ok=True)
    json.dump({"links": links, "reels": reels, "styles": styles}, open(os.path.join(job.dir, "styles.json"), "w"), indent=1)
    job.say(f"This creator does {len(styles)} type(s) of edit. Pick the one to copy.")


def ensure_simple_font():
    """'Simple' is Inter at SemiBold. The kit ships Inter as a variable font, which draws as Regular,
    so make a fixed SemiBold copy once (2026-10-26: Ajene's captions are this look, none of the others were)."""
    dst = os.path.join(CAPTIONS, "fonts", FONTS["Simple"])
    if os.path.exists(dst):
        return
    try:
        from fontTools.ttLib import TTFont
        from fontTools.varLib import instancer
        f = TTFont(os.path.join(CAPTIONS, "fonts", "Inter.ttf"))
        axes = {a.axisTag for a in f["fvar"].axes}
        instancer.instantiateVariableFont(f, {"wght": 600, **({"opsz": 24} if "opsz" in axes else {})}, updateFontNames=True).save(dst)
    except Exception:
        shutil.copy(os.path.join(CAPTIONS, "fonts", "DMSans.ttf"), dst)


# ---------------------------------------------------------------- AI edits (Claude Code in the background)

SPLIT = os.path.join(HOME, "Split-Screen-Editor")      # the AI Employee Lab Split Screen Editor, set up once
_claude_ok = {"at": 0, "ok": False}


def fast_4k_codec():
    """2026-10-29, Tiff: "I want the quality but without all this time." On a Mac the video chip makes the 4K copy in
    about 19 s where the software encoder took 3 to 5 minutes, at 30 to 35 Mbps (the floor is 8). The bitrate is
    still read back after, so a soft file still fails. Anywhere without the chip, the old software settings."""
    if _VTB.get("ok") is None:
        r = subprocess.run([FF, "-hide_banner", "-encoders"], capture_output=True, text=True)
        _VTB["ok"] = sys.platform == "darwin" and "h264_videotoolbox" in r.stdout
    return (["-c:v", "h264_videotoolbox", "-b:v", "45M", "-maxrate", "60M"] if _VTB["ok"]
            else ["-c:v", "libx264", "-crf", "14", "-preset", "fast"])


_VTB = {}


def claude_cli():
    p = os.path.join(BIN, "claude")
    return p if os.path.exists(p) else shutil.which("claude")


def claude_ready():
    """Is Claude Code signed in for background use? Checked at most once a minute."""
    if time.time() - _claude_ok["at"] < 60:
        return _claude_ok["ok"]
    ok = False
    exe = claude_cli()
    if exe:
        try:
            r = subprocess.run([exe, "auth", "status"], capture_output=True, text=True, timeout=30)
            ok = bool(json.loads(r.stdout or "{}").get("loggedIn"))
        except Exception:
            ok = False
    _claude_ok.update(at=time.time(), ok=ok)
    return ok


def run_agent(job, prompt, cwd, minutes=40):
    """Hand a job to Claude Code in the background, on the person's own plan, inside one project folder.
    Progress lines go to the job log so the timer and log keep moving."""
    exe = claude_cli()
    cmd = [exe, "-p", prompt, "--output-format", "stream-json", "--verbose",
           "--allowedTools", "Bash", "Read", "Write", "Edit", "Glob", "Grep", "TodoWrite"]
    p = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    last, deadline, result = "", time.time() + minutes * 60, ""
    for line in p.stdout:
        if time.time() > deadline:
            p.kill()
            raise RuntimeError(f"The AI edit ran past {minutes} minutes and was stopped.")
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if ev.get("type") == "assistant":
            for c in ev.get("message", {}).get("content", []):
                if c.get("type") == "tool_use":
                    what = c.get("input", {}).get("description") or c.get("input", {}).get("command") or c.get("name")
                    what = re.sub(r"\s+", " ", str(what))[:110]
                    if what != last:
                        job.say("   Claude: " + what); last = what
        if ev.get("type") == "result":
            result = str(ev.get("result", ""))
            if ev.get("is_error"):
                raise RuntimeError("The AI edit stopped: " + result[:200])
    p.wait()
    return result


# Script Writer, 2026-10-29 (Tiff: "even if someone ... doesn't have a video, or needs any help starting a video ...
# they dump their idea in, and this one helps you come up with the idea"). Words only, no video: it runs on its
# own thread, never behind RUN_LOCK, so a long render never makes someone wait for a script.
SCRIPT_PROMPT = """You are a short-form video script writer for one small business owner. Write the script they will
read out loud on camera. Nobody is watching this run, so never ask a question: make the call and say it in NOTES.

Their brand: {name}. Their call to action: {cta}.
How they sound (their own writing, may be empty): {voice}

What they gave you:
<<<
{idea}
>>>

First decide which it is.
- THEIR OWN WORDS (a voice note typed out, a transcript, a long ramble in first person): use ONLY their words.
  You pick, cut and reorder. Never add a word, not even a bridge.
- A TOPIC or a short idea: write it fresh in their voice. Say in NOTES that these are your words in their style,
  so they read it out loud and change anything that does not sound like them.

The script: 20 to 45 seconds read aloud, 55 to 120 words. One problem, one answer.
- HOOK: open on the punchline, a specific number, or the viewer's situation. Never open with a question.
- TENSION: one problem in the viewer's day. Short stacked lines.
- PAYOFF: the one answer. Stop the moment it lands.
Never invent a number, price, name, result or fact they did not give you. If a proof point would help (a payment,
a result, a screenshot), say in NOTES what to show on screen, and leave the number for them to fill in.
Never use em dashes. Use a period, comma or colon. No corporate filler.

Then write 5 top-of-screen hooks, each 6 words or less, each using a different hook style (a bold claim, a number,
a "stop doing X", a before and after, a callout of who it is for). With their own words, the hooks may be new words
because they go on screen, not in the script.

Then a short caption in their voice that ends on their call to action.

Reply in exactly this plain text shape, nothing before or after:
HOOK
...
TENSION
...
PAYOFF
...
TOP-OF-SCREEN HOOKS
1. ...
2. ...
3. ...
4. ...
5. ...
CAPTION
...
NOTES
...
"""


def run_script(job, idea, voice):
    job.state, job.started, job.estimate = "writing", time.time(), 60
    job.say("Writing your script")
    try:
        exe = claude_cli()
        if not exe or not claude_ready():
            raise RuntimeError("Claude isn't signed in on this computer yet. Finish Set up first.")
        b = brand()
        prompt = SCRIPT_PROMPT.format(name=b.get("name") or "not given", cta=b.get("cta") or "not given",
                                      voice=voice or "not given", idea=idea)
        r = subprocess.run([exe, "-p", prompt, "--output-format", "text"], capture_output=True, text=True,
                           timeout=300, cwd=job.dir)
        out = (r.stdout or "").strip().replace("\u2014", ",").replace("\u2013", ",")
        if r.returncode or "HOOK" not in out or "PAYOFF" not in out:
            raise RuntimeError("The script came back empty. Try again in a minute.")
        job.script = out
        open(os.path.join(job.dir, "script.txt"), "w").write(out)
        job.state = "done"
        job.say("Your script is ready")
    except Exception as e:
        job.state, job.error = "error", str(e)
        job.say("Stopped: " + str(e))
    job.save()


def transcript_for_agent(job, dst):
    """Our fast transcript, in the timed JSON the editor imports (seconds on the source timeline)."""
    key_ = re.sub(r"\W", "_", os.path.basename(job.src))[:60] + f"_{os.path.getsize(job.src)}"
    cache = os.path.join(JOBS, "_cache", key_)
    os.makedirs(cache, exist_ok=True)
    if os.path.exists(os.path.join(cache, "transcript.json")):
        d = json.load(open(os.path.join(cache, "transcript.json")))
    else:
        transcribe(job, "auto")
        shutil.copy(os.path.join(job.dir, "transcript.json"), cache)
        d = json.load(open(os.path.join(cache, "transcript.json")))
    words, segs = d["words"], d["segments"]
    out = []
    for sg in segs:
        ws = [{"start": round(w["start"], 3), "end": round(w["end"], 3), "text": w["word"].strip()}
              for w in words if sg["start"] - 0.05 <= w["start"] < sg["end"] + 0.05]
        out.append({"start": round(sg["start"], 3), "end": round(sg["end"], 3), "text": sg["text"].strip(), **({"words": ws} if ws else {})})
    json.dump({"segments": out}, open(dst, "w"))


AGENT_PROMPT = """Read AGENTS.md and start editing my video {video}. Create a polished vertical short with original,
content-specific motion graphics. Vary the visual medium, layout, typography, and color where it helps explain the
ideas. Use the actual speech for captions and keep my meaning intact. Check setup, make the creative decisions,
render a draft, review it, fix issues, and export the final MP4.

Details for this run (nobody is watching, so never stop to ask a question; make the call and note it in the brief):
- Job slug: {slug}. The dependencies are already installed and doctor passes.
- A real timed transcript is at {transcript}. Import it with: node scripts/editor.mjs transcript {transcript} --job {slug}
- Keep the finished short between 30 and 60 seconds: pick the strongest stretch of the video.
- My brand color is {accent}. Use it as the main accent.
- Render the FINAL to renders/{slug}/ and make sure an .mp4 is there when you finish.
{style}"""


def run_ai_edit(job, opts, style=None, refs=()):
    if not claude_ready():
        raise RuntimeError("Claude Code isn't signed in on this computer, so the AI edit can't run. "
                           "Open Terminal, type claude auth login, sign in, then try again.")
    if not os.path.exists(os.path.join(SPLIT, "node_modules")):
        raise RuntimeError("The Split Screen Editor isn't set up on this computer yet.")
    secs = float(probe(job.src, count=False)["format"]["duration"])
    job.say(f"Got it: {os.path.basename(job.src)}, {secs / 60:.1f} min")
    slug = "d" + job.id.replace("-", "")[-10:]
    os.makedirs(os.path.join(SPLIT, "inputs"), exist_ok=True)
    video = f"inputs/{slug}.mp4"
    shutil.copy(job.src, os.path.join(SPLIT, video))
    job.state = "writing down every word"
    transcript_for_agent(job, os.path.join(SPLIT, "inputs", f"{slug}.json"))
    lines = ""
    if style:
        lines = ("- COPY THIS CREATOR'S EDITING as closely as you can, every part of it: " + "; ".join(plain_traits({"settings": style}))
                 + ". Match their pacing, caption look and position, layouts (split screens, inserts, b-roll, full-frame graphics), "
                 "and how often the picture changes. Never use their footage, music, logo or name.")
        for i, r in enumerate(refs, 1):
            dst = os.path.join(SPLIT, "inputs", f"{slug}-ref{i}.jpg")
            shutil.copy(r, dst)
        if refs:
            lines += f"\n- Frames from their reels to study (look at every one): inputs/{slug}-ref*.jpg"
    job.state = "Claude is editing your video (about 15 to 25 minutes)"
    run_agent(job, AGENT_PROMPT.format(video=video, slug=slug, transcript=f"inputs/{slug}.json",
                                       accent="#" + brand()["accent"], style=lines), SPLIT)
    import glob
    finals = sorted(glob.glob(os.path.join(SPLIT, "renders", slug, "**", "*.mp4"), recursive=True) +
                    glob.glob(os.path.join(SPLIT, "renders", f"{slug}*.mp4")), key=os.path.getmtime)
    finals = [f for f in finals if "draft" not in os.path.basename(f).lower()] or finals
    if not finals:
        raise RuntimeError("Claude finished but no video came out. Its notes are in ~/Split-Screen-Editor/jobs/" + slug)
    name = re.sub(r"[^\w &-]", "", os.path.splitext(job.name)[0]).strip()[:50]
    out = os.path.join(job.dir, "out", f"{name} - {'Copied Style' if style else 'Split Screen'}.mp4")
    shutil.copy(finals[-1], out)
    d = float(probe(out, count=False)["format"]["duration"])
    ok, checks = ledger(out, "1080x1920", d)
    checks.pop("length matches the moment", None)
    sheet = out[:-4] + " frames.jpg"
    contact_sheet(out, sheet)
    job.shorts.append({"file": os.path.basename(out), "sheet": os.path.basename(sheet), "ok": ok, "seconds": round(d, 1),
                       "from": "", "hook": [], "why": "Edited by Claude Code with the Split Screen Editor.", "checks": checks})
    job.say(f"AI edit {'PASSED' if ok else 'FAILED'} the checks")
    job.save()


def drive_folder():
    """Where finished shorts go: Google Drive for Desktop if this computer has it, else Movies."""
    import glob
    # 2026-11-01: macOS leaves dead copies named "GoogleDrive-you@x.com (10-29-26 3:10 PM)" after a Drive restart.
    # They sort first and nothing in them uploads, so finished videos sat there and never reached Google
    roots = [r for r in sorted(glob.glob(os.path.join(HOME, "Library/CloudStorage/GoogleDrive-*/My Drive")))
             if not re.search(r" \([^/]*\)/My Drive$", r)]
    base = roots[0] if roots else os.path.join(HOME, "Movies")
    return os.path.join(base, "Content Made Easy Videos")


# 2026-10-30: a fresh member who skipped Box 1 dropped a video and got "No such file ... ffprobe".
# Every video job now stops at the door with plain words instead.
SETUP_FIRST = ("Your video tools aren't installed yet. Close the little black window that opened with "
               "this page, then double-click Start Content Made Easy again and wait until it says ready.")


def tools_ready():
    return os.path.exists(FF) and os.path.exists(FP) and os.path.exists(VENV_PY)


def setup_status():
    """What this Mac already has. The page shows these next to the boxes people tick."""
    free = shutil.disk_usage(HOME).free
    return {
        "editing kit (Box 1)": os.path.exists(VENV_PY) and os.path.exists(YUNET),
        "clean sound (Box 2)": bool(deep_filter()),
        "ffmpeg": os.path.exists(FF) and os.path.exists(FP),
        "free Groq key": bool(key("GROQ_API_KEY")),
        "effects kit": True,     # her own effects always ship; the kit's 24 show only where the kit is installed
        "ai edits": bool(claude_cli()) and os.path.exists(os.path.join(SPLIT, "node_modules")) and claude_ready(),
        "free disk space": f"{free / 1e9:.1f} GB",
        "ready": tools_ready(),
    }


# ---------------------------------------------------------------- jobs

AJENE_PROJECTS = {}   # dashboard job -> its Edit Studio video, so tapping a second edit changes the pick and doesn't add the video twice


def ajene_pick(job, style):
    """Puts the dashboard's video in Edit Studio with this edit chosen, then reads the choice back from Studio."""
    import urllib.request

    def call(method, path, data=None):
        req = urllib.request.Request("http://localhost:4191" + path, method=method, headers={"Content-Type": "application/json"},
                                     data=None if data is None else json.dumps(data).encode())
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    r = subprocess.run(["bash", AJENE_STUDIO, "--no-open"], capture_output=True, text=True, timeout=300)
    if r.returncode:
        raise RuntimeError((r.stderr or r.stdout)[-300:])
    pid = AJENE_PROJECTS.get(job.id)
    if pid:
        try:
            call("GET", f"/api/projects/{pid}")
        except Exception:   # removed in Edit Studio since the last tap
            pid = None
    if not pid:
        pid = call("POST", "/api/projects", {"paths": [job.src], "title": os.path.splitext(job.name)[0]})["ids"][0]
        AJENE_PROJECTS[job.id] = pid
    call("PUT", f"/api/projects/{pid}/choices", {"style": style})
    saved = call("GET", f"/api/projects/{pid}")["choices"].get("style")
    if saved != style:
        raise RuntimeError(f"it saved {saved} instead of {style}")
    return {"url": f"http://localhost:4191/#/p/{pid}/style", "project": pid}


class Job:
    def __init__(self, src, name):
        self.id = time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:4]
        self.dir = os.path.join(JOBS, self.id)
        os.makedirs(os.path.join(self.dir, "out"), exist_ok=True)
        self.src, self.name = src, name
        self.state, self.steps, self.shorts, self.error = "waiting", [], [], ""
        self.review, self.go, self.delivered = [], threading.Event(), ""
        self.started, self.estimate = 0.0, 0
        self.styles = []
        self.script = ""
        JOBS_BY_ID[self.id] = self

    def say(self, msg):
        self.steps.append(time.strftime("%H:%M:%S ") + msg)
        open(os.path.join(self.dir, "log.txt"), "a").write(self.steps[-1] + "\n")

    def view(self):
        return {"id": self.id, "name": self.name, "state": self.state, "steps": self.steps,
                "shorts": self.shorts, "error": self.error, "review": self.review if not self.go.is_set() else [],
                "delivered": self.delivered,
                "elapsed": int(time.time() - self.started) if self.started and not self.state.startswith(("done", "stopped")) else 0,
                "estimate": self.estimate, "styles": self.styles, "script": self.script}

    def save(self):
        json.dump(self.view(), open(os.path.join(self.dir, "job.json"), "w"), indent=1)


JOBS_BY_ID = {}

# Updates, 2026-10-27 (Tiff: "when I update it, does it update everyone's?"). The member build stamps
# VERSION and puts version.json next to the zip in Tiff's shared Drive folder. Each member's dashboard
# checks it, shows "Update now", and replaces its own files while keeping their brand, answers and videos.
VERSION = "2026.11.11.1908"                                   # build-member-copy.sh writes the real stamp into the member copy
UPDATE_VERSION_ID = ""                            # Drive id of version.json, filled in by the build
UPDATE_ZIP_ID = ""
KEEP_ON_UPDATE = {"brand.json", "brand-assets", "jobs"}
_latest = {"at": 0.0, "v": ""}


def drive_bytes(file_id, timeout=20):
    import urllib.request
    url = f"https://drive.google.com/uc?export=download&id={file_id}"
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "YourMarketingDashboard"}), timeout=timeout) as r:
        return r.read()


def latest_version():
    if VERSION == "dev" or not UPDATE_VERSION_ID:
        return ""
    if time.time() - _latest["at"] > 3600:
        _latest["at"] = time.time()
        try:
            _latest["v"] = str(json.loads(drive_bytes(UPDATE_VERSION_ID, 8)).get("version", ""))
        except Exception:
            _latest["v"] = ""          # offline or not shared: never nag, never break the page
    return _latest["v"]


def apply_update():
    """Download the newest zip, check it really is the dashboard, copy its files over this folder
    (never brand.json, brand-assets or jobs), then restart this same window on the new code."""
    import zipfile, io
    data = drive_bytes(UPDATE_ZIP_ID, 60)
    z = zipfile.ZipFile(io.BytesIO(data))
    names = [n for n in z.namelist() if n.startswith("Your-Marketing-Dashboard/")]
    if "Your-Marketing-Dashboard/server.py" not in names:
        raise RuntimeError("The download didn't look like the dashboard. Nothing was changed.")
    tmp = tempfile.mkdtemp(prefix="update_", dir=HERE)
    z.extractall(tmp)
    new = os.path.join(tmp, "Your-Marketing-Dashboard")
    compile(open(os.path.join(new, "server.py")).read(), "server.py", "exec")      # never swap in a broken server
    backup = os.path.join(HERE, ".before-update")
    shutil.rmtree(backup, ignore_errors=True)
    os.makedirs(backup)
    for root, dirs, files in os.walk(new):
        rel = os.path.relpath(root, new)
        if rel.split(os.sep)[0] in KEEP_ON_UPDATE:
            continue
        for f in files:
            if rel == "." and f in KEEP_ON_UPDATE:
                continue
            dst = os.path.normpath(os.path.join(HERE, rel, f))
            if os.path.exists(dst):
                os.makedirs(os.path.join(backup, rel), exist_ok=True)
                shutil.copy2(dst, os.path.join(backup, rel, f))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(os.path.join(root, f), dst)
    shutil.rmtree(tmp, ignore_errors=True)


# Beta login, 2026-10-27 (Tiff: one shared username and password for every beta tester).
# The dashboard only listens on the person's own Mac, so this is a door for beta testers, not a vault:
# the password ships inside the zip.
LOGIN_USER, LOGIN_PASS = "test", "blessed123"
LOGIN_TOKEN = hashlib.sha256(f"{LOGIN_USER}:{LOGIN_PASS}:your-marketing-dashboard".encode()).hexdigest()[:32]
OPEN_PATHS = {"/login", "/api/login", "/style.css", "/icon.png", "/favicon.ico", "/manifest.json"}
RUN_LOCK = threading.Lock()   # one video at a time, so two renders never fight for the disk


def transcribe(job, engine, src=None):
    sys.path.insert(0, ENGINE)
    import transcribe as T
    T.log = lambda m: job.say("   " + m.strip())
    src = src or job.src
    secs = float(probe(src, count=False)["format"]["duration"])
    tmp = tempfile.mkdtemp(prefix="cd_", dir=job.dir)
    words, segs = [], []
    n = int(secs // T.CHUNK) + 1
    for i in range(n):
        mp3 = os.path.join(tmp, f"c{i}.mp3")
        subprocess.run([FF, "-v", "error", "-ss", str(i * T.CHUNK), "-t", str(T.CHUNK), "-i", src, "-vn",
                        "-ac", "1", "-ar", "16000", "-c:a", "libmp3lame", "-b:a", "48k", "-y", mp3], check=True)
        if os.path.getsize(mp3) < 20000 and i > 0:
            continue
        res = T.eleven(mp3)
        used = "ElevenLabs"
        if res is None:
            res = T.groq(mp3) if engine != "mac" else None
            used = "fast"
        if res is None:
            res, used = T.local(mp3), "on this computer"
        w, s = res
        off = i * T.CHUNK
        words += [{"word": x["word"], "start": x["start"] + off, "end": x["end"] + off} for x in w]
        segs += [{"start": x["start"] + off, "end": x["end"] + off, "text": x["text"]} for x in s]
        job.say(f"Wrote down part {i + 1} of {n} ({used}): {len(w)} words")
    shutil.rmtree(tmp, ignore_errors=True)
    if not words:
        raise RuntimeError("The transcript came back EMPTY. Stopping instead of guessing.")
    json.dump({"words": words, "segments": segs}, open(os.path.join(job.dir, "transcript.json"), "w"))
    job.say(f"Transcript done: {len(words)} words, last word at {words[-1]['end'] / 60:.1f} of {secs / 60:.1f} min")
    return words, segs, secs


PICK_RULES = """You are a short-form video editor. Below is part of a transcript of a live teaching call.
Lines look like [start-end] text, times in seconds. Find the moments that work as a 20 to 45 second
vertical short ON THEIR OWN, for a stranger who never saw the call.
Rules:
- The HOST is teaching one idea: a hook, then the payoff. Skip chit-chat, waiting, tech trouble,
  sales or money talk between people, gossip, named outside people, and members' personal stories.
- Find the PAYOFF line first. Start on the punch, a specific number, or the viewer's situation.
  NEVER start on a question, mid-sentence, "so yeah", "like I said". End the moment the payoff lands.
- start and end must be line boundaries from the transcript. Length 20 to 45 seconds.
- hook: two short ALL CAPS lines for the top of the screen, each 18 characters or fewer. The hook
  names the PAYOFF or the viewer's win. It must NOT repeat the first words the speaker says, and no
  number twice. blue: 1 to 3 key words from the clip to color.
- score 1 to 10: how strongly a stranger would stop scrolling and learn something.
Return ONLY JSON: {"moments":[{"start":0.0,"end":0.0,"title":"Three To Five Words","hook":["LINE ONE","LINE TWO"],"blue":["word"],"score":7,"why":"one sentence"}]}
Return {"moments":[]} if nothing qualifies. At most 2 moments.
Transcript:
"""


PICK_LOOSE = PICK_RULES.replace("part of a transcript of a live teaching call", "the transcript of a short talking video") \
    .replace("Return {\"moments\":[]} if nothing qualifies.", "Always return the 1 or 2 BEST moments, even if they are not perfect. "
             "Talking about a product or tool you use is fine.")


def ask_groq(text):
    import requests
    k = key("GROQ_API_KEY")
    if not k:
        raise RuntimeError("No Groq key on this computer.")
    for attempt in range(6):
        r = requests.post("https://api.groq.com/openai/v1/chat/completions",
                          headers={"Authorization": f"Bearer {k}"}, timeout=(30, 180),
                          json={"model": PICK_MODEL, "response_format": {"type": "json_object"},
                                "max_tokens": 2500, "messages": [{"role": "user", "content": text}]})
        if r.status_code == 200:
            return json.loads(r.json()["choices"][0]["message"]["content"])
        if r.status_code == 400 and "json_validate_failed" in r.text:
            # 2026-10-27: the free model sometimes writes almost-JSON. Its draft comes back with the
            # error; take the first {...} in it if that reads, else ask again.
            draft = (r.json().get("error") or {}).get("failed_generation", "")
            m = re.search(r"\{.*\}", draft, re.S)
            if m:
                try:
                    return json.loads(m.group(0))
                except ValueError:
                    pass
            if attempt < 4:
                continue
        if r.status_code == 429:
            time.sleep(min(float(r.headers.get("retry-after", 20) or 20), 90) + 1)
            continue
        if attempt >= 2:
            raise RuntimeError(f"Moment picker said HTTP {r.status_code}: {r.text[:160]}")
        time.sleep(10)
    raise RuntimeError("Moment picker kept saying 'too busy'. Try again in a few minutes.")


def pick(job, segs, secs, how_many):
    seen = os.path.join(job.cache, "found.json")
    found = json.load(open(seen)) if os.path.exists(seen) else None
    if found is not None:
        job.say(f"Already looked through this video before: {len(found)} moments, reusing them")
        return choose(job, found, how_many)
    found = []
    t = 0
    while t < secs:
        lines = [s for s in segs if t <= s["start"] < t + WINDOW]
        t += WINDOW
        if sum(len(s["text"].split()) for s in lines) < 60:
            continue
        body = "\n".join(f"[{s['start']:.1f}-{s['end']:.1f}] {s['text'].strip()}" for s in lines)
        try:
            got = ask_groq(PICK_RULES + shorts_taste() + body).get("moments", [])
        except Exception as e:
            job.say(f"   skipped {int(lines[0]['start'] // 60)} min mark: {e}")
            continue
        for m in got:
            try:
                m["start"], m["end"] = float(m["start"]), float(m["end"])
            except (KeyError, TypeError, ValueError):
                continue
            if 15 <= m["end"] - m["start"] <= 50 and len(m.get("hook", [])) == 2:
                found.append(m)
        job.say(f"Looked through minute {int(lines[0]['start'] // 60)} to {int(min(t, secs) // 60)}: {len(got)} moment(s)")
    if not found and secs <= 1200:
        # 2026-10-27: the rules above are tuned for Zoom teaching calls and turned down a 3 minute talking
        # video about a product that made a fine short. One looser pass for short videos.
        body = "\n".join(f"[{s['start']:.1f}-{s['end']:.1f}] {s['text'].strip()}" for s in segs)[:14000]
        try:
            got = ask_groq(PICK_LOOSE + shorts_taste() + body).get("moments", [])
        except Exception as e:
            got = []
            job.say(f"   second look failed: {e}")
        for m in got:
            try:
                m["start"], m["end"] = float(m["start"]), float(m["end"])
            except (KeyError, TypeError, ValueError):
                continue
            if 15 <= m["end"] - m["start"] <= 50 and len(m.get("hook", [])) == 2:
                found.append(m)
        job.say(f"Second, looser look at the whole video: {len(found)} moment(s)")
    json.dump(found, open(seen, "w"))
    return choose(job, found, how_many)


def on_camera(src, s, e):
    """True when a face shows in at least 3 of 5 frames across the moment. On 2026-10-26 three shorts
    passed every count and showed only Zoom's black name tile because the camera was off."""
    import cv2
    cap = cv2.VideoCapture(src)
    det, hits = None, 0
    for k in range(5):
        cap.set(cv2.CAP_PROP_POS_MSEC, (s + (e - s) * (k + 0.5) / 5) * 1000)
        ok, f = cap.read()
        if not ok:
            continue
        if det is None:
            det = cv2.FaceDetectorYN.create(YUNET, "", (f.shape[1], f.shape[0]), 0.6)
        _, fc = det.detect(f)
        hits += fc is not None and len(fc) > 0
    cap.release()
    return hits >= 3


def choose(job, found, how_many):
    found.sort(key=lambda m: -float(m.get("score", 0)))
    chosen, off_cam = [], 0
    for m in found:     # no two shorts from the same stretch of the call, and only when a face shows
        if not all(m["end"] < c["start"] - 5 or m["start"] > c["end"] + 5 for c in chosen):
            continue
        if not on_camera(job.src, m["start"], m["end"]):
            off_cam += 1
            continue
        chosen.append(m)
        if len(chosen) == how_many:
            break
    if off_cam:
        job.say(f"Skipped {off_cam} moment(s) where no face was on camera")
    json.dump({"all": found, "chosen": chosen}, open(os.path.join(job.dir, "moments.json"), "w"), indent=1)
    if not found:
        raise RuntimeError("Couldn't find a 20 to 45 second part that works on its own. Nothing was cut. "
                           "Try a longer video, or one where you teach one clear idea.")
    if not chosen:
        raise RuntimeError("No moment passed the rules with a face on camera. Nothing was cut. "
                           "Try a video where your camera is on and you're teaching.")
    return sorted(chosen, key=lambda m: m["start"])


def quiet_point(src, t, reach=0.8):
    """The quietest 20 ms within `reach` seconds of t, so cuts land on a real pause, not mid-word."""
    import numpy as np
    a = max(0.0, t - reach)
    raw = subprocess.run([FF, "-v", "error", "-ss", str(a), "-t", str(2 * reach), "-i", src, "-vn", "-ac", "1",
                          "-ar", "16000", "-f", "s16le", "-"], capture_output=True).stdout
    x = np.frombuffer(raw, dtype=np.int16).astype(float)
    if len(x) < 640:
        return t
    hop = 320
    rms = np.array([np.sqrt(np.mean(x[i:i + hop] ** 2)) for i in range(0, len(x) - hop, hop)])
    dist = np.abs(np.arange(len(rms)) * 0.02 + a - t)
    return round(a + float(np.argmin(rms * (1 + dist))) * 0.02 + 0.01, 3)


def safe_hook(line):
    """ffmpeg's drawtext reads % as a code and , ; [ ] as filter syntax. On 2026-10-26 the hook
    "AT LEAST 30%" made the finisher fail. Keep plain letters, numbers and a few marks."""
    line = line.upper().replace("%", " PERCENT").replace("&", " AND ")
    line = re.sub(r"\s+", " ", re.sub(r"[^A-Z0-9 $!?'.]", " ", line)).strip()
    return line if len(line) <= 22 else line[:23].rsplit(" ", 1)[0][:22]


def cut(src, start, end, dst):
    subprocess.run([FF, "-v", "error", "-ss", f"{start:.3f}", "-i", src, "-t", f"{end - start:.3f}",
                    "-vf", f"fps={FPS}", "-c:v", "libx264", "-crf", "12", "-preset", "fast", "-pix_fmt", "yuv420p",
                    "-af", "afade=t=in:d=0.02,areverse,afade=t=in:d=0.02,areverse", "-ar", "48000",
                    "-c:a", "pcm_s16le", "-y", dst], check=True)


def ledger(path, expect_shape, expect_seconds):
    """Count the thing, do not read the summary of the thing."""
    info = probe(path)
    v, a = stream(info, "video"), stream(info, "audio")
    dur = float(info["format"]["duration"])
    num, den = (int(x) for x in v["r_frame_rate"].split("/"))
    fps = num / den
    frames = int(v["nb_read_packets"])
    want_frames = dur * fps
    apk = int(a["nb_read_packets"]) if a else 0
    sr = int(a["sample_rate"]) if a else 0
    want_apk = dur * sr / 1024
    checks = {
        "ffprobe reads it": True,
        "shape": [f"{v['width']}x{v['height']}", expect_shape, f"{v['width']}x{v['height']}" == expect_shape],
        "frames = seconds x fps": [frames, round(want_frames, 1), abs(frames - want_frames) <= 2],
        **({"audio packets = seconds x rate / 1024": [apk, round(want_apk, 1), abs(apk - want_apk) <= 3]}
           if a and a.get("codec_name") == "aac" else
           {"sound is the full length": [round(float(a.get("duration") or 0), 2) if a else 0, round(dur, 2),
                                        bool(a) and abs(float(a.get("duration") or 0) - dur) <= 0.1]}),
        "length matches the moment": [round(dur, 2), round(expect_seconds, 2), abs(dur - expect_seconds) <= 0.15],
    }
    ok = all(c is True or c[-1] for c in checks.values())
    return ok, checks


def contact_sheet(path, dst):
    """6 evenly spaced frames side by side, so a person can see the face, captions and hook at a glance."""
    d = float(probe(path)["format"]["duration"])
    subprocess.run([FF, "-v", "error", "-i", path, "-vf", f"fps=6/{d:.2f},scale=270:-2,tile=6x1",
                    "-frames:v", "1", "-y", dst], capture_output=True)


def snap_moment(m, words):
    """A short starts and ends on a whole sentence. On 2026-11-04 two shorts passed every count while one began
    on "work." and ended on "so it", because the moment finder's times are only close. Move each edge to the
    nearest sentence edge; with no punctuation nearby, leave it alone."""
    w = [x for x in words if m["start"] - 6 <= x["start"] <= m["end"] + 6]
    ends = lambda x: bool(re.search(r"[.?!][\"')]*$", x["word"].strip()))
    starts = [x["start"] for i, x in enumerate(w) if i and ends(w[i - 1])]
    a = [t for t in starts if m["start"] - 0.01 <= t <= m["start"] + 2.5] or [t for t in starts if t <= m["start"]][-1:]
    z = [x["end"] for x in w if ends(x) and x["end"] >= m["end"] - 0.01][:1] or [x["end"] for x in w if ends(x) and x["end"] <= m["end"] and x["end"] >= m["end"] - 4][-1:]
    out = dict(m)
    if a:
        out["start"] = a[0]
    if z:
        out["end"] = z[0] + 0.02
    return out if 8 <= out["end"] - out["start"] <= 60 else m


def run_shorts(job, opts):
    info = probe(job.src, count=False)
    v = stream(info, "video")
    if not v or not stream(info, "audio"):
        raise RuntimeError("This file needs both a picture and sound.")
    secs = float(info["format"]["duration"])
    job.say(f"Got it: {os.path.basename(job.src)}, {secs / 60:.0f} min, {v['width']}x{v['height']}")
    need = 1.5e9
    if shutil.disk_usage(HOME).free < need:
        raise RuntimeError(f"Only {shutil.disk_usage(HOME).free / 1e9:.1f} GB free. Free up 1.5 GB first.")
    key_ = re.sub(r"\W", "_", os.path.basename(job.src))[:60] + f"_{os.path.getsize(job.src)}"
    cache = os.path.join(JOBS, "_cache", key_)
    os.makedirs(cache, exist_ok=True)
    if os.path.exists(os.path.join(cache, "transcript.json")):
        d = json.load(open(os.path.join(cache, "transcript.json"))); words, segs = d["words"], d["segments"]
        job.say(f"Already wrote this video down before: {len(words)} words, reusing them")
    else:
        job.state = "writing down every word"
        words, segs, secs = transcribe(job, opts.get("engine", "auto"))
        shutil.copy(os.path.join(job.dir, "transcript.json"), cache)
    job.cache = cache
    job.state = "finding your best moments"
    moments = pick(job, segs, secs, int(opts.get("count", 3)))
    moments = [snap_moment(m, words) for m in moments]
    words_in = lambda m: " ".join(w["word"].strip() for w in words if m["start"] <= w["start"] < m["end"])
    job.review = [{"i": i, "from": f"{int(m['start'] // 60)}:{int(m['start'] % 60):02d}",
                   "seconds": round(m["end"] - m["start"]), "words": words_in(m), "hook": [safe_hook(h) for h in m["hook"]],
                   "title": m.get("title", "")} for i, m in enumerate(moments)]
    job.state = "pick your hooks"
    job.say(f"Found {len(moments)} moment(s) with you on camera. Pick and edit the hooks, then click Make these shorts.")
    # waiting on the person is not work: let other videos run meanwhile (2026-11-04: a job sat "in line" 90 minutes behind this wait)
    RUN_LOCK.release()
    try:
        job.go.set()      # this page makes the moments it found. They pick what to post from the finished videos
        job.go.wait()
    finally:
        RUN_LOCK.acquire()
    picked = [(moments[r["i"]], r["hook"]) for r in job.review if r.get("keep", True)]
    if not picked:
        raise RuntimeError("No moments were kept. Nothing was made.")
    preset, hook_font = brand_files(brand())
    style = opts.get("style_settings")
    if style:
        sr = style_render(style)
        preset, hook_font = sr["preset"], sr["font"]
        job.say("Copying the style you picked: " + "; ".join(plain_traits({"settings": style})))
    job.say(f"Making {len(picked)} short(s) now.")
    for n, (m, hook_lines) in enumerate(picked, 1):
        job.state = f"making short {n} of {len(picked)}"
        s, e = quiet_point(job.src, m["start"]), quiet_point(job.src, m["end"])
        base = os.path.join(job.dir, f"m{n}")
        # every pause inside the moment is cut too (2026-10-27: "it should get rid of the dead air")
        spans = speech_spans(job.src, s, e)
        mlen = tighten(job.src, spans, base + ".mov") if spans else (cut(job.src, s, e, base + ".mov") or e - s)
        ok_cut, cut_checks = ledger(base + ".mov", f"{v['width']}x{v['height']}", mlen)
        if not ok_cut:
            raise RuntimeError(f"Cut {n} did not match the source: {cut_checks}")
        clean = base + " CLEAN.mov"
        if deep_filter():
            subprocess.run([sys.executable, CLEANER, base + ".mov"], check=True, capture_output=True)
        else:
            os.rename(base + ".mov", clean)
            job.say("   clean sound is not set up yet, so the sound was left as it is")
        title = re.sub(r"[^\w ]", "", m.get("title", f"Short {n}")).strip()[:50] or f"Short {n}"
        out = os.path.join(job.dir, "out", f"{n} {title}.mp4")
        moves_file, ctas = [], []
        if opts.get("style_moves"):        # the copied reel's own edit, laid onto this short
            zooms, until, ctas = edit_plan(opts["style_moves"], mlen, opts.get("answers", {}))
            cy_ = style.get("caption_y", 0.5) if style else 0.5
            for c in ctas:       # 2026-10-27: the end pop-up sat right on the caption line; keep it clear above
                if -0.08 < cy_ - c["y"] < 0.1:
                    c["y"] = round(max(0.1, cy_ - 0.12), 3)
            mf = base + "-moves.json"
            json.dump({"zooms": zooms, "hook_until": until}, open(mf, "w"))
            moves_file = ["--moves", mf]
            job.say(f"   their edit on short {n}: {len(zooms)} jump-zooms at their rhythm"
                    + (f", headline for {until:.1f} s" if until else "") + (f", your call to action {len(ctas)} time(s)" if ctas else ""))
        r = subprocess.run([VENV_PY, FINISHER, clean, out, "--hook", *[safe_hook(h) or " " for h in hook_lines],
                            "--blue", *m.get("blue", []), "--layout", sr["layout"] if style else opts.get("layout", "full"),
                            "--preset", preset, "--font", hook_font, "--accent", sr["accent"] if style else brand()["accent"],
                            *(["--no-hook"] if style and sr["no_hook"] else []), *(["--caps"] if style and sr["caps"] else []),
                            *(["--hook-top", str(sr["hook_top"])] if style else []), *moves_file],
                           capture_output=True, text=True)
        if r.returncode:
            raise RuntimeError(f"Finishing short {n} failed: {(r.stderr or r.stdout)[-300:]}")
        rep = json.loads(r.stdout[r.stdout.index("{"):])
        shutil.rmtree(rep.get("work", ""), ignore_errors=True)
        for c in ctas:       # the person's own call to action where the creator had theirs
            tmp = out[:-4] + ".cta.mp4"
            cfg = {"accent": "#" + (sr["accent"] if style else brand()["accent"]), "font": hook_font, **c}
            rc = subprocess.run([VENV_PY, MYFX, "cta-pop", out, tmp, "--start", f"{c['start']:.2f}", "--end", f"{c['end']:.2f}",
                                 "--config", json.dumps(cfg)], capture_output=True, text=True)
            if rc.returncode or not os.path.exists(tmp):
                raise RuntimeError("Your call to action didn't render: " + (rc.stderr or rc.stdout).strip()[-200:])
            os.replace(tmp, out)
        for f in moves_file[1:]:
            os.remove(f)
        brand_finish(job, out)
        ok, checks = ledger(out, "1080x1920", mlen)
        if opts.get("style_moves"):
            checks["their edit copied (jump-zooms, your call to action)"] = [f"{rep.get('zooms', 0)} zooms, {len(ctas)} CTA", "as planned", True]
        import difflib
        norm = lambda t: [FIX_WORDS.get(x, x) for x in re.sub(r"[^a-z0-9 ]", " ", t.lower()).split()]
        said = norm(" ".join(w["word"] for w in words if s <= w["start"] < e))
        heard = norm(rep.get("captions", ""))
        match = round(100 * difflib.SequenceMatcher(None, said, heard).ratio())
        checks["captions match the transcript"] = [f"{match}%", ">= 80%", match >= 80]
        ok = ok and match >= 80
        sheet = out[:-4] + " frames.jpg"
        contact_sheet(out, sheet)
        for f in (base + ".mov", clean):
            if os.path.exists(f):
                os.remove(f)
        job.shorts.append({"file": os.path.basename(out), "sheet": os.path.basename(sheet), "ok": ok,
                           "seconds": round(mlen, 1), "from": f"{int(s // 60)}:{int(s % 60):02d}",
                           "hook": hook_lines, "why": m.get("why", ""), "checks": checks})
        job.say(f"Short {n} {'PASSED' if ok else 'FAILED'} the ledger check: {title}")
        job.save()


EFFECT_RULES = """You place one motion-graphics effect on a short vertical talking video.
Effect: {name}. What it does: {summary}
Use it when: {uses}
Its options (name: meaning): {options}
Its defaults: {defaults}
Below are the speaker's words with times in seconds. Pick ONE stretch of {lo} to {hi} seconds where this
effect fits best: it must start at the start of a sentence and end at the end of one. Then fill in ONLY the
options that hold words (titles, labels, items, headlines, numbers) using the speaker's OWN words from
that stretch. Keep "auto" wherever the defaults say "auto". Keep every text short (under 28 characters).
Every word you write must make sense to a stranger who sees only that text. Never use a fragment or a filler
word: not "get", "get it", "you", "guys", "that", "so", "this", "just", "actually". A one-word title is the word
that names what this video is about. Every word in the defaults is someone else's demo (ads, sales pages,
newsletters): replace all of them, nested ones too, with this speaker's own words. Never write a number the
speaker did not say. Never invent a person, a result or a claim.
Return ONLY JSON: {{"start": 0.0, "end": 0.0, "config": {{}}, "why": "one sentence"}}
Words:
"""


def fx_effect(effect_id):
    return json.load(open(os.path.join(FX_KIT, "engine/effects", f"{effect_id}.json")))


# Tiff's own effects (engine/myfx.py), 2026-10-27: original code, no kit files, so they ship to everyone.
MYFX = os.path.join(ENGINE, "myfx.py")
MYFX_DIR = os.path.join(HERE, "myfx-examples")
NO_PLAN = {"tiff-lights-on", "tiff-screen-wipe", "tiff-shutter-strike", "tiff-zoom-through", "tiff-pull-back", "tiff-whip-cut", "tiff-flash-cut", "tiff-black-white-beats", "tiff-match-cut", "tiff-shoulder-push", "tiff-big-type", "tiff-glow-stack", "tiff-flip-cards", "tiff-tier-list", "tiff-top-five", "tiff-always-never", "tiff-numbered-list", "tiff-mono-story", "tiff-explainer-panel", "tiff-ear-to-ear", "tiff-fitted-stack", "tiff-if-then", "tiff-quadrant", "tiff-cinema-type", "tiff-line-by-line", "tiff-short-box", "tiff-voice-note", "tiff-headline-wall", "tiff-cover-story", "tiff-paper-cut", "tiff-vertigo", "tiff-growth-chart", "tiff-glass-graph", "tiff-wall-words", "tiff-glass-words", "tiff-glass-panel", "tiff-end-stack", "tiff-app-world", "tiff-word-morph", "tiff-phase-reel", "tiff-split-steps", "tiff-business-rotate", "tiff-screen-and-you", "tiff-doc-split", "tiff-twin-versus", "tiff-two-roles", "tiff-day-reel", "tiff-screen-karaoke", "tiff-big-screen-caps", "tiff-split-kinetic", "tiff-tool-cards", "tiff-info-cards", "tiff-wide-minimal", "tiff-wide-lesson", "tiff-wide-tips", "tiff-wide-steps", "tiff-wide-board", "tiff-picture-under", "tiff-picture-above", "tiff-photo-split", "tiff-photo-world", "tiff-photo-grid", "tiff-float-up", "tiff-photo-cluster", "tiff-screen-slide", "tiff-screen-zoom", "tiff-picture-stack", "tiff-story-room", "tiff-then-and-now", "tiff-proof-above", "tiff-word-swap", "tiff-logo-spot", "tiff-fast-personal", "tiff-testimonial-wall", "tiff-behind-you", "tiff-phone-peek", "tiff-digital-zoom", "tiff-word-pop", "tiff-top-banner", "tiff-brand-frame", "tiff-brand-stage", "tiff-cinema-look", "tiff-split-stage", "tiff-note-card", "tiff-glow-words", "tiff-doodles", "tiff-orbit", "tiff-pop-out"}
FORMS = {'big-type', 'glow-stack', 'flip-cards', 'tier-list', 'top-five', 'always-never', 'numbered-list', 'mono-story', 'explainer-panel', 'ear-to-ear', 'fitted-stack', 'if-then', 'quadrant', 'cinema-type', 'line-by-line', 'short-box', 'voice-note', 'headline-wall', 'cover-story', 'paper-cut', 'vertigo', 'growth-chart', 'glass-graph', 'wall-words', 'glass-words', 'glass-panel', 'end-stack', 'app-world', 'word-morph', 'phase-reel', 'split-steps', 'business-rotate', 'screen-and-you', 'doc-split', 'twin-versus', 'two-roles', 'day-reel', 'screen-karaoke', 'big-screen-caps', 'split-kinetic', 'tool-cards', 'info-cards', 'wide-minimal', 'wide-lesson', 'wide-tips', 'wide-steps', 'wide-board', 'picture-under', 'picture-above', 'photo-split', 'photo-world', 'photo-grid', 'float-up', 'photo-cluster', 'screen-slide', 'screen-zoom', 'picture-stack', 'story-room', 'then-and-now', 'proof-above', 'word-swap', 'logo-spot', 'fast-personal', 'testimonial-wall', 'behind-you', 'phone-peek'}
FORM_NOCAP = ('tier-list', 'top-five', 'growth-chart', 'glass-graph', 'split-steps', 'photo-world', 'testimonial-wall', 'glow-stack', 'explainer-panel', 'ear-to-ear', 'fitted-stack', 'short-box', 'line-by-line', 'word-swap', 'fast-personal', 'phase-reel', 'screen-karaoke', 'big-screen-caps', 'split-kinetic')
FORM_PRE = ('screen-karaoke', 'big-screen-caps', 'split-kinetic', 'tool-cards', 'screen-and-you', 'doc-split', 'twin-versus', 'two-roles', 'day-reel', 'word-swap', 'fast-personal', 'phase-reel', 'wall-words', 'app-world', 'screen-slide', 'screen-zoom', 'split-steps', 'glass-panel', 'growth-chart', 'glass-graph', 'glass-words', 'big-type', 'always-never', 'glow-stack', 'explainer-panel', 'ear-to-ear', 'fitted-stack', 'short-box', 'line-by-line', 'headline-wall', 'cover-story', 'vertigo', 'quadrant', 'if-then', 'info-cards', 'picture-under', 'picture-above', 'photo-split', 'photo-world', 'photo-grid', 'float-up', 'photo-cluster', 'screen-slide', 'screen-zoom', 'picture-stack', 'story-room', 'then-and-now', 'proof-above', 'word-swap', 'logo-spot', 'fast-personal', 'testimonial-wall', 'behind-you', 'phone-peek')
PICTURE_KINDS = ('picture-under', 'picture-above', 'photo-split', 'photo-world', 'photo-grid', 'float-up', 'photo-cluster', 'screen-slide', 'screen-zoom', 'picture-stack', 'story-room', 'then-and-now', 'proof-above', 'word-swap', 'logo-spot', 'fast-personal', 'testimonial-wall', 'behind-you', 'phone-peek')
CLIP_KINDS = ('screen-and-you', 'doc-split', 'twin-versus', 'two-roles', 'day-reel')
WIDE_KINDS = ('wide-minimal', 'wide-lesson', 'wide-tips', 'wide-steps', 'wide-board')
MOVES = {'lights-on', 'screen-wipe', 'shutter-strike', 'zoom-through', 'pull-back', 'whip-cut', 'flash-cut', 'black-white-beats', 'match-cut', 'shoulder-push'}
MY_EFFECTS = [
    {"id": "tiff-lights-on", "name": 'Lights On', "uses": ['The room starts dark, the lights flicker on and your video comes all the way up.', 'A big opening.', 'Before and after moments.']},
    {"id": "tiff-screen-wipe", "name": 'Screen Wipe', "uses": ['Your video starts fogged over and gets wiped clear, back and forth.', 'Stops the scroll right away.', 'Reveals and big openers.']},
    {"id": "tiff-shutter-strike", "name": 'Shutter Strike', "uses": ['A camera shutter snaps shut and open on your key moments, with a flash.', 'Feels like a photo shoot.', 'Punchy lists and hooks.']},
    {"id": "tiff-zoom-through", "name": 'Zoom Through', "uses": ['The camera rushes through you into the next shot, with motion blur.', 'Fast and exciting.', 'High energy talking videos.']},
    {"id": "tiff-pull-back", "name": 'Pull Back', "uses": ['Opens tight on your face, then the camera pulls back.', 'A strong first second.', 'Any talking video.']},
    {"id": "tiff-whip-cut", "name": 'Whip Cut', "uses": ['The shot whips sideways and lands back on you.', 'Like a fast camera pan.', 'Moving between ideas.']},
    {"id": "tiff-flash-cut", "name": 'Flash Cut', "uses": ['A bright flash and a new framing land on each key moment.', 'Keeps eyes on the screen.', 'Fast talking videos.']},
    {"id": "tiff-black-white-beats", "name": 'Black and White Beats', "uses": ['Your video snaps between black and white and full color.', 'Feels like a film.', 'Stories and big statements.']},
    {"id": "tiff-match-cut", "name": 'Match Cut', "uses": ['Every shot change flips and reframes you, like a second camera across the room.', 'Feels like a real shoot.', 'Talking videos.']},
    {"id": "tiff-shoulder-push", "name": 'Shoulder Push', "uses": ['The camera drifts in from one side and then the other.', 'Feels like a documentary.', 'Stories and interviews.']},
    {"id": "tiff-big-type", "name": 'Big Type', "uses": ['Your opening line goes huge behind your head, stacked in your color.', 'Stops the scroll.', 'Hooks and big statements.']},
    {"id": "tiff-glow-stack", "name": 'Glow Stack', "uses": ['Every sentence stacks under your chin with one huge glowing word.', 'Replaces your captions.', 'Talking to the camera.']},
    {"id": "tiff-flip-cards", "name": 'Flip Cards', "uses": ['Full-screen cards flip black and white with one word at a time.', 'Then it cuts back to you.', 'Big lines you want felt.']},
    {"id": "tiff-tier-list", "name": 'Tier List', "uses": ['An S to F table sits on your chest and items drop in as you say them.', 'Type your own items, or we use your key words.', 'Ranking anything.']},
    {"id": "tiff-top-five", "name": 'Top 5', "uses": ['A numbered 1 to 5 board fills in as you go.', 'Type your own items, or we use your key words.', 'Countdowns.']},
    {"id": "tiff-always-never", "name": 'Always or Never', "uses": ['A two column chart over your head fills in as you talk.', 'Type your own items, or we use your key words.', 'Do this, not that.']},
    {"id": "tiff-numbered-list", "name": 'Numbered List', "uses": ['A title tag up top and a numbered list that fills in down the side.', 'Type your own items, or we use your key words.', 'Tips and lists.']},
    {"id": "tiff-mono-story", "name": 'Black and White Story', "uses": ['Black and white the whole way with big serif key words.', 'Moody and calm.', 'Personal stories.']},
    {"id": "tiff-explainer-panel", "name": 'Explainer Panel', "uses": ['A dark panel teaches each idea with one huge word and a big number.', 'Replaces your captions.', 'Lessons and frameworks.']},
    {"id": "tiff-ear-to-ear", "name": 'Side Words', "uses": ['Your words fade up either side of your head at eye level, left then right.', 'Replaces your captions.', 'Calm talking videos.']},
    {"id": "tiff-fitted-stack", "name": 'Fitted Stack', "uses": ['One big word in your color with the rest fitted around it, word by word.', 'Replaces your captions.', 'Any talking video.']},
    {"id": "tiff-if-then", "name": 'If Then Grid', "uses": ['A colored grid fills in row by row as you walk through it.', 'Type your own, or we use your key words.', 'Frameworks and decisions.']},
    {"id": "tiff-quadrant", "name": 'Four Box', "uses": ['A 4 box grid on a dark card reveals one box at a time above you.', 'Type your own, or we use your key words.', 'Frameworks and comparisons.']},
    {"id": "tiff-cinema-type", "name": 'Film Titles', "uses": ['Serif title cards cut in between your shots, like a movie trailer.', 'Then it cuts back to you.', 'Big statements.']},
    {"id": "tiff-line-by-line", "name": 'Line By Line', "uses": ['Each line picks its own look: you on camera, a black card, or a big word.', 'Keeps it changing.', 'Stories and hooks.']},
    {"id": "tiff-short-box", "name": 'Text Box Hook', "uses": ['A clean white text box hook up top and small outlined captions.', 'Great for TikTok.', 'Any talking video.']},
    {"id": "tiff-voice-note", "name": 'Voice Note', "uses": ['A voice message bubble with a moving waveform plays over you.', "Looks like you're playing a note.", 'Reactions and replies.']},
    {"id": "tiff-headline-wall", "name": 'Headline Wall', "uses": ['Your words stack into a wall of headlines behind your head.', 'Takes longer.', 'Big news and bold claims.']},
    {"id": "tiff-cover-story", "name": 'Cover Story', "uses": ['You\'re the cover, with your keyword up top: Comment "AI" For The Free Guide.', 'Type your keyword, or we use a word you said.', 'Getting comments and DMs.']},
    {"id": "tiff-paper-cut", "name": 'Paper Cut', "uses": ['A torn paper edge frames you with your words on a note.', 'Handmade feel.', 'Stories and teaching.']},
    {"id": "tiff-vertigo", "name": 'Vertigo', "uses": ['You hold still while the whole room rushes away behind you, with speed blur.', 'Takes longer.', 'A big moment of realization.']},
    {"id": "tiff-growth-chart", "name": 'Growth Chart', "uses": ['A line chart climbs on a dark card below your face as you talk.', 'Type your own labels, or we use your key words.', 'Results and growth.']},
    {"id": "tiff-glass-graph", "name": 'Glass Graph', "uses": ['A frosted glass card sits below your face with a climbing line.', 'Type your own labels, or we use your key words.', 'Results and big wins.']},
    {"id": "tiff-wall-words", "name": 'Wall Words', "uses": ['Your key word looks painted huge on the wall behind you.', 'Takes longer.', 'Bold statements.']},
    {"id": "tiff-glass-words", "name": 'Glass Words', "uses": ['Your key words land on a frosted glass strip.', 'Clean and modern.', 'Any talking video.']},
    {"id": "tiff-glass-panel", "name": 'Glass Panel', "uses": ['A frosted panel with a small graphic and a key word as you teach.', 'Type your own, or we use your key words.', 'Business lessons.']},
    {"id": "tiff-end-stack", "name": 'End Stack', "uses": ['Your call to action stacks up in cards at the end.', 'Uses the call to action in your brand.', 'Any video with an ask.']},
    {"id": "tiff-app-world", "name": 'App World', "uses": ["You're cut out in front of floating app screens with your words.", 'Takes longer.', 'Talking about tools and AI.']},
    {"id": "tiff-word-morph", "name": 'Word Stickers', "uses": ['Your key words swing in as price tag style stickers.', 'Playful.', 'Offers and lists.']},
    {"id": "tiff-phase-reel", "name": 'Phase Reel', "uses": ['Moves through a glowing hook, one word, black and white, then flip cards.', 'Replaces your captions.', 'Big storytelling reels.']},
    {"id": "tiff-split-steps", "name": 'Split Steps', "uses": ['Your face up top and a diagram below that draws itself.', 'Type your own, or we use your key words.', 'Steps and systems.']},
    {"id": "tiff-business-rotate", "name": 'Business Rotation', "uses": ['Rotates between you, a step label and a full screen word card.', 'Keeps it moving.', 'Business teaching.']},
    {"id": "tiff-screen-and-you", "name": 'Screen and You', "uses": ['Your screen recording fills the frame with you in the corner.', 'Add your screen recording.', 'Tutorials and walkthroughs.']},
    {"id": "tiff-doc-split", "name": 'Doc Split', "uses": ['Your document or screen on top, you on the bottom.', 'Add your screen recording.', 'Teaching from a document.']},
    {"id": "tiff-twin-versus", "name": 'Twin Versus', "uses": ['You twice, side by side, showing two ways to do something.', 'Add your second take.', 'This way vs that way.']},
    {"id": "tiff-two-roles", "name": 'Two Roles', "uses": ['One person, two roles. The picture cuts between your two takes.', 'Add your second take.', 'Funny skits and teaching.']},
    {"id": "tiff-day-reel", "name": 'Day Reel', "uses": ['Your clips play over your voice, changing with each shot.', 'Add your clips.', 'Vlogs and a day in your life.']},
    {"id": "tiff-screen-karaoke", "name": 'Screen Karaoke', "uses": ['Big words light up word by word over your screen recording.', 'Replaces your captions.', 'Drop in a screen recording.']},
    {"id": "tiff-big-screen-caps", "name": 'Screen Big Captions', "uses": ['Big one line captions on a solid bar that read over anything.', 'Replaces your captions.', 'Drop in a screen recording.']},
    {"id": "tiff-split-kinetic", "name": 'Split Kinetic', "uses": ['Your video up top, and your words slam in on the bottom half.', 'Replaces your captions.', 'High energy talking videos.']},
    {"id": "tiff-tool-cards", "name": 'Tool Cards', "uses": ['Each tool you name pops up as a clean card.', 'Type your tools, or we use your key words.', 'Tool lists and stacks.']},
    {"id": "tiff-info-cards", "name": 'Info Cards', "uses": ['A clean card with a header in your color drops in up top on each key word.', 'Type your own, or we use your key words.', 'Money talk, steps and big points.']},
    {"id": "tiff-wide-minimal", "name": 'YouTube Clean', "uses": ['A clean wide edit with a simple title and small captions.', 'For wide videos.', 'YouTube videos.']},
    {"id": "tiff-wide-lesson", "name": 'YouTube Lesson', "uses": ['A wide lesson with side cards when you land on a key idea.', 'For wide videos.', 'Teaching on YouTube.']},
    {"id": "tiff-wide-tips", "name": 'YouTube Tips', "uses": ['A chapter marker for each point and a progress bar along the bottom.', 'For wide videos.', 'List videos.']},
    {"id": "tiff-wide-steps", "name": 'YouTube Steps', "uses": ['Glowing step title cards cut in between your teaching.', 'For wide videos.', 'Step by step lessons.']},
    {"id": "tiff-wide-board", "name": 'YouTube Board', "uses": ['An agenda fills in on a clean white board beside you.', 'For wide videos.', 'Workshops and classes.']},
    {"id": "tiff-picture-under", "name": 'Picture Under', "uses": ['Your pictures show under your chin, changing on every phrase.', 'Add your own pictures.', 'Explaining what you mean.']},
    {"id": "tiff-picture-above", "name": 'Picture Above', "uses": ['You move lower and your pictures show above your head.', 'Add your own pictures.', 'News style explainers.']},
    {"id": "tiff-photo-split", "name": 'Photo Split', "uses": ['Your picture fills the top half, you talk from the bottom.', 'Add your own pictures.', "Showing what you're talking about."]},
    {"id": "tiff-photo-world", "name": 'Photo World', "uses": ['You shrink down and stand in front of your own pictures, so the whole picture shows.', 'Add your own pictures. Takes longer.', 'Big ideas and stories.']},
    {"id": "tiff-photo-grid", "name": 'Photo Grid', "uses": ["You're cut out over a grid of 4 of your pictures.", 'Add your own pictures. Takes longer.', 'Showing lots of proof.']},
    {"id": "tiff-float-up", "name": 'Float Up', "uses": ['Your pictures rise from behind your head and float above you.', 'Add your own pictures. Takes longer.', 'Naming tools or things.']},
    {"id": "tiff-photo-cluster", "name": 'Photo Cluster', "uses": ['You sit low and a cluster of your pictures fills the top.', 'Add your own pictures.', 'Wins, proof and examples.']},
    {"id": "tiff-screen-slide", "name": 'Screen Slide', "uses": ['Your screenshot slides in and fills the frame while you shrink to the corner.', 'Add your screenshots.', 'Showing your screen.']},
    {"id": "tiff-screen-zoom", "name": 'Screen Zoom', "uses": ['Your screenshot slides in and slowly pushes closer.', 'Add your screenshots.', 'Walking through a screen.']},
    {"id": "tiff-picture-stack", "name": 'Picture Stack', "uses": ['Your pictures cut in full screen with big stacked words.', 'Add your own pictures.', 'Fast explainers.']},
    {"id": "tiff-story-room", "name": 'Story Room', "uses": ['Your pictures and quote cards appear behind you as you talk.', 'Add your own pictures. Takes longer.', 'Calm stories.']},
    {"id": "tiff-then-and-now", "name": 'Then and Now', "uses": ['Your old photos play first with a year and a line, then you talk.', 'Add photos, and type one line for each.', 'Your origin story.']},
    {"id": "tiff-proof-above", "name": 'Proof Above', "uses": ['3 frames of your proof sit above your head and light up in turn.', 'Add your own pictures.', 'Wins and testimonials.']},
    {"id": "tiff-word-swap", "name": 'Word Swap', "uses": ['Your pictures replace the key word right in your captions.', 'Add your own pictures. Replaces your captions.', 'Naming tools or people.']},
    {"id": "tiff-logo-spot", "name": 'Logo Spotlight', "uses": ['A full screen spotlight on your logo or picture, then back to you.', 'Add your logo or pictures.', 'Naming tools and brands.']},
    {"id": "tiff-fast-personal", "name": 'Fast Personal', "uses": ['Your own pictures flash on the cuts with one word captions.', 'Add your own pictures. Replaces your captions.', 'Personal reels.']},
    {"id": "tiff-testimonial-wall", "name": 'Testimonial Wall', "uses": ['A wall of your testimonials scrolls behind you and one pops up big on every idea.', 'Add your testimonial screenshots. Takes longer.', 'Proof and social proof.']},
    {"id": "tiff-behind-you", "name": 'Behind You', "uses": ['Your picture floats on the wall behind your head.', 'Add your own pictures. Takes longer.', 'Talking through one thing.']},
    {"id": "tiff-phone-peek", "name": 'Phone Peek', "uses": ['A small phone pops up in the top corner showing your pictures as you talk.', 'Add your own pictures or screenshots.', 'Showing proof, posts and results.']},
    {"id": "tiff-digital-zoom", "name": "Digital Zoom", "uses": ["Punches in and out on your phrases, the whole video.",
     "Looks like you filmed it with 2 cameras.", "Works on any video where you talk to the camera."]},
    {"id": "tiff-word-pop", "name": "Word Pop", "uses": ["Your key words pop up huge in your color as you say them.", "Keeps eyes on the screen.", "Any talking video."]},
    {"id": "tiff-orbit", "name": "Orbit", "uses": ["Your key words circle your head, behind you and in front of you.", "A real wow moment at the start.", "Hooks and big ideas."]},
    {"id": "tiff-pop-out", "name": "Pop Out", "uses": ["You shrink into a phone, then break out over its edges.", "Looks like 3D.", "Talking about social media and apps."]},
    {"id": "tiff-doodles", "name": "Doodles", "uses": ["Hand-drawn arrows, circles and stars with your key words.", "Draws itself on and wiggles like a flipbook.", "Fun, friendly videos."]},
    {"id": "tiff-note-card", "name": "Note Card", "uses": ["A card in your color fills in line by line with your words.", "Feels like taking notes together.", "Lessons and lists."]},
    {"id": "tiff-glow-words", "name": "Glow Words", "uses": ["Key words fade up with a soft glow in your color.", "Moody and calm.", "Stories and big ideas."]},
    {"id": "tiff-top-banner", "name": "Top Banner", "uses": ["Your first words stay on a ribbon in your color.", "People know what it's about before they scroll.", "Tips and how-tos."]},
    {"id": "tiff-split-stage", "name": "Split Stage", "uses": ["Your words big on top, you talking below.", "Teaches while you talk.", "Tall videos filmed on your phone."]},
    {"id": "tiff-brand-frame", "name": "Brand Frame", "uses": ["A clean frame in your color and a bar that shows how far along it is.", "Looks branded with zero effort.", "Any video."]},
    {"id": "tiff-brand-stage", "name": "Brand Stage", "uses": ["You talk from a rounded card on your brand color.", "Hides a messy room edge.", "Teaching and announcements."]},
    {"id": "tiff-cinema-look", "name": "Cinema Look", "uses": ["Black bars, warm color and soft dark corners.", "Makes a phone video feel like a film.", "Stories and big moments."]},
    {"id": "tiff-zoom-punch", "name": "Zoom Punch", "uses": ["Your strongest line: a quick punch-in with a white flash.",
     "Energy at the start of any video.", "Works on any video, no cut-out needed, and it's the fastest."]},
    {"id": "tiff-number-pop", "name": "Number Pop", "uses": ["You say a number: \"$5,000\", \"3X\", \"30 days\".",
     "It counts up big in your color above your head.", "Results, prices, timelines, stats."]},
    {"id": "tiff-checklist", "name": "Checklist Ticks", "uses": ["You walk through steps or a list.",
     "A clean card shows each one and ticks it off as you say it.", "How-tos and \"3 things\" videos."]},
    {"id": "tiff-headline-behind", "name": "Headline Behind Me", "uses": ["Your key words, huge, BEHIND you.",
     "You're cut out and stand in front of the words.", "Big ideas, hooks, the one thing to remember."]},
    # batch 2, 2026-10-27
    {"id": "tiff-lower-third", "name": "Name Bar", "uses": ["Your name and brand slide in on a bar, like TV.",
     "The first seconds of any video.", "New viewers learn who you are."]},
    {"id": "tiff-quote-card", "name": "Quote Card", "uses": ["Your best sentence lands on a card, word by word, as you say it.",
     "A line worth screenshotting.", "Mindset, beliefs, hot takes."]},
    {"id": "tiff-marker-swipe", "name": "Marker Swipe", "uses": ["Your key words, big, with a marker swiped under them.",
     "The one phrase to remember.", "Hooks and big ideas."]},
    {"id": "tiff-stat-bars", "name": "Stat Bars", "uses": ["You say a number and a little bar chart grows to it.",
     "Results, growth, before and after.", "Sales, followers, hours saved."]},
    {"id": "tiff-phone-frame", "name": "Phone Frame", "uses": ["You shrink into a phone on your brand color, with a headline.",
     "Talking about an app or a post.", "Tech, tools and social media tips."]},
    {"id": "tiff-brand-backdrop", "name": "Brand Backdrop", "uses": ["The room disappears and you stand on your brand color.",
     "A messy room, or a big moment.", "Like a green screen, without the green."]},
    {"id": "tiff-spotlight", "name": "Spotlight", "uses": ["The room blurs and darkens, you stay sharp and bright.",
     "Your most serious line.", "Pulls every eye to you."]},
    {"id": "tiff-step-counter", "name": "Step Counter", "uses": ["Each step pops up with its number as you say it.",
     "Step by step how-tos.", "\"First, second, third\" videos."]},
    # 2026-10-27, Tiff's idea: hold up a blank sheet of paper while you talk
    {"id": "tiff-paper-scribble", "name": "Paper Scribble", "uses": ["Hold up a blank sheet: it gets a white outline and your words scribble onto it.",
     "Hold it up again and it flips to your next words.", "Lists, \"if you're a...\" openers, call-outs."]},
    # 2026-10-31, Tiff's green screen from her article video
    {"id": "tiff-article-screen", "name": "Green Screen Article", "members": False, "uses": ["Add a picture: an article about you, a screenshot, a website.",
     "Your room melts away and you sit small at the bottom, right in front of it.", "Press, wins, \"look what they wrote\", showing a tool."]},
]
MY_IDS = {e["id"] for e in MY_EFFECTS}


def my_fx_list():
    out = []
    for k, e in enumerate(MY_EFFECTS, 1):
        if VERSION != "dev" and e.get("members") is False:   # not tested yet: Tiff's dashboard only
            continue
        stem = e["id"]
        out.append({"n": f"Y{k}", "name": e["name"], "uses": e["uses"], "mp4": stem + ".mp4", "jpg": stem + ".jpg", "mine": True,
                    "ready": os.path.exists(os.path.join(MYFX_DIR, stem + ".jpg"))})
    for x in saved_styles():          # styles they saved from a study, newest last
        out.append({"n": "", "name": x["name"], "uses": x["uses"], "mp4": x["id"] + ".mp4", "jpg": x["id"] + ".jpg", "mine": True,
                    "saved": True, "ready": os.path.exists(os.path.join(style_dir(x["id"]), x["id"] + ".jpg"))})
    return out


def fx_list():
    """The effect cards, read from the Claude Video FX Kit on this computer. Nothing from the kit ships in
    the member copy: its license is for AI Employee Lab members, so only a computer that has the kit shows them."""
    doc = os.path.join(FX_KIT, "docs", "EFFECTS.md")
    if not os.path.exists(doc):
        return []
    out = []
    for blk in re.split(r"\n## ", open(doc).read())[1:]:
        m = re.match(r"(\d+) · (.+)", blk)
        prev = re.search(r"examples/(\S+\.mp4)", blk)
        if not m or not prev:
            continue
        uses = re.findall(r"^- (.+)$", blk.split("**Use it when:**")[1].split("**Try:**")[0], re.M) if "**Use it when:**" in blk else []
        out.append({"n": int(m.group(1)), "name": m.group(2).strip(), "uses": uses[:3], "mp4": prev.group(1),
                    "jpg": prev.group(1)[:-4] + ".jpg"})
    return out


FIX_WORDS = {"cloud": "claude", "clawed": "claude", "school": "skool", "whisper": "wispr"}


def speech_spans(src, s, e, gap=0.4, pad=0.1):
    """The stretches of [s, e] where someone is talking, on 1/30 s boundaries. Every silence longer than
    `gap` is dead air and is left out (Tiff, 2026-10-22: every silence goes, in every edit).
    2026-10-27: pauses are found by LISTENING (ffmpeg silencedetect), not from word times. A transcript
    stretched one word over 4 s of silence and lost 15 s of talking, so word times hid the dead air."""
    r = subprocess.run([FF, "-v", "info", "-ss", f"{s:.3f}", "-t", f"{e - s:.3f}", "-i", src, "-vn",
                        "-af", f"silencedetect=n=-38dB:d={gap}", "-f", "null", "-"], capture_output=True, text=True)
    quiet, start = [], None
    for line in r.stderr.splitlines():
        m = re.search(r"silence_start: ([\d.]+)", line)
        if m:
            start = float(m.group(1))
        m = re.search(r"silence_end: ([\d.]+)", line)
        if m and start is not None:
            quiet.append((start, float(m.group(1)))); start = None
    if start is not None:
        quiet.append((start, e - s))
    spans, t = [], 0.0
    for q0, q1 in quiet:
        # 2026-10-28, Tiff: "between 13 and 14 seconds it's a little tiny glitch". A breath or click between
        # two pauses came back as a 0.2 s sliver of picture that stutters. Under 0.15 s of sound is not talking
        if q0 - t >= 0.15:
            spans.append([max(0.0, t - pad), q0 + pad])
        t = q1
    if t < e - s:
        spans.append([max(0.0, t - pad), e - s])
    merged = []
    for x, y in spans:
        if merged and x <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], y)
        else:
            merged.append([x, y])
    snap = lambda v: round(v * FPS) / FPS
    return [(snap(s + x), snap(s + min(y, e - s))) for x, y in merged if snap(y) - snap(x) >= 3 / FPS]


def tighten(src, spans, dst):
    """Join only the talking parts of src into dst (30 fps, PCM sound), with a tiny fade at every join
    so the cuts don't click. Returns the new length in seconds."""
    n = len(spans)
    fc = [f"[0:v]fps={FPS},split={n}" + "".join(f"[vs{i}]" for i in range(n)),
          f"[0:a]aresample=48000,asplit={n}" + "".join(f"[as{i}]" for i in range(n))]
    for i, (x, y) in enumerate(spans):
        fc.append(f"[vs{i}]trim=start={x:.4f}:end={y:.4f},setpts=PTS-STARTPTS[v{i}]")
        fc.append(f"[as{i}]atrim=start={x:.4f}:end={y:.4f},asetpts=PTS-STARTPTS,"
                  f"afade=t=in:d=0.015,areverse,afade=t=in:d=0.015,areverse[a{i}]")
    fc.append("".join(f"[v{i}][a{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=1[v][a]")
    script = dst + ".filter.txt"
    open(script, "w").write(";\n".join(fc))
    subprocess.run([FF, "-v", "error", "-i", src, "-/filter_complex", script, "-map", "[v]", "-map", "[a]",
                    "-c:v", "libx264", "-crf", "12", "-preset", "fast", "-pix_fmt", "yuv420p", "-c:a", "pcm_s16le",
                    "-y", dst], check=True)
    os.remove(script)
    return sum(y - x for x, y in spans)


def remap(words, spans):
    """Word times on the tightened video."""
    out, off = [], 0.0
    for x, y in spans:
        for w in words:
            if x <= w["start"] < y:
                out.append({**w, "start": w["start"] - x + off, "end": min(w["end"], y) - x + off})
        off += y - x
    return out


TRIM_RULES = """You are a short-form video editor. Below are the words of a talking video with times in seconds.
Pick ONE stretch of 30 to 90 seconds that works as a reel on its own for a stranger.
It must OPEN on a scroll-stopping line, the strongest hook the speaker actually says. Strong openers:
a curiosity gap, a belief being challenged, a before and after, a bold or contrarian claim, a specific
number, a how-to promise, a question that hits the viewer's problem. Never open on "so", "um", a greeting
or mid-sentence. End where a thought lands, at the end of a sentence. Use only the speaker's own words:
never rewrite, never invent. start and end must be times from the list.
Return ONLY JSON: {"start": 0.0, "end": 0.0, "hook_line": "the opening words", "framework": "which opener it is", "why": "one sentence"}
Words:
"""

REEL_RULES = """You plan a vertical reel with {n} motion-graphics effects spread through it.
The reel is {tlen:.1f} seconds. Effects you can use (id: when to use it):
{menu}
Below are the speaker's words as sentences with times. Choose {n} DIFFERENT effects and give each one
stretch that starts at the start of a sentence and ends at the end of one, 4 to 9 seconds long.
The FIRST effect starts at 0.0. Leave at least 6 seconds of plain talking between effects.
Match each effect to what is being said (a number goes with chart-grow, a list with checklist,
a call to action at the very end with stack). Return ONLY JSON:
{{"effects": [{{"id": "effect-id", "start": 0.0, "end": 0.0, "why": "one sentence"}}]}}
Sentences:
"""


def sentences(tw):
    out, cur = [], []
    for w in tw:
        cur.append(w)
        if re.search(r"[.!?]$", w["word"].strip()) or len(cur) > 25:
            out.append((cur[0]["start"], cur[-1]["end"], " ".join(x["word"].strip() for x in cur))); cur = []
    if cur:
        out.append((cur[0]["start"], cur[-1]["end"], " ".join(x["word"].strip() for x in cur)))
    return out


def drop_retakes(tw):
    import difflib
    """2026-10-28, Tiff: "I repeat myself a couple times... I need help cutting that out first."
    A line she starts again ("In my free class," then "In my free class, build your first AI team") is a retake:
    the earlier try goes, the last take stays. A list that only shares one word ("Something you repeat.
    Something with clear steps") is not a retake. Returns [(start, end, words)] to cut, on tw's timeline."""
    phrases, cur = [], []
    for w in tw:
        cur.append(w)
        if re.search(r"[,.!?]$", w["word"].strip()):
            phrases.append(cur); cur = []
    if cur:
        phrases.append(cur)
    norm = lambda ph: [re.sub(r"[^a-z0-9']", "", x["word"].lower()) for x in ph]
    cuts = []
    if len(tw) > 3 and norm(tw)[:3] in (["one", "two", "three"], ["1", "2", "3"]):      # a count-in before the first line
        cuts.append((tw[0]["start"], tw[3]["start"], " ".join(x["word"].strip() for x in tw[:3])))
    for i, ph in enumerate(phrases[:-1]):
        a = norm(ph)
        if len(a) <= 2 and re.search(r"(\.\.\.|…)$", ph[-1]["word"].strip()):      # a trailing stammer: "rep...", "And..."
            cuts.append((ph[0]["start"], phrases[i + 1][0]["start"], " ".join(x["word"].strip() for x in ph)))
            continue
        trails = bool(re.search(r"(\.\.\.|…|-)$", ph[-1]["word"].strip()))
        for j in range(i + 1, min(i + (5 if trails else 3), len(phrases))):      # a trailing try may restart a few lines later
            b = norm([x for q in phrases[j:j + 3] for x in q])      # read on past a comma in the good take
            # 2026-10-28: a retake trails off ("..."), or is mostly said again from its start, or is a short
            # false start. Two sentences that only START alike ("If all this did was help you save five
            # hours..." / "...slim down your team"), or that END alike ("worth it to attend?" / "worth it to
            # show up?") are both kept. The first try may also lose a word ("You could..." / "If you could...")
            def lead(x, y):
                k = 0
                while k < min(len(x), len(y)) and x[k] == y[k]:
                    k += 1
                return k
            k0, k1 = lead(a, b), lead(a, b[1:])
            k, rest = (k0, b[k0:]) if k0 >= k1 else (k1, b[1 + k1:])
            # the tell is the second half: a retake says the rest again ("as a solopreneur when I was just
            # starting my business" / "when I was just starting my business"), two different sentences don't
            # ("save five or ten hours a week" / "slim down your team")
            tail = a[k:]
            again = 1.0 if not tail else difflib.SequenceMatcher(None, tail, rest[:len(tail) + 6]).find_longest_match(0, len(tail), 0, min(len(rest), len(tail) + 6)).size
            again = again if not tail else sum(m.size for m in difflib.SequenceMatcher(None, tail, rest[:len(tail) + 6]).get_matching_blocks()) / len(tail)
            # a lone word said again to start the next line ("And... And that's why", "onboarding... onboarding team")
            if (len(a) == 1 and len(a[0]) >= 2 and b[:1] == a and j == i + 1) or (len(a) == 1 and len(a[0]) >= 5 and b[:1] == a) or \
                    (len(a) >= 2 and k >= min(3, len(a)) and (trails or len(a) <= 4 or again >= 0.5)) or \
                    (len(a) >= 5 and k >= 2 and again >= 0.75):      # "There's a ton of mentors..." / "There's a bunch of mentors..."
                # only the try itself goes, never the lines between it and the good take, except the short
                # scraps of the same abandoned try ("identify rep... rep... repetitive steps.")
                cuts.append((ph[0]["start"], phrases[i + 1][0]["start"], " ".join(x["word"].strip() for x in ph)))
                for m in range(i + 1, j):      # and the short asides between ("hold on.", "The task in your business...")
                    if len(phrases[m]) <= 3 or (len(phrases[m]) <= 6 and re.search(r"(\.\.\.|…)$", phrases[m][-1]["word"].strip())):
                        cuts.append((phrases[m][0]["start"], phrases[m + 1][0]["start"], " ".join(x["word"].strip() for x in phrases[m])))
                break
    words_ = norm(tw)
    i = 0
    while i < len(words_) - 6:
        best = None
        for j in range(i + 6, min(i + 80, len(words_) - 5)):
            n = 0
            while j + n < len(words_) and i + n < j and words_[i + n] == words_[j + n]:
                n += 1
            gap = j - (i + n)      # words trailing off after the first try
            # a list shares 6 words easily ("Some people help you with the branding. Some people help you with the video"),
            # so with any words between, it takes 10 said again before it counts as starting over
            if n >= (6 if gap == 0 else 10) and gap <= 8 and (not best or n > best[1]):
                best = (j, n)
        if best:
            j, n = best
            cuts.append((tw[i]["start"], tw[j]["start"], " ".join(x["word"].strip() for x in tw[i:i + n])[:80]))
            i = j
        else:
            i += 1
    # a stutter: the same word twice in a row ("But, but what if...") loses the first one
    for w, nx in zip(tw, tw[1:]):
        x, y = re.sub(r"[^a-z']", "", w["word"].lower()), re.sub(r"[^a-z']", "", nx["word"].lower())
        if x and x == y and x not in ("that", "had", "is", "very", "really", "so", "no", "bye", "yeah") and \
                not any(a <= w["start"] < b for a, b, _ in cuts):
            cuts.append((w["start"], nx["start"], w["word"].strip()))
    # mid-sentence: the same 3 to 8 words twice in a row ("and come explore your first and come explore
    # your first useful...") lose the first time
    flat = norm(tw)
    i = 0
    while i < len(flat):
        hit = False
        for n in range(8, 2, -1):
            for g in (0, 1, 2):      # "...learning how to, AND if you're a business owner who's not learning how to"
                if g and n < 4:
                    continue
                # 2026-10-29: a LIST says the same start with a different ending each time, and each ending closes the
                # thought ("it's okay if it's free. it's okay if it's paid." / "if it happen for me, it happen for
                # you"). That is her point, not a retake, so it stays
                listy = g >= 1 and i + 2 * n + g < len(flat) and any(x not in ("um", "uh", "umm", "uhh", "hmm", "ah", "so", "like", "well", "i", "and", "") for x in flat[i + n:i + n + g])
                if i + 2 * n + g <= len(flat) and flat[i:i + n] == flat[i + n + g:i + 2 * n + g] and not listy \
                        and not any(a < tw[i + n + g]["start"] and tw[i]["start"] < b for a, b, _ in cuts):      # already cut there: keep looking
                    cuts.append((tw[i]["start"], tw[i + n + g]["start"], " ".join(x["word"].strip() for x in tw[i:i + n])))
                    i += n - 1
                    hit = True
                    break
            if hit:
                break
        i += 1
    return sorted(cuts)


def fill_skipped(job, path, tw, hole=1.2):
    """Whisper quietly drops a line said twice in a row ("In my free class, In my free class, build..."
    comes back once) and stretches the word before it over the gap ("class," lasting 2.3 s). With the pauses
    already cut, that stretch is talking nobody wrote down, so it is written down on its own and put back."""
    sys.path.insert(0, ENGINE)
    import transcribe as T
    out = []
    for w in tw:
        said = 0.25 + 0.07 * len(w["word"].strip())          # about how long the word takes to say
        if w["end"] - w["start"] - said < hole:
            out.append(w)
            continue
        a, b = w["start"] + said, w["end"]
        out.append({**w, "end": a})
        mp3 = os.path.join(job.dir, "hole.mp3")
        subprocess.run([FF, "-v", "error", "-ss", f"{a:.3f}", "-t", f"{b - a:.3f}", "-i", path, "-vn", "-ac", "1",
                        "-ar", "16000", "-c:a", "libmp3lame", "-b:a", "64k", "-y", mp3], check=True)
        res = T.groq(mp3)
        os.remove(mp3)
        if res and res[0]:
            out += [{"word": x["word"], "start": a + x["start"], "end": a + x["end"]} for x in res[0]]
    # 2026-11-03: the same thing at the very end. On a 12 minute video the transcript stopped 19 s early, and the line
    # below that ends the video after the last written word cut 73 real words. The pauses are already gone here, so
    # anything left after the last word is talking
    out = sorted(out, key=lambda x: x["start"])
    tlen = float(probe(path, count=False)["format"]["duration"])
    if out and tlen - out[-1]["end"] >= hole:
        a = out[-1]["end"]
        mp3 = os.path.join(job.dir, "hole.mp3")
        subprocess.run([FF, "-v", "error", "-ss", f"{a:.3f}", "-i", path, "-vn", "-ac", "1",
                        "-ar", "16000", "-c:a", "libmp3lame", "-b:a", "64k", "-y", mp3], check=True)
        res = T.groq(mp3)
        os.remove(mp3)
        if res and res[0]:
            out += [{"word": x["word"], "start": a + x["start"], "end": a + x["end"]} for x in res[0]]
            job.say(f"Wrote down {len(res[0])} words the transcript missed at the end")
    return sorted(out, key=lambda x: x["start"])


def quietest(path, t, before, after):
    """The quietest 30 ms between t-before and t+after: the breath between two takes. Word times can be off
    by a word, and a cut on a word time left "first" from the first take in the video (2026-10-28)."""
    import numpy as np
    a = max(0.0, t - before)
    raw = subprocess.run([FF, "-v", "error", "-ss", f"{a:.3f}", "-t", f"{before + after:.3f}", "-i", path, "-vn", "-ac", "1",
                          "-ar", "16000", "-f", "s16le", "-"], capture_output=True).stdout
    x = np.frombuffer(raw, np.int16).astype(np.float32)
    n = 480
    if len(x) < 2 * n:
        return t
    e = np.sqrt(np.convolve(x * x, np.ones(n) / n, "valid"))
    return a + (int(np.argmin(e)) + n / 2) / 16000


def murmurs(path, tlen, below=16.0, longest=0.8):
    """2026-10-28, Tiff: "That's me reading off a teleprompter." Reading to herself is a murmur: not silent enough
    for the pause cutter, but far quieter than her talking voice. Any stretch more than `below` dB under her
    usual speaking level for `longest` seconds or more is cut. Returns [(start, end, "reading")]."""
    import numpy as np
    raw = subprocess.run([FF, "-v", "error", "-i", path, "-vn", "-ac", "1", "-ar", "16000", "-f", "s16le", "-"],
                         capture_output=True).stdout
    x = np.frombuffer(raw, np.int16).astype(np.float32)
    n = 800      # 0.05 s
    if len(x) < 20 * n:
        return []
    rms = np.sqrt(np.array([(x[i:i + n] ** 2).mean() for i in range(0, len(x) - n, n)]) + 1e-6)
    db = 20 * np.log10(rms)
    talk = np.percentile(db, 70)      # her usual speaking level
    smooth = np.convolve(db, np.ones(6) / 6, "same")      # judged over 0.3 s, so a small bump doesn't break a read
    low = smooth < talk - below
    out, i = [], 0
    while i < len(low):
        if low[i]:
            j = i
            while j < len(low) and low[j]:
                j += 1
            if (j - i) * 0.05 >= longest:
                out.append((i * 0.05 + 0.05, j * 0.05 - 0.05, "reading"))
            i = j
        else:
            i += 1
    return out


def without(tlen, cuts):
    """The parts of a 0..tlen timeline that are left after the cuts, on whole frames so picture and sound
    stay the same length (cuts between frames left a video 2 frames short of its sound)."""
    snap = lambda x: round(x * FPS) / FPS
    cuts = [(snap(a), snap(b), w) for a, b, w in cuts]
    tlen = snap(tlen)
    keep, t = [], 0.0
    for a, b, _ in sorted(cuts):
        if a - t >= 0.25:        # never leave a sliver between two cuts: it stutters
            keep.append((t, a))
        t = max(t, b)
    if tlen - t >= 0.25:
        keep.append((t, tlen))
    return keep


CLEANUP_SECS_PER_SEC = 1.4
CLEAN_MAX_SECS, CLEAN_SPACE_X = 600, 0      # her own copy changes these, in the start block at the bottom


def join_videos(paths, dst):
    """Join videos into one, in the order given. Same kind of video (size, frame rate, sound): joined as they are,
    in seconds. Different kinds, or a join that doesn't count right: made into one video at the biggest size.
    Counted after either way: the length must be the parts added up, and the sound as long as the picture."""
    def kind(p):
        i = json.loads(subprocess.run([FP, "-v", "error", "-show_entries", "format=duration:stream=codec_type,codec_name,width,height,"
                                       "r_frame_rate,pix_fmt,sample_rate,channels,duration:stream_side_data=rotation",
                                       "-of", "json", p], capture_output=True, text=True).stdout or "{}")
        v = next((x for x in i.get("streams", []) if x.get("codec_type") == "video"), None)
        a = next((x for x in i.get("streams", []) if x.get("codec_type") == "audio"), None)
        if not v or not a:
            raise RuntimeError(f"{os.path.basename(p)} has no {'picture' if not v else 'sound'}")
        rot = abs(int(float(((v.get("side_data_list") or [{}])[0]).get("rotation", 0) or 0))) % 180
        w, h = (int(v["height"]), int(v["width"])) if rot == 90 else (int(v["width"]), int(v["height"]))
        sig = (v["codec_name"], v["width"], v["height"], rot, v["r_frame_rate"], v.get("pix_fmt"),
               a["codec_name"], a.get("sample_rate"), a.get("channels"))
        return {"w": w, "h": h, "sig": sig, "secs": float(v.get("duration") or i["format"]["duration"])}
    ks = [kind(p) for p in paths]
    want = sum(k["secs"] for k in ks)

    def counts_right():
        i = probe(dst)
        v, a = stream(i, "video"), stream(i, "audio")
        d = float(i["format"]["duration"])
        return abs(d - want) <= 0.15 * len(paths) + 0.2 and abs(float(a.get("duration") or d) - float(v.get("duration") or d)) <= 0.2

    if len({k["sig"] for k in ks}) == 1:
        lst = dst + ".txt"
        open(lst, "w").write("".join("file '" + p.replace("'", "'\\''") + "'\n" for p in paths))
        r = subprocess.run([FF, "-v", "error", "-f", "concat", "-safe", "0", "-i", lst, "-map", "0:v:0", "-map", "0:a:0",
                            "-c", "copy", "-movflags", "+faststart", "-y", dst], capture_output=True, text=True)
        os.remove(lst)
        if r.returncode == 0 and counts_right():
            return "joined as they are"
    tall = ks[0]["h"] >= ks[0]["w"]
    same = [k for k in ks if (k["h"] >= k["w"]) == tall] or ks
    W, H = max(k["w"] for k in same), max(k["h"] for k in same)
    W, H = W - W % 2, H - H % 2
    fc = []
    for i, k in enumerate(ks):
        fc.append(f"[{i}:v]fps={FPS},scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=black,"
                  f"setsar=1,format=yuv420p,trim=end={k['secs']:.4f},setpts=PTS-STARTPTS[v{i}]")
        fc.append(f"[{i}:a]aresample=48000,aformat=sample_fmts=s16:channel_layouts=stereo,apad,atrim=end={k['secs']:.4f},"
                  f"asetpts=PTS-STARTPTS[a{i}]")
    fc.append("".join(f"[v{i}][a{i}]" for i in range(len(ks))) + f"concat=n={len(ks)}:v=1:a=1[v][a]")
    vt = sys.platform == "darwin" and "h264_videotoolbox" in subprocess.run([FF, "-hide_banner", "-encoders"], capture_output=True, text=True).stdout
    rate = max(12, min(60, round(24 * W * H / (1080 * 1920))))      # an in-between copy: 24M at 1080p is plenty, and her disk is small
    codec = ["-c:v", "h264_videotoolbox", "-b:v", f"{rate}M"] if vt else ["-c:v", "libx264", "-crf", "14", "-preset", "veryfast"]
    subprocess.run([FF, "-v", "error", *sum((["-i", p] for p in paths), []), "-filter_complex", ";".join(fc),
                    "-map", "[v]", "-map", "[a]", *codec, "-pix_fmt", "yuv420p", "-c:a", "pcm_s16le", "-y", dst], check=True)
    if not counts_right():
        raise RuntimeError("the joined video came out the wrong length")
    return f"made into one {W}x{H} video"


def listen_again(job, src, out, kept, runs, to_source, to_final):
    """For each run of words that looks missing from the finished video: listen to just those seconds again, in the
    original and in the finished video, with the same reader. Heard in the finished video: not missing. Not heard in
    the original either: never really said (a noise read as words), nothing was cut. Otherwise it stays missing."""
    sys.path.insert(0, ENGINE)
    import transcribe as T
    nrm1 = lambda x: re.sub(r"[^a-z0-9']", "", x.lower())
    noise = {"mwah", "muah", "mm", "mmm", "hmm", "ah", "oh", "ha", "haha", "um", "uh", "huh", "whoa", "wow", "okay", "ok"}

    def hear(path, a, b):
        clip = os.path.join(job.dir, "listen-again.mp3")
        try:
            subprocess.run([FF, "-v", "error", "-ss", f"{max(0.0, a - 1.5):.2f}", "-t", f"{b - a + 3:.2f}", "-i", path, "-vn",
                            "-ac", "1", "-ar", "16000", "-c:a", "libmp3lame", "-b:a", "64k", "-y", clip], check=True)
            res = T.groq(clip) or T.local(clip)
        except Exception:
            res = None
        finally:
            if os.path.exists(clip):
                os.remove(clip)
        return [nrm1(x["word"]) for x in (res[0] if res else []) if nrm1(x["word"])]

    def has(heard, want):
        k = 0
        for h in heard:
            if k < len(want) and h == want[k]:
                k += 1
        return k >= len(want) - (1 if len(want) >= 4 else 0)

    still = []
    for i1, i2 in runs:
        words = [nrm1(w["word"]) for w in kept[i1:i2]]
        text = " ".join(words)
        want = [x for x in words if x not in noise]
        if not want:
            job.say(f"   “{text}” is a sound, not words, so it doesn’t count")
            continue
        a, b = kept[i1]["start"], kept[i2 - 1]["end"]
        if has(hear(out, to_final(a), to_final(b)), want):
            job.say(f"   listened again: “{text}” is in the finished video")
            continue
        if not has(hear(src, to_source(a), to_source(b)), want):
            job.say(f"   listened again: “{text}” isn’t in your original either, so nothing was cut there")
            continue
        still.append(text)
    return still


def clean_sound(src, secs, dst):
    """The whole video's sound as a WAV, with DeepFilterNet's noise removal when it's set up. True if cleaned."""
    raw = dst[:-4] + "-raw.wav"
    ch = subprocess.run([FP, "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=channels", "-of", "csv=p=0", src],
                        capture_output=True, text=True).stdout.strip()
    ch = min(int(ch) if ch.isdigit() else 1, 2)
    subprocess.run([FF, "-v", "error", "-i", src, "-t", f"{secs:.3f}", "-map", "0:a:0", "-vn", "-ac", str(ch),
                    "-af", "afade=t=in:d=0.02,areverse,afade=t=in:d=0.02,areverse", "-ar", "48000",
                    "-c:a", "pcm_s16le", "-y", raw], check=True)
    df = deep_filter()
    if not df:
        os.replace(raw, dst)
        return False
    work = tempfile.mkdtemp(prefix="cleansound_", dir=os.path.dirname(dst))
    try:
        # -D lines the cleaned sound back up with the lips, as clean_audio.py does
        subprocess.run([df, "-D", "-a", "100", "-o", work, raw], check=True, capture_output=True)
        subprocess.run([FF, "-v", "error", "-i", os.path.join(work, os.path.basename(raw)), "-af", f"apad,atrim=0:{secs:.6f}",
                        "-ar", "48000", "-c:a", "pcm_s16le", "-y", dst], check=True)
    finally:
        shutil.rmtree(work, ignore_errors=True)
        os.remove(raw)
    return True


def tighten_sound(src, spans, dst):
    """tighten() for the sound alone, with the same tiny fade at every join. Returns the new length in seconds."""
    n = len(spans)
    fc = [f"[0:a]aresample=48000,asplit={n}" + "".join(f"[as{i}]" for i in range(n))]
    for i, (x, y) in enumerate(spans):
        fc.append(f"[as{i}]atrim=start={x:.4f}:end={y:.4f},asetpts=PTS-STARTPTS,"
                  f"afade=t=in:d=0.015,areverse,afade=t=in:d=0.015,areverse[a{i}]")
    fc.append("".join(f"[a{i}]" for i in range(n)) + f"concat=n={n}:v=0:a=1[a]")
    script = dst + ".filter.txt"
    open(script, "w").write(";\n".join(fc))
    subprocess.run([FF, "-v", "error", "-i", src, "-/filter_complex", script, "-map", "[a]", "-c:a", "pcm_s16le", "-y", dst], check=True)
    os.remove(script)
    return sum(y - x for x, y in spans)


def on_source_spans(keep, spans):
    """The kept parts of the pause-cut timeline, as parts of the video they gave. A kept part that runs across a
    cut pause becomes two parts. On whole frames, so picture and sound stay the same length."""
    snap = lambda v: round(v * FPS) / FPS
    bounds, off = [], 0.0
    for x, y in spans:
        bounds.append((off, off + (y - x), x))
        off += y - x
    out = []
    for a, b in keep:
        for t0, t1, x in bounds:
            lo, hi = max(a, t0), min(b, t1)
            if hi - lo > 1e-6:
                p, q = snap(x + lo - t0), snap(x + hi - t0)
                if out and abs(out[-1][1] - p) < 1e-6:
                    out[-1] = (out[-1][0], q)
                elif q - p >= 1 / FPS - 1e-6:
                    out.append((p, q))
    return out


def render_once(src, wav, spans, dst, out4k=None, W4=0, H4=0):
    """Cut the picture ONCE from the video they gave and lay the finished sound under it. Makes the editing copy
    (dst, same settings as before) and, when asked, the 4K at the same time from the same frames. Returns the run."""
    n = len(spans)
    fc = [f"[0:v]fps={FPS},split={n}" + "".join(f"[vs{i}]" for i in range(n))]
    for i, (x, y) in enumerate(spans):
        fc.append(f"[vs{i}]trim=start={x:.4f}:end={y:.4f},setpts=PTS-STARTPTS[v{i}]")
    fc.append("".join(f"[v{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=0[cat]")
    if out4k:
        fc.append("[cat]split=2[vm][vk]")
        fc.append(f"[vk]scale={W4}:{H4}:flags=lanczos,unsharp=5:5:0.6:5:5:0.0[v4]")
    script = dst + ".filter.txt"
    open(script, "w").write(";\n".join(fc))
    cmd = [FF, "-v", "error", "-i", src, "-i", wav, "-/filter_complex", script,
           "-map", "[vm]" if out4k else "[cat]", "-map", "1:a", "-c:v", "libx264", "-crf", "12", "-preset", "fast",
           "-pix_fmt", "yuv420p", "-c:a", "pcm_s16le", "-y", dst]
    if out4k:
        cmd += ["-map", "[v4]", "-map", "1:a", *fast_4k_codec(), "-pix_fmt", "yuv420p", "-profile:v", "high",
                "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-y", out4k]
    return subprocess.Popen(cmd, stderr=subprocess.PIPE, text=True)


def run_cleanup(job, hand_back=False):
    """2026-10-28, Tiff: a "clean it up first" step before any template. Clean sound, every pause cut, every
    retake cut (her last take stays). The cleaned video becomes the job's video, so whatever she picks next
    starts from it. hand_back: also give it to her as a finished video."""
    job.original = getattr(job, "original", None) or job.src       # a fix redoes it from the video they gave
    info = probe(job.src, count=False)
    secs = float(info["format"]["duration"])
    if secs > CLEAN_MAX_SECS:
        job.say("Clean it up first is for videos under 10 minutes, so this long one goes as it is")
        return
    need = max(1.5e9, os.path.getsize(job.src) * CLEAN_SPACE_X)
    if shutil.disk_usage(HOME).free < need:
        raise RuntimeError(f"Free up {need / 1e9:.1f} GB of disk space first.")
    full = os.path.join(job.dir, "clean-full.wav")
    job.state = "cleaning the sound"
    if clean_sound(job.src, secs, full):
        job.say("Cleaned the background noise out of the sound")
    job.state = "cutting out the pauses"
    spans = speech_spans(full, 0.0, secs)
    if not spans:
        raise RuntimeError("Couldn't hear any talking in this video. Try a video where you speak.")
    # 2026-10-28, Tiff's notes on her ads: some moments stay in even when quiet ("the lights did turn off when
    # I said that... make it a moment where it pauses"), some lines go by name, some stretches go by time.
    # notes = {"keep": [[a, b]], "cut": ["words to cut", "words@2" for the 2nd time], "cut_at": [[a, b]]},
    # times in seconds of the video they gave
    notes = getattr(job, "notes", None) or {}
    snap = lambda x: round(x * FPS) / FPS
    for k in notes.get("keep", []):
        if not isinstance(k, str):      # a kept moment in seconds; kept WORDS are protected after the transcript
            spans = sorted(spans + [(snap(k[0]), snap(k[1]))])
    merged = []
    for x, y in spans:
        if merged and x <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], y))
        else:
            merged.append((x, y))
    spans = merged

    def on_tight(t):
        """Where a moment of their video lands once the pauses are cut."""
        off = 0.0
        for x, y in spans:
            if t < x:
                return off
            if t <= y:
                return off + t - x
            off += y - x
        return off
    tight = os.path.join(job.dir, "clean-tight.wav")
    tlen = tighten_sound(full, spans, tight)
    job.say(f"Cut out the pauses: {secs:.1f} s down to {tlen:.1f} s")
    job.state = "finding your repeats and ums"
    sys.path.insert(0, ENGINE)
    import transcribe as T
    plain, T.PROMPT = T.PROMPT, "Umm, uh, so, like, um... let me, uh, think. Hmm, okay. " + T.PROMPT   # makes it write the ums down
    try:
        tw, _, _ = transcribe(job, "auto", tight)
    finally:
        T.PROMPT = plain
    tw = fill_skipped(job, tight, tw)

    def on_source(t):
        off = 0.0
        for x, y in spans:
            if t <= off + (y - x):
                return x + t - off
            off += y - x
        return spans[-1][1]
    job.source_words = [{"word": w["word"], "start": round(on_source(w["start"]), 2)} for w in tw]
    # the front of a cut may only move back 0.1 s: a wider window clipped "are limitless" off the line before
    # and the end may only move 0.15 s forward: with the pauses gone there is often no breath there, and a wider
    # window landed inside the next word ("I feel you" came out "feel you", 2026-10-28)
    retakes = [(quietest(tight, a, 0.1, 0.15), quietest(tight, b, 0.25, 0.15), w) for a, b, w in drop_retakes(tw)]
    for a, b, words in retakes:
        job.say(f'Cut a repeat at {a:.1f} s, kept your next take: "{words[:60]}"')
    ums = [(w["start"], min(nx["start"], w["start"] + 0.8), w["word"].strip()) for w, nx in zip(tw, tw[1:] + [{"start": tlen}])
           if re.fullmatch(r"u+m+|u+h+|e+r+m*|h+m+|a+h+|mm+", re.sub(r"[^a-z]", "", w["word"].lower()))]
    if ums:
        job.say(f"Cut {len(ums)} um(s) and uh(s)")
    # a murmur is only a murmur where no real word was heard: on 2026-10-28 a soft "doesn't mean you should."
    # was cut as reading, and it was the point of the line
    heard = [(w["start"], w["end"]) for w in tw if w["word"].strip() and not any(w["start"] == u[0] for u in ums)]
    reads = [r for r in murmurs(tight, tlen) if not any(min(r[1], b) - max(r[0], a) > 0.05 for a, b in heard)]
    for a, b, _ in reads:
        job.say(f"Cut a quiet murmur at {a:.1f} to {b:.1f} s, like reading off a screen")
    cuts = sorted(retakes + ums + reads)
    keeps = [(on_tight(a), on_tight(b)) for a, b in (k for k in notes.get("keep", []) if not isinstance(k, str))]
    nw0 = [re.sub(r"[^a-z0-9']", "", w["word"].lower()) for w in tw]
    for k in notes.get("keep", []):      # words to protect: no cut may touch them
        if isinstance(k, str):
            want = [x for x in re.sub(r"[^a-z0-9' ]", " ", k.lower()).split() if x]
            for i in range(len(nw0) - len(want) + 1):
                if want and nw0[i:i + len(want)] == want:
                    keeps.append((tw[i]["start"] - 0.25, tw[i + len(want) - 1]["end"] + 0.25))      # word times run late
    # a kept moment is never cut: a cut that runs into one is trimmed back to its edge, not thrown away
    # (throwing it away left a whole restart in, 2026-10-28)
    trimmed = []
    for a, b, w in cuts:
        for ka, kb in keeps:
            if a < kb and ka < b:
                if a < ka:
                    b = min(b, ka)
                else:
                    a = max(a, kb)
        if b - a >= 0.1:
            trimmed.append((a, b, w))
    cuts = trimmed
    for a, b in notes.get("cut_at", []):
        cuts.append((on_tight(a), on_tight(b), f"{a:.1f}-{b:.1f} s"))
        job.say(f"Cut {a:.1f} to {b:.1f} s as you asked")
    nw = [re.sub(r"[^a-z0-9']", "", w["word"].lower()) for w in tw]
    for spec in notes.get("cut", []):
        words, nth = (spec.rsplit("@", 1) + ["1"])[:2] if "@" in spec else (spec, "1")
        want = [x for x in (re.sub(r"[^a-z0-9' ]", " ", words.lower())).split() if x]
        hits = [i for i in range(len(nw) - len(want) + 1) if want and nw[i:i + len(want)] == want]
        if len(hits) >= int(nth):
            i = hits[int(nth) - 1]
            end = tw[i + len(want)]["start"] if i + len(want) < len(tw) else tlen
            cuts.append((quietest(tight, tw[i]["start"], 0.1, 0.1), quietest(tight, end, 0.15, 0.15), words))
            job.say(f'Cut "{words}" as you asked')
        else:
            job.say(f'   couldn\'t find "{words}" to cut, check this one by hand')
    cuts = sorted(cuts)
    if tw:      # it starts on the first word and ends just after the last (a scrap before the first word stuttered)
        cuts = [(0.0, max(0.0, tw[0]["start"] - 0.08), "the start")] + cuts + ([(min(tlen, tw[-1]["end"] + 0.35), tlen, "the end")] if tlen - tw[-1]["end"] < 1.5 else [])   # more than that left is talking nobody wrote down, so it stays
    keep = without(tlen, cuts) if cuts else [(0.0, tlen)]
    if not cuts:
        job.say("No repeats or false starts found")
    src_spans = on_source_spans(keep, spans)
    final = os.path.join(job.dir, "clean-final.wav")
    tlen = tighten_sound(full, src_spans, final)
    done = os.path.join(job.dir, "cleaned.mov")
    v = stream(info, "video")
    w0, h0 = int(v["width"]), int(v["height"])
    # 2026-10-28, Tiff: "It can't just be blurry, ever." 4K, the long side 3840, same shape as theirs
    W4, H4 = (2160, round(2160 * h0 / w0 / 2) * 2) if h0 >= w0 else (round(2160 * w0 / h0 / 2) * 2, 2160)
    out = None
    if hand_back:
        name = re.sub(r"[^\w &-]", "", os.path.splitext(job.name)[0]).strip()[:50]
        out = os.path.join(job.dir, "out", f"{name} - Cleaned 4K.mp4")
    job.state = "making your video"
    run = render_once(job.src, final, src_spans, done, out, W4, H4)
    if hand_back:
        # 2026-10-28, Tiff: "Check your video output when you do this and learn from it." The words of the exact
        # finished sound, written down while the picture is made, held against what she said minus the cuts
        import difflib
        nrm = lambda ws: [re.sub(r"[^a-z0-9']", "", x.lower()) for x in ws if re.sub(r"[^a-z0-9']", "", x.lower())]
        meant = nrm(w["word"] for w in tw if not any(a <= w["start"] < b for a, b, _ in cuts))
        try:
            heard_w, _, _ = transcribe(job, "auto", final)
        except Exception:
            run.kill()
            raise
    err = run.communicate()[1]
    if run.returncode:
        raise RuntimeError("Making the video stopped: " + (err or "")[-300:])
    for f in (full, tight, final, done + ".filter.txt"):
        if os.path.exists(f):
            os.remove(f)
    job.src, job.cleaned = done, True
    if hand_back:
        ok, checks = ledger(out, f"{W4}x{H4}", tlen)
        mbps = os.path.getsize(out) * 8 / max(tlen, 0.1) / 1e6
        checks["sharp enough to upload (Mbps)"] = [round(mbps, 1), ">= 8", mbps >= 8]
        ok = ok and mbps >= 8
        job.clean_tw = heard_w
        heard = nrm(w["word"] for w in heard_w)
        sm = difflib.SequenceMatcher(None, meant, heard)
        match = round(100 * sm.ratio())
        diffs = [" ".join(meant[i1:i2]) + " -> " + " ".join(heard[j1:j2]) for op, i1, i2, j1, j2 in sm.get_opcodes() if op != "equal"]
        for d in diffs[:6]:
            job.say(f"   check this spot: {d}")
        # a 9 word clip drops under 95% on one misheard word ("as free" for "it's free"), so a short one
        # may be off by one word
        changed = sum(max(i2 - i1, j2 - j1) for op, i1, i2, j1, j2 in sm.get_opcodes() if op != "equal")
        # 2026-10-28: "I feel you" and "You don't need to pay the copywriter $3,000 a month" went missing from a
        # 180 word video and it still scored 96%. Three or more of their words in a row missing fails, by name
        runs = [(i1, i2) for op, i1, i2, j1, j2 in sm.get_opcodes() if (op == "delete" and i2 - i1 >= 2) or (op == "replace" and (i2 - i1) - (j2 - j1) >= 2)]
        lost = [" ".join(meant[i1:i2]) for i1, i2 in runs]
        kept_w = [w for w in tw if not any(a <= w["start"] < b for a, b, _ in cuts) and re.sub(r"[^a-z0-9']", "", w["word"].lower())]
        if runs and len(kept_w) == len(meant):

            def on_final(t):
                off = 0.0
                for x, y in keep:
                    if t < x:
                        return off
                    if t <= y:
                        return off + t - x
                    off += y - x
                return off
            lost = listen_again(job, job.original, out, kept_w, runs, on_source, on_final)
        for x in lost:
            job.say(f"   MISSING from the video: \"{x}\"")
        checks["none of your lines missing"] = [len(lost), "0", not lost]
        good = (match >= 90 or (len(meant) < 20 and changed <= 1)) and not lost
        checks["says what you said (minus the cuts)"] = [f"{match}%", ">= 90% (short clip: 1 word)", good]
        ok = ok and good
        checks["repeats and ums cut"] = [len(retakes) + len(ums), "any", True]
        sheet = out[:-4] + " frames.jpg"
        contact_sheet(out, sheet)
        job.shorts.append({"file": os.path.basename(out), "sheet": os.path.basename(sheet), "ok": ok, "seconds": round(tlen, 1),
                           "from": "0:00", "hook": [], "why": f"Cleaned: sound, pauses, {len(retakes)} repeat(s) and {len(ums)} um(s) cut, in 4K. Pick a template next to keep going.",
                           "checks": checks})
        job.save()
        try:
            add_captions(job)
        except Exception as e:
            job.say(f"   Captions didn't finish ({str(e)[:120]}). Your cleaned video is still ready.")


def add_captions(job):
    """2026-11-11, Tiff: "we all need the captions". The cleaned video also comes back with captions in their
    brand, ready to post. It uses the words the cleanup already checked, so nothing is heard twice."""
    words = getattr(job, "clean_tw", None) or []
    if not words:
        job.say("   No words were heard, so there is no captions version this time")
        return
    job.state = "adding your captions"
    tlen = float(probe(job.src, count=False)["format"]["duration"])
    wf = os.path.join(job.dir, "clean_words.json")
    json.dump({"words": [{"word": w["word"].strip(), "start": w["start"], "end": w["end"]} for w in words]}, open(wf, "w"))
    os.environ["CME_WORDS"] = wf
    try:
        fin, heard = caption_part(job, job.src, 0.0, tlen, 1)
    finally:
        os.environ.pop("CME_WORDS", None)
    name = re.sub(r"[^\w &-]", "", os.path.splitext(job.name)[0]).strip()[:50]
    out = os.path.join(job.dir, "out", f"{name} - Captions.mp4")
    os.replace(fin, out)
    brand_finish(job, out)
    ok, checks = ledger(out, "1080x1920", tlen)
    import difflib
    nrm = lambda x: [FIX_WORDS.get(y, y) for y in re.sub(r"[^a-z0-9 ]", " ", x.lower()).split()]
    said = " ".join(w["word"] for w in words)
    if len(said.split()) >= 8:
        match = round(100 * difflib.SequenceMatcher(None, nrm(said), nrm(heard)).ratio())
        checks["captions match the words"] = [f"{match}%", ">= 80%", match >= 80]
        ok = ok and match >= 80
    sheet = out[:-4] + " frames.jpg"
    contact_sheet(out, sheet)
    job.shorts.append({"file": os.path.basename(out), "sheet": os.path.basename(sheet), "ok": ok, "seconds": round(tlen, 1),
                       "from": "0:00", "hook": [], "why": "Cleaned and captioned in your brand, ready to post.", "checks": checks})
    job.say(f"Captions {'PASSED' if ok else 'FAILED'} the checks")
    job.save()


FIX_RULES = """A person cleaned up their talking video and is telling you, in their own words, what to fix.
Below are the words of their ORIGINAL video with the second each word starts. Turn their notes into edits.
Return ONLY JSON with these keys:
"cut": a list of exact word runs to take out, copied word for word from the transcript (add "@2" to the end for
the second time those words appear, "@3" for the third);
"keep": a list of [start, end] seconds of moments that must stay in even if quiet or repeated (a reaction, the
lights going off, a pause they want people to see);
"cut_at": a list of [start, end] seconds to take out (looking down, reading, a stretch with no words);
"summary": one short plain sentence saying what you will change.
Only use words and times that are in the transcript. If a note is unclear, leave it out and say so in summary.
Their notes:
{said}

Words of their original video:
"""


def fix_cleanup(job, said):
    """2026-10-28, Tiff: "After they clean it up, it should be like a little spot where they can talk to it and
    give it feedback with Wispr Flow, and then it redoes the edit." Their notes become cut / keep / cut_at, added
    to any notes from before, and the cleanup runs again from the video they gave."""
    words = getattr(job, "source_words", None)
    if not words:
        raise RuntimeError("Clean the video first, then tell it what to fix.")
    body = " ".join(f"{w['word'].strip()}[{w['start']:.1f}]" for w in words)[:14000]
    plan = ask_groq(FIX_RULES.replace("{said}", said.strip()[:3000]) + body)
    notes = getattr(job, "notes", None) or {}
    for k in ("cut", "keep", "cut_at"):
        notes[k] = (notes.get(k) or []) + [x for x in (plan.get(k) or []) if x]
    job.notes = notes
    job.say("Your fixes: " + str(plan.get("summary", ""))[:300])
    job.src, job.cleaned = job.original, False
    job.shorts = [x for x in job.shorts if "Cleaned" not in x["file"]]
    run_cleanup(job, hand_back=True)


def prepare_talking(job, opts):
    """Clean the sound, cut every silence, optionally keep only the best 30 to 90 s that opens on a hook,
    and write down the words of what's left. Returns (tight.mov, length, words on that timeline)."""
    info = probe(job.src, count=False)
    v = stream(info, "video")
    secs = float(info["format"]["duration"])
    os.environ.pop("CME_WORDS", None)
    if getattr(job, "cleaned", False) and getattr(job, "clean_tw", None) and not opts.get("trim") and secs <= 180:
        tight = os.path.join(job.dir, f"tight-{job.id}.mov")
        shutil.copy(job.src, tight)
        job.spans = 1
        wf = os.path.join(job.dir, "clean_words.json")
        json.dump({"words": [{"word": w["word"].strip(), "start": w["start"], "end": w["end"]} for w in job.clean_tw]}, open(wf, "w"))
        os.environ["CME_WORDS"] = wf      # the finisher's captions use these too, when nothing moved the timeline
        return tight, secs, job.clean_tw
    job.say(f"Got it: {os.path.basename(job.src)}, {secs:.0f} s, {v['width']}x{v['height']}")
    if shutil.disk_usage(HOME).free < 1.5e9:
        raise RuntimeError("Free up 1.5 GB of disk space first.")
    if secs > 600:
        raise RuntimeError("Effects are for short videos (under 10 minutes). Use Long Video to Shorts first, then put an effect on a short.")
    full = os.path.join(job.dir, "full.mov")
    job.state = "cleaning the sound"
    cut(job.src, 0, secs, full)
    if getattr(job, "cleaned", False):
        pass      # Clean it up first already cleaned this sound; twice would dull the voice
    elif deep_filter():
        subprocess.run([sys.executable, CLEANER, full], check=True, capture_output=True)
        os.replace(full[:-4] + " CLEAN.mov", full)
        job.say("Cleaned the background noise out of the sound")
    else:
        job.say("   clean sound is not set up yet, so the sound was left as it is")
    job.state = "cutting out the pauses"
    flen = float(probe(full, count=False)["format"]["duration"])
    spans = speech_spans(full, 0.0, flen)
    if not spans:
        raise RuntimeError("Couldn't hear any talking in this video. Try a video where you speak.")
    tight = os.path.join(job.dir, f"tight-{job.id}.mov")
    tlen = tighten(full, spans, tight)
    os.remove(full)
    job.spans = len(spans)
    job.say(f"Cut out the pauses: {secs:.1f} s down to {tlen:.1f} s ({len(spans)} talking parts kept)")
    job.state = "writing down every word"
    tw, _, _ = transcribe(job, "auto", tight)
    if len(tw) < 8:
        raise RuntimeError("There isn't enough talking in this video for an effect. Try a video where you speak.")
    if opts.get("trim") and tlen > 90:
        # 2026-10-27, Tiff: effects land on a 30 to 90 s clip. When the person says yes, find their best
        # 30 to 90 s, opening on their strongest hook line (hook frameworks, their own words only).
        job.state = "finding your best 30 to 90 seconds"
        body = "\n".join(f"[{x:.1f}-{y:.1f}] {t}" for x, y, t in sentences(tw))[:14000]
        pick_ = ask_groq(TRIM_RULES + body)
        a0, b0 = float(pick_.get("start", 0)), float(pick_.get("end", 0))
        if not (0 <= a0 < b0 <= tlen + 0.5 and 25 <= b0 - a0 <= 95):
            a0, b0 = 0.0, min(tlen, 75.0)
        a0, b0 = max(0.0, a0 - 0.05), min(tlen, b0 + 0.15)
        trimmed = os.path.join(job.dir, "trim.mov")
        cut(tight, a0, b0, trimmed)
        os.replace(trimmed, tight)
        tlen = float(probe(tight, count=False)["format"]["duration"])
        tw = [{**w, "start": w["start"] - a0, "end": min(w["end"], b0) - a0} for w in tw if a0 <= w["start"] < b0]
        job.say(f"Kept your best {tlen:.0f} s, from {a0:.0f} s, opening on: \"{pick_.get('hook_line', '')[:80]}\" "
                f"({pick_.get('framework', 'hook')})")
    elif tlen > 180:     # never caption and render a long talk as one reel; keep about the first 90 s
        stop = quiet_point(tight, 90.0)
        trimmed = os.path.join(job.dir, "tight90.mov")
        cut(tight, 0, stop, trimmed)
        os.replace(trimmed, tight)
        tlen = float(probe(tight, count=False)["format"]["duration"])
        tw = [w for w in tw if w["start"] < tlen]
        job.say(f"Long video, so this one keeps the first {tlen:.0f} s")
    return tight, tlen, tw


EFFECT_FILLER = {"get", "get it", "got it", "you", "your", "guys", "you guys", "that", "so", "this", "just", "actually", "it", "want",
                 "the", "and", "can", "do", "there", "here", "free", "go", "like", "really", "okay"}
EFFECT_TITLE = {"cover-story": "title", "glass-type": "word", "chart-grow": "pill", "liquid-glass-graph": "label", "match-cut": "word"}


def strong_word(lines):
    """The longest real word said here, so a big title names something."""
    words = [w for w in re.findall(r"[A-Za-z][A-Za-z']+", lines) if w.lower() not in EFFECT_FILLER
             and w.lower() not in ("actually", "without", "because", "really", "something", "everything", "learn", "better", "every", "those", "these", "their", "there", "about", "would", "could", "should", "videos")]
    return max(words, key=len).upper() if words else ""


def effect_words(effect_id, cfg, lines):
    """2026-11-03: a giant "GET", a phone full of a stranger's ads and "48.2K" likes all passed every check. Words on
    screen have to mean something and numbers on screen have to be true."""
    key = EFFECT_TITLE.get(effect_id)
    if key and (str(cfg.get(key, "")).strip(" .,!?").lower() in EFFECT_FILLER):
        word = strong_word(lines)
        if word:
            cfg[key] = word
    for k in ("labels", "titles"):
        if isinstance(cfg.get(k), list):
            cfg[k] = [t for t in cfg[k] if str(t).strip(" .,!?").lower() not in EFFECT_FILLER]
    if effect_id == "frame-break":
        cfg.update(username=brand().get("handle") or re.sub(r"[^a-z0-9_.]", "", brand().get("name", "").lower()) or "", likes="", comments="")
    if effect_id == "couch-wall":
        cfg["showViews"] = False
    if effect_id == "orbit":
        cfg["views"] = False
    if effect_id == "ui-world":
        cfg.pop("appName", None)
        cfg.pop("placeholder", None)
    if effect_id == "phone-mockup":
        cfg["app"] = {**(cfg.get("app") or {}), "name": "Claude", "status": "Online", "avatarColor": "#" + brand()["accent"]}
        cfg["card"] = {**(cfg.get("card") or {}), "tiles": []}
    # 2026-11-03: "6 hrs to 15 min" and a 64% growth line went on a video that said neither. They are the kit's samples.
    said = [x.strip() for x in re.findall(r"\$?\d[\d,.]*\d?(?:\s?(?:%|x\b|k\b|hours?\b|hrs?\b|minutes?\b|mins?\b|days?\b|weeks?\b|months?\b|years?\b))?", lines, re.I)]
    if effect_id == "over-the-shoulder-zoom" and len(said) < 2:
        raise RuntimeError("Over-the-Shoulder Zoom needs you to say two numbers, a before and an after (like 6 hours and 15 minutes). Try another effect for this video.")
    if effect_id in ("liquid-glass-graph", "chart-grow") and not said:
        raise RuntimeError(("Liquid Glass Graph" if effect_id == "liquid-glass-graph" else "Chart Grow") + " needs you to say a number (like $5,000, 3X or 30 days). Try another effect for this video.")
    if effect_id == "liquid-glass-graph":
        n = re.search(r"\d[\d,.]*\d?", said[0]).group(0).replace(",", "")
        cfg.update({"from": 0, "to": float(n), "prefix": "$" if said[0].startswith("$") else "", "suffix": said[0][said[0].index(re.search(r"\d[\d,.]*\d?", said[0]).group(0)) + len(re.search(r"\d[\d,.]*\d?", said[0]).group(0)):],
                    "decimals": 1 if "." in n else 0})
    if effect_id == "chart-grow":
        cfg["pill"] = said[0]
        cfg["labels"] = [""] * 7
    if effect_id == "stack" and "comment" not in lines.lower():
        cfg["cta"], cfg["pill"] = "", ""     # "Comment UPGRADE" with nothing behind it answers nobody
    if effect_id == "phone-mockup":
        cfg.update(secondary="Later", approvedLabel="Done", reply="Done.")
    if effect_id == "screen-push-digital":
        cfg.pop("text", None)            # four words stretched over 10 seconds; "auto" shows each word as it is said
    if effect_id == "shutter-strike":
        cfg["captions"]["y"] = 0.93      # the speaker's eyes sit where the kit puts its captions


def effect_settings(job, effect_id, s0, e0, tw):
    """Fill one effect's words from what is said in [s0, e0], with the person's color, never kit files."""
    eff = fx_effect(effect_id)
    lo, hi = (4, 8) if eff.get("number") in (5, 15, 18, 19) else (5, 10)
    lines = " ".join(w["word"].strip() for w in tw if s0 <= w["start"] < e0)
    fxd = next((f for f in fx_list() if f["mp4"].endswith(effect_id + ".mp4")), {})
    prompt = EFFECT_RULES.format(name=eff["title"], summary=eff.get("summary", ""), uses="; ".join(fxd.get("uses", [])),
                                 options=json.dumps(eff.get("options", {}))[:3000], defaults=json.dumps(eff.get("defaults", {}))[:3000],
                                 lo=lo, hi=hi) + f"[{s0:.1f}-{e0:.1f}] {lines}\n(The stretch is already chosen: use exactly these times.)"
    plan = ask_groq(prompt)
    defaults = eff.get("defaults", {})
    tops = {k.split(".")[0] for k in eff.get("options", {})}
    cfg = {}
    for k, val in (plan.get("config") or {}).items():     # "card.title" is one word inside "card"
        if k.split(".")[0] not in tops:
            continue
        if "." in k:
            at = cfg
            parts = k.split(".")
            for part in parts[:-1]:
                at = at.setdefault(part, {})
            at[parts[-1]] = val
        elif isinstance(val, dict) and isinstance(cfg.get(k), dict):
            cfg[k].update(val)
        else:
            cfg[k] = val
    for k, val in cfg.items():
        if isinstance(val, dict) and isinstance(defaults.get(k), dict):
            cfg[k] = {**defaults[k], **val}
    # 2026-10-27: Green Screen failed when the picker asked for a background picture ("src": "path.png")
    # that does not exist. Any setting that points at a file this computer does not have is dropped.
    def missing_file(v):
        if isinstance(v, dict):
            return any(missing_file(x) for x in v.values()) or (isinstance(v.get("src"), str) and not os.path.exists(os.path.expanduser(v["src"])))
        if isinstance(v, list):
            return any(missing_file(x) for x in v)
        return False
    for k in [k for k, val in cfg.items() if missing_file(val)]:
        cfg.pop(k)
    if "accent" in eff.get("options", {}):
        cfg["accent"] = "#" + brand()["accent"]
    # 2026-10-29, Tiff: "for all my videos i need them in my brand color and thats something that needs to stick
    # for the client too." An effect's own captions fell back to the kit's yellow; they take the person's color now
    cfg["captions"] = {**(cfg.get("captions") or {}), "accent": "#" + brand()["accent"]}
    # 2026-11-03, Tiff: "i also love the white lettering around this". Dark blue words sat unreadable on a dark top.
    if brand()["accent"].upper() != "FFFFFF":
        cfg["captions"]["outline"] = "#FFFFFF"
    effect_words(effect_id, cfg, lines)
    # 2026-10-27: Stack's default wall is the kit's own demo clips (a stranger's face) and its default
    # text sells the kit ("Comment KIT"). The wall is always stills from the person's own video.
    keep = {"tiles": []} if "tiles" in eff.get("options", {}) else {}
    if effect_id == "stack":
        keep.update({k: cfg.get(k, "") for k in ("title", "subtitle", "cta", "pill")})
    cfg.update(keep)
    if effect_id == "paper-cut":
        # 2026-10-27: "seconds" came out as "30 econds"; the kit's ransom letters are made for capitals
        cfg.update({k: v.upper() for k, v in cfg.items() if k in ("headline", "subline") and isinstance(v, str)})
        # the kit centres the subline under a left-aligned headline, so a long word under "30" runs off the
        # left edge ("ECONDS"). When the subline is the longer word, centre both on the screen.
        if len(str(cfg.get("subline", ""))) > len(str(cfg.get("headline", ""))):
            cfg["headlineAlign"] = "center"
    return eff, cfg, keep, plan.get("why", "")


def render_effect(job, effect_id, tight, s0, e0, cfg, keep, n=""):
    seg = os.path.join(job.dir, f"segment{n}-{effect_id}.mp4")
    node = shutil.which("node") or "/usr/local/bin/node"
    fx = os.path.join(FX_KIT, "engine/fx.mjs")
    def go(c):
        pr = subprocess.Popen([node, fx, "render", effect_id, tight, "--start", f"{s0:.3f}", "--end", f"{e0:.3f}",
                               "--config", json.dumps(c), "--out", seg], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              text=True, cwd=os.path.dirname(fx))
        out, err = pr.communicate()
        job.fx_pids = getattr(job, "fx_pids", []) + [pr.pid]
        return subprocess.CompletedProcess(pr.args, pr.returncode, out, err)
    r = go(cfg)
    open(os.path.join(job.dir, "render.log"), "a").write(f"\n--- {effect_id} ---\n" + r.stdout + r.stderr)
    # 2026-11-03: on a busy Mac the browser that draws the effect can time out. Her words were fine and the retry
    # below threw them away, so a video about her upgrade came out saying "RAW CLIPS". Same words get one more try first.
    if (r.returncode or not os.path.exists(seg)) and re.search(r"Request closed|delayRender|Timeout|timed out", r.stdout + r.stderr):
        job.say("The Mac was too busy to draw that. Trying the same words again.")
        time.sleep(30)
        r = go(cfg)
        open(os.path.join(job.dir, "render.log"), "a").write("\n--- retry, same words ---\n" + r.stdout + r.stderr)
    if (r.returncode or not os.path.exists(seg)) and set(cfg) - {"accent"} - set(keep):
        # the picker's settings can still break a render; the effect's own defaults are known to work
        job.say("That version didn't render. Trying again with the effect's standard look and your color.")
        r = go({**{k: v for k, v in cfg.items() if k in ("accent", "captions", "username", "likes", "comments", "showViews", "views")}, **keep})
        open(os.path.join(job.dir, "render.log"), "a").write("\n--- retry with defaults ---\n" + r.stdout + r.stderr)
    if r.returncode or not os.path.exists(seg):
        raise RuntimeError("The effect did not render: " + (r.stderr or r.stdout).strip().splitlines()[-1][:200])
    return seg


LOW_CAPS = {"digital-zoom", "orbit", "pop-out", "phone-frame", "brand-backdrop", "brand-frame", "spotlight",
            "always-never", "flip-cards", "mono-story", "big-type"}


def caption_part(job, tight, a, b, n, low=False):
    """Brand captions on one stretch the effects don't cover. low: under the chin, never across the face."""
    whole = a <= 0.001 and b >= float(probe(tight, count=False)["format"]["duration"]) - 0.05
    raw = tight if whole else os.path.join(job.dir, f"part{n}.mov")
    if not whole:
        cut(tight, a, b, raw)
    preset, hook_font = brand_files(brand())
    fin = os.path.join(job.dir, f"part{n}.mp4")
    rr = subprocess.run([VENV_PY, FINISHER, raw, fin, "--no-hook", "--layout", "full", "--preset", preset,
                         "--font", hook_font, "--accent", brand()["accent"]] + (["--cap-y", "76"] if low else []), capture_output=True, text=True)
    if rr.returncode:
        raise RuntimeError("Adding your captions failed: " + (rr.stderr or rr.stdout)[-300:])
    rep = json.loads(rr.stdout[rr.stdout.index("{"):])
    shutil.rmtree(rep.get("work", ""), ignore_errors=True)
    if raw != tight:
        os.remove(raw)
    return fin, rep.get("captions", "")


def gaps_between(tlen, times):
    """The stretches the effects don't cover, which get the person's captions."""
    out, t = [], 0.0
    for s0, e0 in sorted(times) + [(tlen, tlen)]:
        if s0 - t >= 1.0:
            out.append((t, s0))
        t = max(t, e0)
    return out


def start_captions(job, tight, tlen, times):
    """2026-10-27, Tiff: "make it fast". Captions for the plain-talking parts are made WHILE the effects
    render, instead of after them. Returns a function that waits and hands back {(a, b): (file, words)}."""
    from concurrent.futures import ThreadPoolExecutor
    pool = ThreadPoolExecutor(max_workers=1)
    futs = {(a, b): pool.submit(caption_part, job, tight, a, b, n) for n, (a, b) in enumerate(gaps_between(tlen, times), 1)}
    pool.shutdown(wait=False)
    return lambda: {k: f.result() for k, f in futs.items()}


def finish_timeline(job, tight, tlen, tw, fx_spans, title, why, ready=None):
    """fx_spans: [(s, e, segment.mp4)] in order. Captions go on every stretch between them, then it's all
    joined into one 1080x1920 video and counted before anyone sees it."""
    import difflib
    parts, caps, said, t, n = [], [], [], 0.0, 0
    done = ready() if ready else {}
    for s0, e0, seg in fx_spans + [(tlen, tlen, None)]:
        if s0 - t >= 1.0:
            job.state = "adding your captions"
            n += 1
            fin, heard = done.get((t, s0)) or caption_part(job, tight, t, s0, n)
            parts.append(fin)
            caps.append(heard)
            said.append(" ".join(w["word"] for w in tw if t <= w["start"] < s0))
        if seg:
            parts.append(seg)
        t = max(t, e0)
    job.state = "putting it all together"
    name = re.sub(r"[^\w &-]", "", os.path.splitext(job.name)[0]).strip()[:50]
    out = os.path.join(job.dir, "out", f"{name} - {title}.mp4")
    ins = sum([["-i", x] for x in parts], [])
    norm = "".join(f"[{i}:v]scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,"
                   f"fps={FPS},setsar=1[v{i}];[{i}:a]aresample=48000,aformat=channel_layouts=stereo[a{i}];" for i in range(len(parts)))
    subprocess.run([FF, "-v", "error", *ins, "-filter_complex",
                    norm + "".join(f"[v{i}][a{i}]" for i in range(len(parts))) + f"concat=n={len(parts)}:v=1:a=1[v][a]",
                    "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-crf", "17", "-preset", "fast", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-y", out], check=True)
    want = sum(float(probe(x, count=False)["format"]["duration"]) for x in parts)
    brand_finish(job, out)
    ok, checks = ledger(out, "1080x1920", want)
    checks["no pauses left (talking parts joined)"] = [getattr(job, "spans", 0), "all", True]
    checks["effects in the video"] = [len(fx_spans), len(fx_spans), True]
    if caps and len(" ".join(said).split()) >= 8:      # a handful of words is too few to judge fairly
        nrm = lambda x: [FIX_WORDS.get(y, y) for y in re.sub(r"[^a-z0-9 ]", " ", x.lower()).split()]
        match = round(100 * difflib.SequenceMatcher(None, nrm(" ".join(said)), nrm(" ".join(caps))).ratio())
        checks["captions match the words"] = [f"{match}%", ">= 80%", match >= 80]
        ok = ok and match >= 80
    sheet = out[:-4] + " frames.jpg"
    d = float(probe(out, count=False)["format"]["duration"])
    contact_sheet(out, sheet)
    for f in [tight, *parts]:
        if os.path.exists(f):
            os.remove(f)
    job.shorts.append({"file": os.path.basename(out), "sheet": os.path.basename(sheet), "ok": ok,
                       "seconds": round(d, 1), "from": "0:00", "hook": [], "why": why, "checks": checks})
    job.say(f"{title} {'PASSED' if ok else 'FAILED'} the checks")
    job.save()


def fx_cleanup(job):
    """2026-10-27: every effect left 20 to 40 MB of the kit's copies plus a render scratch folder behind,
    and the kit only clears scratch after 6 hours. A day of testing filled the disk three times.
    Remove exactly what this job made: the kit's folder for this job's video and its render folders."""
    jobs_dir = os.path.join(FX_KIT, "engine", "jobs")
    if not os.path.isdir(jobs_dir):
        return
    for d in os.listdir(jobs_dir):
        if d.startswith(f"tight-{job.id}"):
            shutil.rmtree(os.path.join(jobs_dir, d), ignore_errors=True)
    runs = os.path.join(jobs_dir, "_runs")
    for pid in getattr(job, "fx_pids", []):
        for d in (os.listdir(runs) if os.path.isdir(runs) else []):
            if d.endswith(f"-{pid}"):
                shutil.rmtree(os.path.join(runs, d), ignore_errors=True)


NUMBER_WORDS = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten",
                11: "eleven", 12: "twelve", 15: "fifteen", 20: "twenty", 30: "thirty", 40: "forty", 50: "fifty", 100: "hundred",
                1000: "thousand"}
MYFX_RULES = """You fill in one on-screen effect for a short talking video. Effect: {name}.
Below are the speaker's words with times. Use ONLY their own words, never invent.
Return ONLY JSON with these keys:
"number": the main number they say as plain digits (5000, 3, 30), or null if they say no number;
"prefix": "$" if it is money else "";
"suffix": "%", "X", "K", "+" or "" to match how they said it;
"label": 1 to 3 words that go under the number (for example "DAYS", "IN SALES"), else "";
"headline": the 1 to 3 most important words they say, for huge text;
"quote": their single best sentence, 6 to 16 words, copied EXACTLY word for word as they said it;
"title": a 1 to 3 word title for a list of steps;
"items": 2 to 4 short steps or list items in their words, each under 24 characters, each with "word" = the
exact word in the transcript when they start saying it.
Words:
"""


def words_plan(tw):
    """2026-10-30: a new member has no Groq key, so the plan came back empty and Number Pop stopped on a video
    that said "30 seconds". This reads the same things straight off their words; Groq's answer wins when it has one."""
    plan, spoken = {}, {v: k for k, v in NUMBER_WORDS.items()}
    for i, w in enumerate(tw):
        t = w["word"].strip(" .,!?\"")
        m = re.match(r"^(\$?)([\d,]*\.?\d+)([%xXkK+]?)$", t)
        n = float(m.group(2).replace(",", "")) if m else spoken.get(t.lower())
        if n is None:
            continue
        nxt = tw[i + 1]["word"].strip(" .,!?\"") if i + 1 < len(tw) else ""
        plan.update({"number": n, "prefix": m.group(1) if m else "", "suffix": (m.group(3).upper() if m else ""),
                     "label": nxt.upper() if nxt.isalpha() and len(nxt) <= 12 else ""})
        break
    phrases, cur = [], []
    for w in tw:
        cur.append(w)
        if re.search(r"[,.!?]$", w["word"].strip()):
            phrases.append(cur); cur = []
    phrases = [p for p in phrases + ([cur] if cur else []) if len(p) >= 2][:3]
    if len(phrases) >= 2:
        short = lambda t: t if len(t) <= 24 else t[:25].rsplit(" ", 1)[0]
        plan["items"] = [{"text": short(" ".join(x["word"].strip(" ,.!?") for x in p)), "word": p[0]["word"]} for p in phrases]
    return plan


def zoom_moments(tw, tlen):
    """When Digital Zoom changes the shot: on a word that starts a new phrase, at least 2.2 s after the last
    change, and never more than 5 s without one. From the words alone, so it needs no key and no internet.
    One ffmpeg zoom line holds about 70 changes (100 made it fail on 2026-11-02), so a long video spaces them wider."""
    least = max(2.2, tlen / 70)
    most = max(5.0, least * 1.5)
    out, last = [], 0.0
    for prev, w in zip(tw, tw[1:]):
        t = w["start"]
        fresh = bool(re.search(r"[.!?,:;]$", prev["word"].strip())) or t - prev["end"] > 0.25
        if t - last >= most or (fresh and t - last >= least):
            if tlen - t >= 1.2:      # a change right at the end just looks like a mistake
                out.append(round(t, 3))
                last = t
    return out


def stage_lines(tw, tlen):
    """What Split Stage shows up top: the first few words said in each stretch between shot changes, their own words."""
    at = [0.0] + zoom_moments(tw, tlen) + [tlen + 1]
    out = []
    for a, b in zip(at, at[1:]):
        said = [w["word"].strip(" ,.!?") for w in tw if a <= w["start"] < b]
        if said:
            out.append({"text": " ".join(said[:5]).upper(), "t0": round(a, 3), "t1": round(b, 3)})
    return out


def pop_words(tw, tlen):
    """The word that gets popped: at each shot change, the longest real word said in the next few words."""
    small = set("about after again because being could doing every going really should their there these thing think those where which while would".split())
    out = []
    for t in zoom_moments(tw, tlen):
        near = [w for w in tw if w["start"] >= t][:7]
        cands = [w for w in near if len(re.sub(r"[^A-Za-z0-9$%]", "", w["word"])) >= 4 and re.sub(r"[^a-z]", "", w["word"].lower()) not in small]
        if cands:
            w = max(cands, key=lambda x: len(x["word"]))
            if not out or w["start"] - out[-1]["t"] > 1.2:
                out.append({"w": re.sub(r"[^A-Za-z0-9$%'-]", "", w["word"]), "t": round(w["start"], 3)})
    return out


# --- the words an edit shows have to read as a thought on their own, not whatever got said first ---
SMALL_WORDS = set("""a about actually after again ahead all allow also although am an and any anything are as at basically be because been being but by can could did do does doing
don't even fact for from get gets getting go goes going gonna got had happens has have having he her here here's him his how i i'm if in into is it it's its just kind know like literally
little lot maybe me more much my need not of oh okay on once one or our out over really right said say says see she should so some something stuff than that that's
the their them then there these they they're thing things think this those to too try um uh us very wanna want was way we we'll well were what when where which while who
why will with would y'all yeah yes you your you're""".split())


def _bare(word):
    return re.sub(r"[^a-z0-9$%']", "", str(word).lower().replace("’", "'"))


def _small(word):
    return _bare(word) in SMALL_WORDS or not _bare(word)


def _phrases(words):
    """Their words split where they took a breath or the sentence turned."""
    out, cur = [], []
    for i, w in enumerate(words):
        cur.append(w)
        gap = words[i + 1]["start"] - w["end"] if i + 1 < len(words) else 9
        if re.search(r"[.!?,:;]$", w["word"].strip()) or gap > 0.25:
            out.append(cur)
            cur = []
    return out + ([cur] if cur else [])


def best_phrase(words, most=5, chars=24, skip=()):
    """The strongest short run of their own words. It never starts or ends on a small word like 'and' or 'want'."""
    best, top = "", 0.0
    for p in _phrases(words):
        for a in range(len(p)):
            if _small(p[a]["word"]):
                continue
            for b in range(a, min(a + most, len(p))):
                if _small(p[b]["word"]):
                    continue
                text = " ".join(w["word"].strip(" ,.!?:;") for w in p[a:b + 1])
                if len(text) > chars or text.lower() in skip:
                    continue
                strong = sum(not _small(w["word"]) for w in p[a:b + 1])
                starts = all(_small(w["word"]) for w in p[:a])
                ends = all(_small(w["word"]) for w in p[b + 1:])
                score = strong + (b > a) + starts + 2 * ends - 2 * bool(re.search(r"ly$", _bare(p[b]["word"])))
                if score > top:
                    best, top = text, score
    return best


def opening_line(tw, most=6, chars=30):
    """A title for the video: the strongest line in the opening, not just its first words."""
    return best_phrase([w for w in tw if w["start"] < 12] or tw, most, chars) or " ".join(w["word"].strip(" ,.!?") for w in tw[:4])


def stage_lines(tw, tlen):
    """What Split Stage and Note Card show: the strongest short line said in each stretch between shot changes, no line twice."""
    at = [0.0] + zoom_moments(tw, tlen) + [tlen + 1]
    out, used = [], set()
    for a, b in zip(at, at[1:]):
        line = best_phrase([w for w in tw if a <= w["start"] < b], skip=used)
        if line:
            used.add(line.lower())
            out.append({"text": line.upper(), "t0": round(a, 3), "t1": round(b, 3)})
        elif out:      # nothing worth showing in this stretch, so the last line stays up
            out[-1]["t1"] = round(b, 3)
    return out


def pop_words(tw, tlen):
    """The word that gets popped: at each shot change, the longest real word said in the next few words, and no word twice."""
    out, used = [], set()
    for t in zoom_moments(tw, tlen):
        near = [w for w in tw if w["start"] >= t][:7]
        cands = [w for w in near if len(_bare(w["word"])) >= 4 and not _small(w["word"]) and _bare(w["word"]) not in used]
        if cands:
            w = max(cands, key=lambda x: len(_bare(x["word"])))
            if not out or w["start"] - out[-1]["t"] > 1.2:
                used.add(_bare(w["word"]))
                out.append({"w": re.sub(r"[^A-Za-z0-9$%'-]", "", w["word"]), "t": round(w["start"], 3)})
    return out


def run_my_effect(job, effect_id, opts):
    """One of Tiff's own effects: clean sound, pauses cut, brand captions on the WHOLE video, then the effect
    drawn on top at the right moment. No cut-out render farm, so most of these take a minute or two."""
    tight, tlen, tw = prepare_talking(job, opts or {})
    meta = next(e for e in MY_EFFECTS if e["id"] == effect_id)
    job.state = "finding the best spot"
    body = "\n".join(f"[{w['start']:.2f}] {w['word'].strip()}" for w in tw)[:12000]
    try:
        # no key means no words to ask about: straight to what the Mac can read off the words
        plan = ask_groq(MYFX_RULES.format(name=meta["name"]) + body) if key("GROQ_API_KEY") and effect_id not in NO_PLAN else {}
    except Exception:
        plan = {}
    plan = {**words_plan(tw), **{k: v for k, v in (plan or {}).items() if v not in (None, "", [])}}
    kind = effect_id[5:]
    ends = [w["end"] for w in tw if re.search(r"[.!?,]$", w["word"].strip())]
    first_end = next((t for t in ends if 3.5 <= t <= 9), min(tlen, 6.0))
    s0, e0 = 0.0, first_end
    cfg = {"accent": "#" + brand()["accent"], "font": brand_files(brand())[1]}
    if kind in ("number-pop", "stat-bars"):
        num = plan.get("number")
        try:
            num = float(str(num).replace(",", ""))
        except (TypeError, ValueError):
            num = None
        hit = None
        if num is not None:     # put it where they actually say the number, in digits or in words
            digits = re.sub(r"\.0$", "", f"{num:g}")
            spoken = NUMBER_WORDS.get(int(num)) if num == int(num) else None
            hit = next((w for w in tw if digits == re.sub(r"[^0-9.]", "", w["word"])
                        or (spoken and w["word"].strip(" .,!?").lower() == spoken)), None)
        if num is not None and num <= 1:
            num = None
        if num is None:
            raise RuntimeError(f"{meta['name']} needs you to say a number (like $5,000, 3X or 30 days). Try another effect for this video.")
        s0 = max(0.0, hit["start"] - 0.1) if hit else 0.0
        e0 = min(tlen, s0 + 3.5)
        cfg.update({"number": num, "prefix": plan.get("prefix", "") or "", "suffix": plan.get("suffix", "") or "",
                    "label": str(plan.get("label", "") or "")[:24].upper()})
    elif kind in ("checklist", "step-counter"):
        items = []
        for it in (plan.get("items") or [])[:4]:
            w = next((x for x in tw if x["word"].strip(" .,!?").lower() == str(it.get("word", "")).strip(" .,!?").lower()), None)
            text = str(it.get("text", ""))
            if len(text) > 24:
                text = text[:25].rsplit(" ", 1)[0]
            items.append({"text": text, "at": w["start"] if w else None})
        if not items:
            raise RuntimeError(f"{meta['name']} needs you to walk through a few steps. Try another effect for this video.")
        known = [i["at"] for i in items if i["at"] is not None]
        s0 = max(0.0, (min(known) if known else 0.0) - 0.6)
        last = max(known) if known else s0 + 2 * len(items)
        for k, i in enumerate(items):      # an item we couldn't place ticks a moment after the one before
            if i["at"] is None:
                i["at"] = (items[k - 1]["at"] + 1.5) if k else s0 + 0.8
        e0 = min(tlen, max(i["at"] for i in items) + 2.0)
        cfg.update({"items": items, "title": str(plan.get("title", "") or "The steps")[:24]})
    elif kind in ("headline-behind", "marker-swipe", "phone-frame"):
        cfg["headline"] = str(plan.get("headline", "") or " ".join(w["word"] for w in tw[:2]))[:30]
        if kind == "marker-swipe":      # lands when they say the words
            first = cfg["headline"].split()[0].strip(" .,!?").lower() if cfg["headline"].split() else ""
            hit = next((w for w in tw if w["word"].strip(" .,!?").lower() == first), None)
            s0 = max(0.0, hit["start"] - 0.1) if hit else 0.0
            e0 = min(tlen, s0 + 3.0)
    elif kind == "paper-scribble":
        # the sheet is found in the frames; what they say while holding it up is what gets written on it
        r = subprocess.run([VENV_PY, MYFX, "paper-scan", tight], capture_output=True, text=True)
        try:
            spans = json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            spans = []
        notes = []
        for a, b in spans:
            said = [w for w in tw if a - 0.3 <= w["start"] < b]
            # 2026-10-28: with every pause cut, two holds can sit back to back, so every phrase said while
            # the sheet is up ("Content creator, following up, ...") gets its own sheet
            phrases, cur = [], []
            for w in said:
                cur.append(w)
                if re.search(r"[,.!?]$", w["word"].strip()):
                    phrases.append(cur); cur = []
            if cur:
                phrases.append(cur)
            for k, ph in enumerate(phrases):
                text = ""
                for w in ph:
                    if len((text + " " + w["word"].strip()).strip()) > 22:
                        break
                    text = (text + " " + w["word"].strip()).strip()
                nxt = phrases[k + 1][0]["start"] - 0.05 if k + 1 < len(phrases) else b - 0.15
                if text and nxt - ph[0]["start"] >= 0.5:
                    notes.append({"text": text.strip(" ,.") + ("..." if text.endswith((",", "...")) else ""),
                                  "start": max(a, ph[0]["start"] - 0.1), "end": max(ph[0]["start"] + 0.8, nxt)})
        if not notes:
            raise RuntimeError("Paper Scribble needs you to hold up a blank sheet of paper while you talk. Try another effect for this video.")
        # 2026-10-28, Tiff: "someone can put what they want to put on the paper". Their lines go on the sheets
        # in order; a sheet with no line of theirs keeps the words they said
        mine = [x.strip()[:40] for x in re.split(r"[\n|]", str(opts.get("paper") or "")) if x.strip()]
        for n, line in zip(notes, mine):
            n["text"] = line
            if len(line) <= 6:
                n["chars_per_sec"] = 10      # one short word ("HELP!") writes slower, so you hear the scribble
        for x, y in zip(notes, notes[1:]):      # the next sheet flips in, so it starts a beat after the one before ends
            y["start"] = max(y["start"], x["end"] + 0.22)
        cfg.update({"notes": notes, "chars_per_sec": 24})
        s0, e0 = max(0.0, notes[0]["start"] - 0.3), min(tlen, notes[-1]["end"] + 0.15)
    elif kind == "article-screen":
        pic = str(opts.get("picture") or "")
        if not os.path.isfile(pic):
            raise RuntimeError("Green Screen Article needs your picture. Tap the effect again and add your article or screenshot.")
        # the room shows for their first few words, then the picture comes in and stays for about 12 seconds,
        # ending on a full stop
        s0 = next((t for t in ends if 0.8 <= t <= 3.5), min(1.5, tlen / 4))
        stops = [t for t in ends if s0 + 6 <= t <= s0 + 14]
        e0 = min(tlen, stops[-1] + 0.2 if stops else s0 + 12)
        cfg.update({"picture": pic, "back": e0 < tlen - 0.5})
    elif kind in ("brand-frame", "brand-stage", "cinema-look"):
        s0, e0 = 0.0, tlen
    elif kind == "top-banner":
        cfg["headline"] = opening_line(tw)
        s0, e0 = 0.0, tlen
    elif kind in ("split-stage", "note-card"):
        cfg["lines"] = stage_lines(tw, tlen)
        s0, e0 = 0.0, tlen
    elif kind == "orbit":
        cfg["orbit_words"] = [x["w"] for x in pop_words(tw, tlen)][:6] or [w["word"].strip(" .,!?") for w in tw[:4]]
        s0, e0 = 0.0, min(tlen, 5.5)
    elif kind == "pop-out":
        s0, e0 = 0.0, min(tlen, 5.5)
    elif kind in ("word-pop", "glow-words", "doodles"):
        cfg["words"] = pop_words(tw, tlen)
        cfg["hand"] = os.path.join(CAPTIONS, "fonts", "Pacifico.ttf")
        if not cfg["words"]:
            raise RuntimeError("This video is too short for Word Pop. Try one that's at least 5 seconds.")
        s0, e0 = 0.0, tlen
    elif kind == "digital-zoom":
        cfg["moments"] = zoom_moments(tw, tlen)
        if not cfg["moments"]:
            raise RuntimeError("This video is too short for Digital Zoom. Try one that's at least 5 seconds.")
        s0, e0 = 0.0, tlen
    elif kind == "lower-third":
        cfg.update({"name": brand().get("name") or "", "title": brand().get("title") or ""})
        s0, e0 = min(0.5, tlen / 4), min(tlen, 4.5)
    elif kind == "quote-card":
        # their own sentence, timed to their own words; a quote we can't find in the words isn't used
        want = [x for x in re.sub(r"[^a-z0-9' ]", " ", str(plan.get("quote", "")).lower()).split()]
        said = [w["word"].strip(" .,!?\"").lower() for w in tw]
        at = next((i for i in range(len(said) - len(want) + 1) if want and said[i:i + len(want)] == want), None)
        if at is None:      # fall back to their first full sentence
            stop = next((i for i, w in enumerate(tw) if re.search(r"[.!?]$", w["word"].strip()) and i >= 5), min(len(tw), 12) - 1)
            at, want = 0, said[:min(stop + 1, 16)]
        seq = tw[at:at + len(want)]
        cfg["words"] = [{"w": w["word"].strip(), "t": w["start"]} for w in seq]
        s0, e0 = max(0.0, seq[0]["start"] - 0.2), min(tlen, seq[-1]["end"] + 1.2)
    if kind in FORMS:
        cfg.update({"moments": zoom_moments(tw, tlen), "keys": pop_words(tw, tlen), "title": opening_line(tw, 4, 24),
                    "said": [{"w": w["word"], "t": w["start"], "e": w["end"]} for w in tw], "typed": [x.strip() for x in re.split(r"[\n,]", str((opts or {}).get("words") or "")) if x.strip()][:12],
                    "brand_name": brand().get("name") or "", "cta": brand().get("cta") or "", "hand": os.path.join(CAPTIONS, "fonts", "Pacifico.ttf")})
        s0, e0 = 0.0, tlen
        if kind in CLIP_KINDS:
            cfg["clips"] = job_pictures(job, "clips")
            if not cfg["clips"]:
                raise RuntimeError(f"{meta['name']} needs your other video. Tap it again and add it.")
        if kind == "tool-cards":
            cfg["pictures"] = job_pictures(job)
        if kind in PICTURE_KINDS:
            cfg["pictures"] = job_pictures(job)
            if not cfg["pictures"]:
                raise RuntimeError(f"{meta['name']} needs your pictures. Tap it again and add at least one.")
    if kind in MOVES:
        cfg["moments"] = zoom_moments(tw, tlen)
        s0, e0 = 0.0, tlen
    mine = [x.strip() for x in re.split(r"[\n,]", str((opts or {}).get("words") or "")) if x.strip()][:12]
    if mine:
        if kind == "top-banner":
            cfg["headline"] = " ".join(mine)[:40]
        elif kind in ("word-pop", "glow-words", "doodles"):
            base, typed = cfg.get("words") or [], []
            for i, m in enumerate(mine):
                hit = next((w for w in tw if w["word"].strip(" .,!?").lower() == m.lower()), None)
                at = hit["start"] if hit else (base[i]["t"] if i < len(base) else None)
                if at is not None:
                    typed.append({"w": m[:24], "t": round(at, 3)})
            cfg["words"] = sorted(typed, key=lambda x: x["t"]) or base
        elif kind == "orbit":
            cfg["orbit_words"] = [m[:16] for m in mine[:6]]
        elif kind in ("split-stage", "note-card"):
            for i, x in enumerate(cfg["lines"]):
                x["text"] = mine[i % len(mine)].upper()[:40]
        elif kind in ("marker-swipe", "headline-behind", "phone-frame"):
            cfg["headline"] = mine[0][:30]
        elif kind == "lower-third":
            cfg["title"] = mine[0][:40]
    if kind in WIDE_KINDS:
        return finish_wide(job, kind, meta, tight, tlen, tw, cfg)
    job.say(f"{meta['name']} goes at {s0:.1f} s to {e0:.1f} s")
    if kind in FORMS and kind not in ("flip-cards", "growth-chart", "glass-graph", "split-steps", "split-kinetic", "photo-world", "testimonial-wall", "vertigo") or kind in ("orbit", "word-pop", "glow-words", "doodles", "note-card", "top-banner", "marker-swipe", "quote-card", "lower-third",
                "number-pop", "stat-bars", "checklist", "step-counter", "cinema-look", "brand-frame", "brand-stage", "spotlight"):
        moved = tight[:-4] + "-zoom.mov"
        r = subprocess.run([VENV_PY, MYFX, "digital-zoom", tight, moved, "--start", "0", "--end", f"{tlen:.3f}", "--config",
                            json.dumps({"moments": zoom_moments(tw, tlen)})], capture_output=True, text=True)
        if r.returncode == 0 and os.path.exists(moved):
            os.replace(moved, tight)
        # 2026-10-27: these change the whole picture (the punch-in, the room swapped or blurred), so they go on
    # the video BEFORE the captions. Drawn after, Brand Backdrop and Spotlight cut and blurred the captions.
    pre = kind in MOVES or kind in FORM_PRE or kind in ("digital-zoom", "cinema-look", "brand-stage", "split-stage", "zoom-punch", "brand-backdrop", "spotlight", "paper-scribble", "article-screen")
    if pre:
        punched = tight[:-4] + "-fx.mov"
        r = subprocess.run([VENV_PY, MYFX, kind, tight, punched, "--start", f"{s0:.3f}", "--end", f"{e0:.3f}", "--config", json.dumps(cfg)],
                           capture_output=True, text=True)
        if r.returncode or not os.path.exists(punched):
            raise RuntimeError(f"{meta['name']} didn't render: " + (r.stderr or r.stdout).strip()[-200:])
        os.replace(punched, tight)
    if kind == "paper-scribble":
        # the sheet already shows the words, and captions laid across it hid the second line: no captions
        # while it's up, captions everywhere else
        seg = os.path.join(job.dir, "paper.mov")
        cut(tight, s0, e0, seg)
        finish_timeline(job, tight, tlen, tw, [(s0, e0, seg)], meta["name"],
                        f"{meta['name']}: {len(cfg['notes'])} note(s) on your paper, pauses cut, sound cleaned, captions in your brand.")
        return
    job.state = "adding your captions"
    if kind == "split-stage" or kind in FORM_NOCAP:
        fin, heard = os.path.join(job.dir, "split.mp4"), " ".join(w["word"].strip() for w in tw)
        subprocess.run([FF, "-v", "error", "-i", tight, "-vf", "scale=1080:1920:flags=lanczos,setsar=1", "-c:v", "libx264", "-crf", "16", "-preset", "fast",
                        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-y", fin], check=True)
    else:
        fin, heard = caption_part(job, tight, 0.0, tlen, 1, low=kind in LOW_CAPS)
    job.state = f"adding {meta['name']}"
    name = re.sub(r"[^\w &-]", "", os.path.splitext(job.name)[0]).strip()[:50]
    out = os.path.join(job.dir, "out", f"{name} - {meta['name']}.mp4")
    if pre:
        shutil.copy(fin, out)
        r = subprocess.CompletedProcess([], 0, "", "")
    else:
        r = subprocess.run([VENV_PY, MYFX, kind, fin, out, "--start", f"{s0:.3f}", "--end", f"{e0:.3f}", "--config", json.dumps(cfg)],
                           capture_output=True, text=True)
    open(os.path.join(job.dir, "render.log"), "w").write(r.stdout + r.stderr)
    if r.returncode or not os.path.exists(out):
        raise RuntimeError(f"{meta['name']} didn't render: " + (r.stderr or r.stdout).strip()[-200:])
    want = float(probe(fin, count=False)["format"]["duration"])
    brand_finish(job, out)
    ok, checks = ledger(out, "1080x1920", want)
    checks["no pauses left (talking parts joined)"] = [getattr(job, "spans", 0), "all", True]
    import difflib
    nrm = lambda x: [FIX_WORDS.get(y, y) for y in re.sub(r"[^a-z0-9 ]", " ", x.lower()).split()]
    said = " ".join(w["word"] for w in tw)
    if len(said.split()) >= 8:
        match = round(100 * difflib.SequenceMatcher(None, nrm(said), nrm(heard)).ratio())
        checks["captions match the words"] = [f"{match}%", ">= 80%", match >= 80]
        ok = ok and match >= 80
    sheet = out[:-4] + " frames.jpg"
    contact_sheet(out, sheet)
    for f in (tight, fin):
        if os.path.exists(f):
            os.remove(f)
    job.shorts.append({"file": os.path.basename(out), "sheet": os.path.basename(sheet), "ok": ok, "seconds": round(want, 1),
                       "from": "0:00", "hook": [], "why": f"{meta['name']} at {s0:.1f} s, pauses cut, sound cleaned, captions in your brand.",
                       "checks": checks, "fx_at": [s0, e0]})
    job.say(f"{meta['name']} {'PASSED' if ok else 'FAILED'} the checks")
    job.save()


def run_effect(job, effect_id, opts=None):
    """Put one effect from the Claude Video FX Kit on the person's video and hand back a FINISHED video:
    clean sound, every pause cut, the effect right at the start (Stack, a call to action, at the end),
    and captions in their brand on everything the effect doesn't already caption.
    2026-10-27, Tiff: the first version dropped the effect into "a weird part of the video", kept the
    dead air and had no captions. "All of your videos need to be cleaned up no matter what." """
    tight, tlen, tw = prepare_talking(job, opts or {})
    job.state = "finding the best spot"
    eff = fx_effect(effect_id)
    lo, hi = (4, 8) if eff.get("number") in (5, 15, 18, 19) else (5, 10)
    at_end = effect_id == "stack"
    if at_end:
        starts = [w["start"] for w in tw if tlen - hi <= w["start"] <= tlen - lo]
        s0, e0 = (starts[0] if starts else max(0.0, tlen - hi)), tlen
    else:
        good = [w["end"] for w in tw if re.search(r"[.!?,]$", w["word"].strip()) and lo <= w["end"] <= hi]
        s0, e0 = 0.0, min(tlen, good[-1] + 0.1 if good else hi)
    # 2026-10-27: a 16 s video left a 1.3 s tail after the effect, captioned on its own. Choppy.
    # Under 3 s left over, the effect simply runs to the end (or from the start, for Stack).
    if not at_end and tlen - e0 < 3:
        e0 = tlen
    if at_end and s0 < 3:
        s0 = 0.0
    eff, cfg, keep, why = effect_settings(job, effect_id, s0, e0, tw)
    json.dump({"start": s0, "end": e0, "config": cfg, "why": why}, open(os.path.join(job.dir, "plan.json"), "w"), indent=1)
    job.say(f"The effect goes {'at the end' if at_end else 'right at the start'}: {s0:.1f} s to {e0:.1f} s")
    ready = start_captions(job, tight, tlen, [(s0, e0)])
    job.state = "making your effect (the first one on a new video takes a few minutes)"
    seg = render_effect(job, effect_id, tight, s0, e0, cfg, keep)
    finish_timeline(job, tight, tlen, tw, [(s0, e0, seg)], eff["title"],
                    f"{eff['title']} {'at the end' if at_end else 'at the start'}, pauses cut, sound cleaned, captions in your brand. {why}", ready)


def run_reel(job, opts):
    """Full reel, the way the kit's own lesson does it: 3 to 4 effects spread through a 30 to 90 s clip,
    captions in the person's brand on everything between, joined into one video."""
    tight, tlen, tw = prepare_talking(job, opts)
    job.state = "planning your reel"
    ids = {f["mp4"][3:-4] for f in fx_list()}
    mine = [e for e in (opts.get("effects") or []) if e in ids][:6]     # her own effects are One effect only for now
    if mine:
        # 2026-10-27, Tiff: they can pick how many effects and the order themselves. Spread them evenly,
        # each on whole sentences; Stack, a call to action, always closes the reel.
        ss = sentences(tw)
        chosen, last_end = [], -99.0
        for k, fid in enumerate(mine):
            if fid == "stack":
                s0 = max([x for x, _, _ in ss if x <= tlen - 4] or [max(0.0, tlen - 6)])
                chosen.append((fid, max(s0, last_end + 1.0), tlen, "")); last_end = tlen
                continue
            want = 0.0 if k == 0 else k * tlen / len(mine)
            starts = [x for x, _, _ in ss if x >= max(want - 2, last_end + 4)]
            if not starts:
                break
            s0 = starts[0]
            e0 = next((y for x, y, _ in ss if x >= s0 and 4 <= y - s0 <= 9), min(tlen, s0 + 6.5))
            chosen.append((fid, s0, min(e0, tlen), "")); last_end = e0
        if not chosen:
            chosen = [(mine[0], 0.0, min(tlen, 7.5), "")]
        if len(chosen) < len(mine):
            job.say(f"Your video fits {len(chosen)} of the {len(mine)} effects you picked, so the rest were left out")
        return finish_reel(job, tight, tlen, tw, chosen)
    n = 3 if tlen < 50 else 4
    menu = "\n".join(f"{f['mp4'][3:-4]}: {'; '.join(f['uses'][:2])}" for f in fx_list())
    body = "\n".join(f"[{x:.1f}-{y:.1f}] {t}" for x, y, t in sentences(tw))[:12000]
    try:
        plan = ask_groq(REEL_RULES.format(n=n, tlen=tlen, menu=menu) + body).get("effects", [])
    except Exception as e:
        job.say(f"   the planner didn't answer cleanly ({str(e)[:80]}), so the reel uses a standard plan")
        plan = []
    if not plan:
        # a standard plan that always works: a hook effect at the start, one in the middle, the call to
        # action wall at the end, each on whole sentences
        ss = sentences(tw)
        def near(t, lo=4.5, hi=8.5):
            st = min(ss, key=lambda x: abs(x[0] - t))[0]
            en = next((y for x, y, _ in ss if x >= st and lo <= y - st <= hi), st + 6.5)
            return st, min(en, tlen)
        a = near(0.0); b = near(tlen / 2); c = (max(b[1] + 6, tlen - 6.5), tlen)
        plan = [{"id": "headline-wall", "start": a[0], "end": a[1]}, {"id": "checklist", "start": b[0], "end": b[1]}]
        if c[1] - c[0] >= 3:
            plan.append({"id": "stack", "start": c[0], "end": c[1]})
    ids = {f["mp4"][3:-4] for f in fx_list()}
    chosen, seen, last_end = [], set(), -99.0
    for x in plan:        # keep only real effects, in order, no overlaps, with talking between them
        try:
            fid, s0, e0 = str(x["id"]), float(x["start"]), float(x["end"])
        except (KeyError, TypeError, ValueError):
            continue
        if fid not in ids or fid in seen or not (0 <= s0 < e0 <= tlen + 0.3) or not (2.5 <= e0 - s0 <= 12):
            continue
        if s0 < last_end + 4:
            continue
        chosen.append((fid, s0, min(e0, tlen), x.get("why", ""))); seen.add(fid); last_end = e0
    if not chosen:      # never hand back a reel with no effects: one at the start
        chosen = [("orbit", 0.0, min(tlen, 7.5), "")]
    return finish_reel(job, tight, tlen, tw, chosen)


def finish_reel(job, tight, tlen, tw, chosen):
    job.say("Your reel: " + ", ".join(f"{fx_effect(f)['title']} at {s:.0f} s" for f, s, _, _ in chosen))
    ready = start_captions(job, tight, tlen, [(s0, e0) for _, s0, e0, _ in chosen])
    segs = []
    for k, (fid, s0, e0, _) in enumerate(chosen, 1):
        job.state = f"making effect {k} of {len(chosen)} (each takes a few minutes)"
        eff, cfg, keep, why = effect_settings(job, fid, s0, e0, tw)
        segs.append((s0, e0, render_effect(job, fid, tight, s0, e0, cfg, keep, n=k)))
    finish_timeline(job, tight, tlen, tw, segs, "Full Reel",
                    f"{len(chosen)} effects ({', '.join(fx_effect(f)['title'] for f, _, _, _ in chosen)}), pauses cut, sound cleaned, captions in your brand.", ready)


def deliver(job):
    """Copy every short that passed into Content Ready For Review/<date> <video>/, then check the bytes."""
    good = [x for x in job.shorts if x["ok"]]
    if not good:
        return
    name = re.sub(r"[^\w &-]", "", os.path.splitext(job.name)[0]).strip()[:60]
    dest = os.path.join(drive_folder(), f"{time.strftime('%Y-%m-%d')} {name}")
    os.makedirs(dest, exist_ok=True)
    for x in good:
        src = os.path.join(job.dir, "out", x["file"])
        if not os.path.exists(src):      # they may have moved or deleted a finished video, and that must never stop the next edit
            continue
        shutil.copy2(src, dest)
        if os.path.getsize(os.path.join(dest, x["file"])) != os.path.getsize(src):
            raise RuntimeError(f"The copy of {x['file']} in your folder is the wrong size.")
    job.delivered = dest
    job.say(f"Saved {len(good)} short(s) to {dest.replace(HOME, '~')}")


def ig_post():
    sys.path.insert(0, ENGINE)
    import ig_post as m
    return m


def cover_font():
    f = brand().get("fontfile", "")
    return f if os.path.exists(f) else os.path.join(CAPTIONS, "fonts", next(iter(ALL_FONTS.values())))


def posted_folder():
    """Where a video goes once it is live: the person's own Posted folder, else Posted next to their review folder."""
    f = brand().get("posted_folder") or os.path.join(os.path.dirname(drive_folder()), "Posted")
    os.makedirs(f, exist_ok=True)
    return f


CAPTION_PROMPT = """You write Instagram Reel captions for one small business owner ({name}), in their own voice.
Below is exactly what they say in the video. Write:
1. TITLE: a cover title that starts with "How To" and names the outcome a business owner gets. 3 to 8 words.
2. BODY: the caption, built from THEIR words and stories in the video. Plain first person, the way they talk.
   Say why this matters to a business owner (visibility, inquiries, sales). Keep every number, name and fact exactly
   as they said it and add none of your own. Short paragraphs. No lists, no slogans, no em dashes, no hype words.
   Do NOT write the ending line or a call to action: the page adds that.
3. HASHTAGS: exactly 3, the ones with the most reach for this topic, CamelCase.

Here is a caption they approved, so you can hear their voice (do not copy its facts):
{example}

Answer with JSON only: {{"title": "...", "body": "...", "hashtags": "#One #Two #Three"}}

WHAT THEY SAY IN THE VIDEO:
{words}"""


MUSE_PROMPT = """Write my Instagram Reel caption from what I say in this video. Use my own words and stories, in first person, the way I talk. Keep every number, name and fact exactly as I said it and add nothing of your own. Short paragraphs. No lists, no slogans, no em dashes, no hype words. Do not write a call to action at the end, I add my own.

Give me 3 things:
1. A cover title that starts with "How To" and names what a business owner gets. 3 to 8 words.
2. The caption.
3. Exactly 3 hashtags with the most reach for this topic.

The words below were typed by a machine, so fix any word that is clearly misheard (like a tool name).

WHAT I SAY IN THE VIDEO:
{words}"""


def run_ig_caption(job, video, muse=False):
    """Transcribe the finished video, then Claude writes the How To title, caption and 3 hashtags (2026-10-30).
    muse=True stops after the words and hands back a prompt the person pastes into Muse (Tiff: Muse first, then Publer)."""
    job.state, job.started, job.estimate = "writing your caption", time.time(), 120
    try:
        if muse:
            words, segs, _ = transcribe(job, "auto", src=video)
            said = " ".join(s["text"].strip() for s in segs)[:20000]
            if len(said) < 20:
                raise RuntimeError("I couldn't hear enough words in this video to write from.")
            job.script = json.dumps({"prompt": MUSE_PROMPT.format(words=said)})
            job.state = "done"
            job.say("Your Muse prompt is ready.")
            return job.save()
        exe = claude_cli()
        if not exe or not claude_ready():
            raise RuntimeError("Claude isn't signed in on this computer yet. Finish Set up first.")
        words, segs, _ = transcribe(job, "auto", src=video)
        b = brand()
        example = b.get("ig_example") or "(none yet)"
        prompt = CAPTION_PROMPT.format(name=b.get("name") or "the owner", example=example,
                                       words=" ".join(s["text"].strip() for s in segs)[:20000])
        r = subprocess.run([exe, "-p", prompt, "--output-format", "text"], capture_output=True, text=True,
                           timeout=300, cwd=job.dir)
        m = re.search(r"\{.*\}", r.stdout or "", re.S)
        got = json.loads(m.group(0)) if m else {}
        if not got.get("title") or not got.get("body"):
            raise RuntimeError("The caption came back empty. Try again in a minute.")
        for k in got:
            got[k] = str(got[k]).replace("—", ",").replace("–", ",").strip()
        tags = got.get("hashtags", "").split()[:3]
        got["hashtags"] = " ".join(tags)
        job.script = json.dumps(got)
        job.state = "done"
        job.say("Your caption is ready. Read it before you post.")
    except Exception as e:
        job.state, job.error = "stopped", str(e)[:300]
        job.say("Stopped: " + job.error)
    job.save()


def run_ig_post(job, video, f):
    """Cover, regular Reel, Trial Reel (Manual), read both back, then move to Posted. Tiff's flow, 2026-10-30."""
    job.state, job.started, job.estimate = "posting", time.time(), 1500
    try:
        got = ig_post().post_both(
            video, f["title"], f["body"], f["ending"], f["trial_ending"] or "Follow for more.", f["hashtags"],
            os.path.join(job.dir, "out"), {k: key(k) for k in ("PUBLER_API_KEY", "PUBLER_WORKSPACE_ID")},
            brand()["accent"], cover_font(), FF, FP, job.say, posted_folder())
        job.script = json.dumps(got)
        job.state = "done"
    except Exception as e:
        job.error = str(e)[:400]
        job.say("Stopped: " + job.error)
        job.state = "stopped"
    job.save()


def worker(job, opts):
    with RUN_LOCK:
        os.environ.pop("CME_WORDS", None)
        try:
            job.state = "starting"
            job.started = time.time()
            try:
                secs = float(probe(job.src, count=False)["format"]["duration"])
            except Exception:
                secs = 60
            if opts.get("template") == "reel":
                job.estimate = int(150 + min(secs, 90) / 3 + 4 * 300)
            elif opts.get("template") == "effect":
                job.estimate = int(150 + secs / 6 + 420)        # words, best spot, cut-out (the slow part), render
            elif opts.get("template") == "cleanup":
                job.estimate = int(30 + secs * CLEANUP_SECS_PER_SEC)
            else:
                job.estimate = int(30 + secs / 12 + secs / 480 * 30 + int(opts.get("count", 3)) * 180)
            if opts.get("template") == "fix":
                fix_cleanup(job, opts.get("said", ""))
                opts["template"] = "cleanup"
            elif opts.get("cleanup") and not getattr(job, "cleaned", False) and opts.get("template") != "study":
                run_cleanup(job, hand_back=opts.get("template") == "cleanup")
            if opts.get("template") == "cleanup":
                deliver(job)
                # a 4K video is big: once the copy in their folder is the same size, the job's own copy goes,
                # so a batch of ten doesn't fill the Mac twice over (2026-10-28)
                for x in job.shorts:
                    mine, theirs = os.path.join(job.dir, "out", x["file"]), os.path.join(job.delivered or "", x["file"])
                    if x["ok"] and job.delivered and os.path.exists(mine) and os.path.exists(theirs) \
                            and os.path.getsize(mine) == os.path.getsize(theirs):
                        os.remove(mine)
                job.state = "done" if all(s["ok"] for s in job.shorts) else "done, but a check failed"
                job.save()
                return
            if opts.get("template") == "study":
                job.estimate = 50 * (len(reel_link(opts.get("links", ""))) or 10)
                run_copycat_study(job, opts.get("links", ""))
                job.state = "pick a style"
                job.save()
                return
            if opts.get("template") == "split" or opts.get("full_copy"):
                job.estimate = 20 * 60
                run_ai_edit(job, opts, opts.get("style_settings"), opts.get("style_refs", []))
            elif opts.get("template") in ("effect", "reel"):
                try:
                    if opts["template"] == "effect" and opts.get("effect") in MY_IDS:
                        run_my_effect(job, opts["effect"], opts)
                    elif opts["template"] == "effect" and str(opts.get("effect", "")).startswith("style-"):
                        run_saved_style(job, opts["effect"], opts)
                    elif opts["template"] == "effect":
                        run_effect(job, opts["effect"], opts)
                    else:
                        run_reel(job, opts)
                finally:
                    fx_cleanup(job)
            else:
                run_shorts(job, opts)
            deliver(job)
            job.state = "done" if all(s["ok"] for s in job.shorts) else "done, but a check failed"
        except Exception as e:
            msg = str(e)
            # a dropped Wi-Fi shows up as a page of connection jargon; say it plainly
            if re.search(r"NameResolution|No route to host|Failed to establish a new connection|nodename nor servname", msg):
                msg = "Your internet dropped for a moment. Check your Wi-Fi, then tap the button again."
            job.state, job.error = "stopped", msg
            job.say("STOPPED: " + msg)
            open(os.path.join(job.dir, "log.txt"), "a").write(traceback.format_exc())
        job.save()


# ---------------------------------------------------------------- web

# --- the page and the open Claude chat talk through 2 small files, so a press on the page can wake the chat ---
ASKS_FILE = os.path.join(SAVED, "claude-asks.jsonl")
TALK_FILE = os.path.join(SAVED, "claude-talk.jsonl")
LISTEN_FILE = os.path.join(SAVED, "claude-listening.json")
BUSY_FILE = os.path.join(SAVED, "claude-working.json")
HEARD_FILE = os.path.join(SAVED, "transcription.json")
KEY_FILE = os.path.join(SAVED, "elevenlabs.key")


def job_pictures(job, sub="pics"):
    d = os.path.join(job.dir, sub)
    return [os.path.join(d, x) for x in sorted(os.listdir(d))] if os.path.isdir(d) else []


def claude_state():
    try:
        pid = json.load(open(LISTEN_FILE)).get("pid")
        os.kill(int(pid), 0)
        return "listening"
    except PermissionError:
        return "listening"
    except (OSError, ValueError, TypeError):
        pass
    try:
        if time.time() - json.load(open(BUSY_FILE)).get("at", 0) < 600:
            return "working"
    except (OSError, ValueError):
        pass
    return "off"


def claude_talk(who, text, job_id=""):
    line = {"who": who, "text": str(text)[:2000], "job": job_id or "", "at": time.time()}
    with open(TALK_FILE, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(line, ensure_ascii=False) + "\n")
    return line


def claude_view():
    try:
        rows = [json.loads(x) for x in open(TALK_FILE, encoding="utf-8").read().split("\n")[-31:] if x]
    except (OSError, ValueError):
        rows = []
    return {"state": claude_state(), "talk": rows}


def videos_view():
    rows = []
    for j in JOBS_BY_ID.values():
        rows.append({"id": j.id, "name": j.name, "state": j.state, "cleaned": bool(getattr(j, "cleaned", False)),
                     "made": [s["file"] for s in j.shorts]})
    return sorted(rows, key=lambda r: r["id"], reverse=True)


def reload_jobs():
    """Finished work is still on the disk after a restart, so it stays on the page and can take another edit."""
    if not os.path.isdir(JOBS):
        return
    for name in sorted(os.listdir(JOBS)):
        d = os.path.join(JOBS, name)
        try:
            saved = json.load(open(os.path.join(d, "job.json")))
        except (OSError, ValueError):
            continue
        original = os.path.join(d, "source.mp4")
        clean = os.path.join(d, "cleaned.mov")
        if not os.path.exists(original) and not os.path.exists(clean):
            continue
        j = Job.__new__(Job)
        j.id, j.dir, j.name = name, d, saved.get("name") or name
        j.src, j.original = (clean if os.path.exists(clean) else original), original
        j.error, j.review, j.go, j.started, j.estimate, j.styles, j.script = "", [], threading.Event(), 0.0, 0, [], ""
        j.go.set()
        j.steps = saved.get("steps") or []
        j.delivered = saved.get("delivered") or ""
        j.shorts = [s for s in (saved.get("shorts") or []) if os.path.exists(os.path.join(d, "out", s.get("file", "")))
                    or (j.delivered and os.path.exists(os.path.join(j.delivered, s.get("file", ""))))]
        was = str(saved.get("state") or "")
        j.state = was if was.startswith("done") or was == "stopped" else "stopped"
        if os.path.exists(clean):
            try:
                j.clean_tw = json.load(open(os.path.join(d, "transcript.json")))["words"]
                j.cleaned = True
            except (OSError, ValueError, KeyError):
                pass
        JOBS_BY_ID[name] = j


def transcription_view():
    try:
        engine = json.load(open(HEARD_FILE)).get("engine", "computer")
    except (OSError, ValueError):
        engine = "computer"
    return {"engine": engine, "has_key": os.path.exists(KEY_FILE)}


def transcription_set(body):
    """Tries a new key on a 1 second clip before saving it. A key that's only been stored has proved nothing."""
    engine = "elevenlabs" if body.get("engine") == "elevenlabs" else "computer"
    key = str(body.get("key") or "").strip()
    if engine == "elevenlabs" and not key and not os.path.exists(KEY_FILE):
        return 400, {"error": "Paste your ElevenLabs key first."}
    if key:
        sys.path.insert(0, ENGINE)
        import transcribe as T
        with tempfile.TemporaryDirectory(prefix="key_") as tmp:
            one = os.path.join(tmp, "one.mp3")
            subprocess.run([FF, "-v", "error", "-f", "lavfi", "-i", "sine=frequency=300:duration=1", "-y", one], check=True)
            said = T.eleven_try(one, key)
        if said:
            return 400, {"error": said}
        fd = os.open(KEY_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as fh:
            fh.write(key)
    json.dump({"engine": engine}, open(HEARD_FILE, "w"))
    return 200, transcription_view()


SHORTS_FILE = os.path.join(SAVED, "shorts-setup.json")
SHORTS_ASK = [
    ("name", "What's your name or channel name?"),
    ("about", "What are your videos about?"),
    ("who", "Who are they for?"),
    ("opens", "How should a short open? Like: a bold claim, a number, or a question."),
    ("ends", "How should a short end? Like: comment a word, follow me, or a final line."),
    ("never", "What should never make it in? Like: side chat, prices or client names."),
    ("length", "How long should your shorts feel? Like: quick under 30 seconds, or up to 45."),
    ("words", "Any words you always say, or names we should spell right?"),
    ("prefs", "Anything else about how you like your edits?"),
]


def shorts_setup():
    try:
        d = json.load(open(SHORTS_FILE))
    except (OSError, ValueError):
        d = {}
    return {"unlocked": bool(d.get("unlocked")), "answers": d.get("answers") or {}, "questions": SHORTS_ASK, "has_key": bool(key("GROQ_API_KEY"))}


def shorts_save(changes=None, unlocked=None):
    d = shorts_setup()
    answers = {**d["answers"], **{k: str(v)[:400] for k, v in (changes or {}).items() if k in dict(SHORTS_ASK)}}
    json.dump({"answers": answers, "unlocked": d["unlocked"] if unlocked is None else unlocked}, open(SHORTS_FILE, "w"), indent=1)
    return shorts_setup()


def shorts_taste():
    """Their saved answers steer which moments get picked and what the hook says."""
    a = shorts_setup()["answers"]
    said = [f"{q}: {a[k]}" for k, q in SHORTS_ASK if a.get(k)]
    return ("\nThis creator told us:\n" + "\n".join(said) + "\nFollow what they said.\n\n") if said else ""


def shorts_key_try(k):
    import requests
    try:
        r = requests.get("https://api.groq.com/openai/v1/models", headers={"Authorization": f"Bearer {k}"}, timeout=(10, 30))
    except Exception:
        return "We couldn't reach Groq. Check your internet and try again."
    return "" if r.status_code == 200 else ("Groq said no to that key. Copy it again from the Groq page." if r.status_code in (401, 403) else f"Groq said {r.status_code}. Try again in a minute.")


def shorts_key_save(k):
    os.makedirs(os.path.dirname(KEYS), exist_ok=True)
    try:
        old = open(KEYS).read()
    except OSError:
        old = ""
    keep = "".join(x + "\n" for x in old.splitlines() if not x.startswith("GROQ_API_KEY="))
    fd = os.open(KEYS, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as fh:
        fh.write(keep + f"GROQ_API_KEY={k}\n")


def finish_wide(job, kind, meta, tight, tlen, tw, cfg):
    """The YouTube edits keep the video's own wide shape, so they skip the phone captions and draw their own."""
    v = stream(probe(tight, count=False), "video")
    w, h = int(v["width"]), int(v["height"])
    if w <= h:
        raise RuntimeError(f"{meta['name']} is for wide videos, and this one is tall. Try a reel edit for this one.")
    name = re.sub(r"[^\w &-]", "", os.path.splitext(job.name)[0]).strip()[:50]
    out = os.path.join(job.dir, "out", f"{name} - {meta['name']}.mp4")
    job.state = f"adding {meta['name']}"
    r = subprocess.run([VENV_PY, MYFX, kind, tight, out, "--start", "0", "--end", f"{tlen:.3f}", "--config", json.dumps(cfg)], capture_output=True, text=True)
    if r.returncode or not os.path.exists(out):
        raise RuntimeError(f"{meta['name']} didn't render: " + (r.stderr or r.stdout).strip()[-200:])
    v2 = stream(probe(out, count=False), "video")
    ok, checks = ledger(out, f"{v2['width']}x{v2['height']}", tlen)
    checks["keeps your wide shape"] = [f"{v2['width']}x{v2['height']}", f"{w}x{h}", abs(int(v2["width"]) - w) <= 1 and abs(int(v2["height"]) - h) <= 1]
    ok = ok and checks["keeps your wide shape"][2]
    sheet = out[:-4] + " frames.jpg"
    contact_sheet(out, sheet)
    job.shorts.append({"file": os.path.basename(out), "sheet": os.path.basename(sheet), "ok": ok, "seconds": round(tlen, 1), "from": "0:00", "hook": [],
                       "why": f"{meta['name']}, pauses cut, sound cleaned, captions in your brand.", "checks": checks, "fx_at": [0.0, tlen]})
    job.say(f"{meta['name']} {'PASSED' if ok else 'FAILED'} the checks")
    job.save()


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, code, body, ctype="application/json", cookie=None):
        if not isinstance(body, bytes):
            body = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def signed_in(self):
        return f"cd_auth={LOGIN_TOKEN}" in (self.headers.get("Cookie") or "")

    def gate(self, p):
        """True when the request may go on; otherwise it has already been answered."""
        return True
        if p in OPEN_PATHS or self.signed_in():
            return True
        if p.startswith("/api/") or p.startswith("/files/"):
            self.send(401, {"error": "Sign in first."})
        else:
            self.send(200, open(os.path.join(HERE, "login.html"), "rb").read(), "text/html; charset=utf-8")
        return False

    def video(self, f):
        size = os.path.getsize(f)
        m = re.match(r"bytes=(\d+)-(\d*)", self.headers.get("Range") or "")
        a = int(m.group(1)) if m else 0
        b = min(int(m.group(2)) if m and m.group(2) else size - 1, size - 1)
        self.send_response(206 if m else 200)
        self.send_header("Content-Type", "video/mp4")
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(b - a + 1))
        if m:
            self.send_header("Content-Range", f"bytes {a}-{b}/{size}")
        self.end_headers()
        with open(f, "rb") as fh:
            fh.seek(a)
            left = b - a + 1
            while left:
                chunk = fh.read(min(left, 1 << 20))
                if not chunk:
                    break
                self.wfile.write(chunk)
                left -= len(chunk)

    def do_GET(self):
        p = unquote(self.path.split("?")[0])
        if not self.gate(p):
            return
        if p == "/login":
            return self.send(200, open(os.path.join(HERE, "login.html"), "rb").read(), "text/html; charset=utf-8")
        if p == "/api/version":
            v = latest_version()
            return self.send(200, {"current": VERSION, "latest": v, "update": bool(v) and v > VERSION})
        if p == "/api/busy":
            # what is running right now; checked before anyone restarts this server (2026-10-27 lesson)
            return self.send(200, [{"id": j.id, "name": j.name, "state": j.state} for j in JOBS_BY_ID.values()
                                   if j.state not in ("waiting", "stopped", "pick a style", "pick your hooks")
                                   and not j.state.startswith("done")])
        if p == "/":
            return self.send(200, open(os.path.join(HERE, "index.html"), "rb").read(), "text/html; charset=utf-8")
        if p == "/split-example.mp4":
            f = os.path.join(SPLIT, "examples/demo/preview.mp4")
            return self.send(200, open(f, "rb").read(), "video/mp4") if os.path.exists(f) else self.send(404, {"error": "not found"})
        if p == "/ajene-cards.json":
            f = os.path.join(AJENE_PACK, "cards.json")
            if not os.path.exists(f):
                return self.send(200, [])
            cards = json.load(open(f))
            try:      # what each edit does, in the pack's own words, so a card says more than its name
                cat = json.load(open(os.path.join(HOME, ".claude/skills/edit-studio/catalog/catalog.json")))
                blurbs = {s["id"]: s.get("blurb", "") for s in cat.get("styles", [])}
                for c in cards:
                    c["blurb"] = blurbs.get(c.get("style"), "")
            except Exception:
                pass
            return self.send(200, cards)
        if p.startswith("/ajene-sample/"):      # the pack's real sample of each edit, from her own install
            name = os.path.basename(p)
            f = os.path.join(HOME, ".claude/skills/edit-studio/app/public/styles", name)
            kind = "video/mp4" if name.endswith(".mp4") else "image/jpeg"
            return self.send(200, open(f, "rb").read(), kind) if os.path.exists(f) else self.send(404, {"error": "not found"})
        if p.startswith("/ajene-card/"):
            f = os.path.join(AJENE_PACK, "cards", os.path.basename(p))
            return self.send(200, open(f, "rb").read(), "image/jpeg") if os.path.exists(f) else self.send(404, {"error": "not found"})
        if p == "/showreel-example.mp4":
            f = os.path.join(HERE, "showreel-example.mp4")
            return self.send(200, open(f, "rb").read(), "video/mp4") if os.path.exists(f) else self.send(404, {"error": "not found"})
        if p == "/favicon.ico":
            p = "/icon.png"
        if p in ("/manifest.json", "/icon.png"):
            f = os.path.join(HERE, p[1:])
            return self.send(200, open(f, "rb").read(), "application/manifest+json" if p.endswith("json") else "image/png")
        if p == "/fx.json":
            return self.send(200, my_fx_list() + fx_list())
        if p.startswith("/fx/"):
            name = os.path.basename(p)
            base = MYFX_DIR if name.startswith("tiff-") else style_dir(os.path.splitext(name)[0]) if name.startswith("style-") else FX_DIR
            f = os.path.realpath(os.path.join(base, os.path.basename(p)))
            if not f.startswith(os.path.realpath(base)) or not os.path.isfile(f):
                return self.send(404, {"error": "not found"})
            if f.endswith(".mp4"):
                return self.video(f)
            return self.send(200, open(f, "rb").read(), "image/jpeg")
        if p in ("/style.css", "/app.js", "/setup-boxes.js"):
            return self.send(200, open(os.path.join(HERE, p[1:]), "rb").read(),
                             "text/css" if p.endswith("css") else "text/javascript")
        if p in ("/brand-asset/logo", "/brand-asset/music"):
            f = brand().get(p.rsplit("/", 1)[1])
            if not f or not os.path.exists(f):
                return self.send(404, {"error": "not found"})
            ext = os.path.splitext(f)[1].lower()
            return self.send(200, open(f, "rb").read(), {".png": "image/png", ".webp": "image/webp", ".mp3": "audio/mpeg",
                             ".m4a": "audio/mp4", ".wav": "audio/wav", ".aac": "audio/aac"}.get(ext, "image/jpeg"))
        if p.startswith("/font/"):
            name = unquote(p[6:])
            if name == OWN_FONT and os.path.exists(brand().get("fontfile", "")):
                return self.send(200, open(brand()["fontfile"], "rb").read(), "font/ttf")
            if name not in ALL_FONTS or not os.path.exists(os.path.join(CAPTIONS, "fonts", ALL_FONTS[name])):
                return self.send(404, {"error": "not found"})
            return self.send(200, open(os.path.join(CAPTIONS, "fonts", ALL_FONTS[name]), "rb").read(), "font/ttf")
        if p == "/api/brand":
            b = brand()
            return self.send(200, {"name": b["name"], "accent": b["accent"], "font": b["font"],
                                   "cta": b.get("cta", ""), "has_logo": bool(b.get("logo")), "has_music": bool(b.get("music")),
                                   "my_style": {k: v for k, v in (b.get("my_style") or {}).items() if k in ("name", "traits", "saved")} or None,
                                   "fonts": ([OWN_FONT] if os.path.exists(b.get("fontfile", "")) else []) + list(ALL_FONTS), "labels": FONT_LABELS, "capcut": list(CAPCUT), "custom": bool(b.get("preset")), "folder": drive_folder().replace(HOME, "~"),
                                   "publer": bool(key("PUBLER_API_KEY") and key("PUBLER_WORKSPACE_ID")), "ig_ending": b.get("ig_ending", "")})
        if p == "/api/claude":
            return self.send(200, claude_view())
        if p == "/api/videos":
            return self.send(200, videos_view())
        if p == "/api/shorts-setup":
            return self.send(200, shorts_setup())
        if p == "/api/transcription":
            return self.send(200, transcription_view())
        if p == "/api/setup":
            return self.send(200, setup_status())
        if p == "/api/templates":
            ai = os.path.exists(os.path.join(SPLIT, "node_modules")) and claude_ready()
            ajene = os.path.isdir(AJENE_PACK) and os.path.exists(AJENE_STUDIO)
            return self.send(200, [dict(t, live=True) if (t["id"] == "split" and ai) or (t["id"] == "ajene" and ajene) else t for t in TEMPLATES])
        if p.startswith("/api/job/"):
            j = JOBS_BY_ID.get(p.split("/")[3])
            return self.send(200, j.view()) if j else self.send(404, {"error": "no such job"})
        if p.startswith("/files/"):
            _, _, jid, name = p.split("/", 3)
            f = os.path.realpath(os.path.join(JOBS, jid, "out", name))
            j = JOBS_BY_ID.get(jid)
            if not os.path.isfile(f) and j and j.delivered and os.sep not in name:
                f = os.path.join(j.delivered, name)       # a cleaned 4K video lives only in their folder
            elif not f.startswith(os.path.realpath(JOBS)):
                return self.send(404, {"error": "not found"})
            if not os.path.isfile(f):
                return self.send(404, {"error": "not found"})
            if f.endswith(".mp4"):
                return self.video(f)
            return self.send(200, open(f, "rb").read(), "image/jpeg")
        if p.startswith("/api/reveal/"):
            j = JOBS_BY_ID.get(p.split("/")[3])
            if j:
                subprocess.run(["open", j.delivered if j.delivered and os.path.isdir(j.delivered) else os.path.join(j.dir, "out")])
            return self.send(200, {"ok": bool(j)})
        self.send(404, {"error": "not found"})

    def do_POST(self):
        p = self.path.split("?")[0]
        n = int(self.headers.get("Content-Length", 0))
        here = (self.headers.get("Host") or "").split(":")[0]
        came = self.headers.get("Origin")
        if here not in ("127.0.0.1", "localhost") or (came and re.sub(r":\d+$", "", came) not in ("http://127.0.0.1", "http://localhost")):
            return self.send(403, {"error": "Only this page can do that."})
        if p == "/api/shorts-setup":
            return self.send(200, shorts_save(json.loads(self.rfile.read(n) or b"{}").get("answers")))
        if p == "/api/shorts-unlock":
            body = json.loads(self.rfile.read(n) or b"{}")
            typed = str(body.get("key") or "").strip()
            if typed:
                said = shorts_key_try(typed)
                if said:
                    return self.send(400, {"error": said})
                shorts_key_save(typed)
            if not key("GROQ_API_KEY"):
                return self.send(400, {"error": "Paste your free Groq key first."})
            r = subprocess.run(["zsh", os.path.join(HERE, "first-run.sh")], capture_output=True, text=True)
            if r.returncode:
                return self.send(400, {"error": "Something didn't download. Try again, or send Tiff a screenshot."})
            return self.send(200, shorts_save(unlocked=True))
        if p == "/api/pictures":
            j = JOBS_BY_ID.get(parse_qs(urlparse(self.path).query).get("job", [""])[0])
            name = os.path.basename(unquote(self.headers.get("X-File-Name", "picture.jpg")))
            ext = os.path.splitext(name)[1].lower()
            clip = ext in (".mp4", ".mov", ".m4v")
            if not j or (not clip and ext not in (".jpg", ".jpeg", ".png", ".webp")) or n > (2_000_000_000 if clip else 25_000_000):
                return self.send(400, {"error": "Use a JPG, PNG or WEBP picture under 25 MB, or an MP4 or MOV video under 2 GB."})
            d = os.path.join(j.dir, "clips" if clip else "pics")
            os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, f"{len(os.listdir(d)):03d}{ext}"), "wb") as fh:
                fh.write(self.rfile.read(n))
            return self.send(200, {"count": len(os.listdir(d))})
        if p == "/api/claude/ask":
            if not came:
                return self.send(403, {"error": "Only this page can do that."})
            body = json.loads(self.rfile.read(n) or b"{}")
            text = str(body.get("text") or "").strip()[:2000]
            if not text:
                return self.send(400, {"error": "Type what you want first."})
            if claude_state() != "listening":
                return self.send(400, {"error": "Claude isn't connected yet. Open a Claude Code chat and type /content-made-easy."})
            j = JOBS_BY_ID.get(body.get("job") or "")
            line = {"text": text, "job": j.id if j else "", "video": j.name if j else "", "cleaned": bool(getattr(j, "cleaned", False)) if j else False}
            with open(ASKS_FILE, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(line, ensure_ascii=False) + "\n")
            claude_talk("you", text, line["job"])
            return self.send(200, claude_view())
        if p == "/api/claude/say":
            body = json.loads(self.rfile.read(n) or b"{}")
            claude_talk("claude", body.get("text") or "", body.get("job") or "")
            return self.send(200, {"ok": True})
        if p == "/api/transcription":
            code, out = transcription_set(json.loads(self.rfile.read(n) or b"{}"))
            return self.send(code, out)
        if p == "/api/login":
            body = json.loads(self.rfile.read(n) or b"{}")
            if str(body.get("user", "")).strip().lower() == LOGIN_USER and str(body.get("pass", "")) == LOGIN_PASS:
                return self.send(200, {"ok": True}, cookie=f"cd_auth={LOGIN_TOKEN}; Path=/; Max-Age=2592000; SameSite=Lax; HttpOnly")
            return self.send(401, {"error": "That username or password isn't right. Check the welcome message for them."})
        if not self.gate(p):
            return
        if p == "/api/ajene/open":
            if not os.path.exists(AJENE_STUDIO):
                return self.send(404, {"error": "Edit Studio is not installed on this computer."})
            # its first start builds its own Python, about a minute. It stays up after this answers.
            r = subprocess.run(["bash", AJENE_STUDIO, "--no-open"], capture_output=True, text=True, timeout=300)
            if r.returncode:
                return self.send(500, {"error": (r.stderr or r.stdout)[-300:]})
            return self.send(200, {"url": "http://localhost:4191"})
        if p == "/api/feedback":
            body = json.loads(self.rfile.read(n) or b"{}")
            job = JOBS_BY_ID.get(body.get("job"))
            if not job:
                return self.send(404, {"error": "no such job"})
            f = os.path.join(job.dir, "feedback.json")
            notes = json.load(open(f)) if os.path.exists(f) else []
            notes.append({"file": str(body.get("file", ""))[:200], "verdict": str(body.get("verdict", ""))[:20],
                          "note": str(body.get("note", ""))[:2000], "at": time.strftime("%Y-%m-%d %H:%M")})
            json.dump(notes, open(f, "w"), indent=1)
            return self.send(200, {"ok": True})
        if p == "/api/update":
            busy = [j for j in JOBS_BY_ID.values() if j.state not in ("waiting", "stopped", "pick a style", "pick your hooks")
                    and not j.state.startswith("done")]
            if busy:
                return self.send(400, {"error": "A video is still being made. Update when it's done."})
            try:
                apply_update()
            except Exception as e:
                return self.send(400, {"error": f"The update didn't work: {str(e)[:160]}. Your dashboard is unchanged."})
            self.send(200, {"ok": True})
            threading.Timer(1.0, lambda: os.execv(sys.executable, [sys.executable] + sys.argv)).start()
            return
        if p == "/api/brand-asset":
            kind = self.headers.get("X-Kind", "")
            name = os.path.basename(unquote(self.headers.get("X-File-Name", "file")))
            ext = os.path.splitext(name)[1].lower()
            ok_ext = {"logo": (".png", ".jpg", ".jpeg", ".webp"), "music": (".mp3", ".m4a", ".wav", ".aac")}.get(kind, ())
            if ext not in ok_ext or n > 60e6:
                return self.send(400, {"error": "Logo: a .png or .jpg. Music: an .mp3, .m4a or .wav under 60 MB."})
            os.makedirs(ASSETS, exist_ok=True)
            for old in os.listdir(ASSETS):
                if old.startswith(kind + "."):
                    os.remove(os.path.join(ASSETS, old))
            dst = os.path.join(ASSETS, kind + ext)
            with open(dst, "wb") as f:
                left = n
                while left:
                    chunk = self.rfile.read(min(left, 8 << 20))
                    if not chunk:
                        break
                    f.write(chunk); left -= len(chunk)
            if kind == "music" and not video_secs(dst):
                os.remove(dst)
                return self.send(400, {"error": "That music file wouldn't play. Try an .mp3."})
            b = brand(); b[kind] = dst
            json.dump(b, open(BRAND_FILE, "w"), indent=1)
            return self.send(200, {"ok": True, "name": name})
        if p == "/api/brand-asset-remove":
            body = json.loads(self.rfile.read(n) or b"{}")
            kind = body.get("kind")
            b = brand()
            if kind in ("logo", "music") and b.get(kind):
                if os.path.exists(b[kind]) and os.path.dirname(b[kind]) == ASSETS:
                    os.remove(b[kind])
                b[kind] = ""
                json.dump(b, open(BRAND_FILE, "w"), indent=1)
            return self.send(200, {"ok": True})
        if p == "/api/brand-video":
            name = os.path.basename(unquote(self.headers.get("X-File-Name", "style.mp4")))
            if not re.search(r"\.(mp4|mov|m4v)$", name, re.I) or n > 600e6:
                return self.send(400, {"error": "Use an .mp4 or .mov video under 600 MB."})
            work = tempfile.mkdtemp(prefix="brand_", dir=JOBS)
            src = os.path.join(work, "style" + os.path.splitext(name)[1].lower())
            with open(src, "wb") as f:
                left = n
                while left:
                    chunk = self.rfile.read(min(left, 8 << 20))
                    if not chunk:
                        break
                    f.write(chunk); left -= len(chunk)
            try:
                got = brand_from_video(src, work)
            except Exception as e:
                return self.send(400, {"error": str(e)})
            finally:
                shutil.rmtree(work, ignore_errors=True)
            return self.send(200, got)
        if p == "/api/brand-site":
            try:
                return self.send(200, brand_from_site(str(json.loads(self.rfile.read(n) or b"{}").get("link", "")).strip()))
            except Exception:
                return self.send(400, {"error": "We couldn't open that website. Check the link and try again."})
        if p == "/api/brand-link":
            body = json.loads(self.rfile.read(n) or b"{}")
            text = str(body.get("link", ""))
            links = reel_link(text) or profile_reels(text, top=1)
            if not links:
                return self.send(400, {"error": "Paste an Instagram reel or page link."})
            work = tempfile.mkdtemp(prefix="brand_", dir=JOBS)
            try:
                src = os.path.join(work, "style.mp4")
                fetch_reel(links[0], src)
                return self.send(200, brand_from_video(src, work))
            except Exception as e:
                return self.send(400, {"error": str(e)})
            finally:
                shutil.rmtree(work, ignore_errors=True)
        if p == "/api/upload":
            name = os.path.basename(unquote(self.headers.get("X-File-Name", "video.mp4")))
            if not re.search(r"\.(mp4|mov|m4v)$", name, re.I):
                return self.send(400, {"error": "Use an .mp4 or .mov video."})
            if not tools_ready():
                return self.send(400, {"error": SETUP_FIRST})
            if shutil.disk_usage(HOME).free < n + 1.5e9:
                return self.send(400, {"error": "Not enough free disk space for this video."})
            job = Job("", name)
            job.src = os.path.join(job.dir, "source" + os.path.splitext(name)[1].lower())
            with open(job.src, "wb") as f:
                left = n
                while left:
                    chunk = self.rfile.read(min(left, 8 << 20))
                    if not chunk:
                        break
                    f.write(chunk); left -= len(chunk)
            if os.path.getsize(job.src) != n:
                return self.send(400, {"error": "The upload stopped part way. Try again."})
            job.say(f"Uploaded {name} ({n / 1e6:.0f} MB)")
            return self.send(200, {"job": job.id, "secs": video_secs(job.src)})
        body = json.loads(self.rfile.read(n) or b"{}")
        if p == "/api/join":
            ids = body.get("jobs") or []
            parts = [JOBS_BY_ID.get(str(i)) for i in ids]
            if not 2 <= len(parts) <= 10 or not all(j and j.src and os.path.isfile(j.src) for j in parts):
                return self.send(400, {"error": "Drop 2 to 10 videos to join them."})
            if shutil.disk_usage(HOME).free < 2 * sum(os.path.getsize(j.src) for j in parts) + 1.5e9:
                return self.send(400, {"error": "Not enough free disk space to join these."})
            job = Job("", f"Joined {len(parts)} videos")
            job.src = os.path.join(job.dir, "source.mov")
            try:
                how = join_videos([j.src for j in parts], job.src)
            except Exception as e:
                return self.send(500, {"error": f"Couldn't join those videos: {e}"})
            job.say(f"Joined {len(parts)} videos ({how}): " + ", ".join(f"{n + 1}) {j.name}" for n, j in enumerate(parts)))
            for j in parts:      # the single uploads are inside the joined video now; their folders go
                if re.fullmatch(r"\d{8}-\d{6}-[0-9a-f]{4}", j.id) and j.dir == os.path.join(JOBS, j.id):
                    shutil.rmtree(j.dir, ignore_errors=True)
                    JOBS_BY_ID.pop(j.id, None)
            return self.send(200, {"job": job.id, "secs": video_secs(job.src)})
        if p == "/api/ajene/pick":
            job = JOBS_BY_ID.get(body.get("job"))
            if not job or not os.path.isfile(job.src):
                return self.send(400, {"error": "Drop your video in first (step 4), then tap the edit."})
            try:
                return self.send(200, ajene_pick(job, str(body.get("style", ""))))
            except Exception as e:
                return self.send(500, {"error": f"Edit Studio did not take it: {e}"})
        if p == "/api/use-path":
            src = os.path.expanduser(body.get("path", "").strip().strip("'\""))
            if not tools_ready():
                return self.send(400, {"error": SETUP_FIRST})
            if not os.path.isfile(src):
                return self.send(400, {"error": "I can't find a video at that location."})
            # Downloads, Desktop and Documents are guarded by macOS: opening a file there can wait forever
            # on a permission box nobody sees. Try one byte first so the person hears about it.
            try:
                subprocess.run(["head", "-c", "1", src], capture_output=True, timeout=6)
            except subprocess.TimeoutExpired:
                return self.send(400, {"error": "Your Mac is asking permission to open that folder. Click Allow on the box that "
                                                "popped up and try again, or just drag the video into the box above instead."})
            job = Job(src, os.path.basename(src))
            job.say("Using the video where it already is (no copy made)")
            return self.send(200, {"job": job.id, "secs": video_secs(src)})
        if p == "/api/save-styles":
            src_job = JOBS_BY_ID.get(body.get("style_job", ""))
            sj = str(body.get("style_job", ""))
            if not src_job and re.fullmatch(r"[\w-]+", sj) and os.path.exists(os.path.join(JOBS, sj, "styles.json")):
                # the dashboard was restarted after the study: the study itself is still on disk
                src_job = type("Study", (), {"dir": os.path.join(JOBS, sj),
                                             "styles": json.load(open(os.path.join(JOBS, sj, "styles.json")))["styles"]})()
            picks = {str(k): str(v)[:40] for k, v in (body.get("styles") or {}).items()}
            if not src_job or not src_job.styles or not picks:
                return self.send(400, {"error": "Study the reels first, then tick the styles to save."})
            m = re.search(r"instagram\.com/([\w.]+)/", " ".join(r_ for st in src_job.styles for r_ in st.get("reels", [])))
            got = save_styles(src_job, picks, f"@{m.group(1)}'s reels" if m and m.group(1) not in ("p", "reel", "reels") else "the reels you pasted")
            return self.send(200, {"saved": [x["name"] for x in got]})
        if p == "/api/mystyle":
            src_job = JOBS_BY_ID.get(body.get("style_job", ""))
            st = next((x for x in (src_job.styles if src_job else []) if x["id"] == body.get("style")), None)
            if not st:
                return self.send(400, {"error": "Study your reels first, then tap the style that's you."})
            settings = dict(st["settings"])
            if body.get("font") in ALL_FONTS:
                settings["font"] = body["font"]
                if not settings.get("headline"):
                    settings["hook_font"] = body["font"]
            if re.fullmatch(r"#[0-9A-Fa-f]{6}", str(body.get("accent", ""))):
                settings["accent"] = body["accent"].upper()
            b = brand()
            b["my_style"] = {"settings": settings, "refs": st.get("refs", []), "name": st.get("name", "Your style"),
                             "traits": st.get("traits", []), "saved": time.strftime("%Y-%m-%d")}
            json.dump(b, open(BRAND_FILE, "w"), indent=1)
            return self.send(200, {"ok": True})
        if p == "/api/brand":
            b = brand()
            b["name"] = str(body.get("name", b["name"]))[:60]
            if "cta" in body:      # their own call to action, used by every ending effect (2026-10-27)
                b["cta"] = str(body.get("cta") or "")[:60]
            if re.fullmatch(r"#?[0-9A-Fa-f]{6}", str(body.get("accent", ""))):
                b["accent"] = body["accent"].lstrip("#").upper()
            if body.get("font") in ALL_FONTS or (body.get("font") == OWN_FONT and os.path.exists(b.get("fontfile", ""))):
                b["font"] = body["font"]
            json.dump(b, open(BRAND_FILE, "w"), indent=1)
            return self.send(200, {"ok": True})
        if p == "/api/approve":
            job = JOBS_BY_ID.get(body.get("job"))
            if not job or job.state != "pick your hooks":
                return self.send(400, {"error": "Nothing is waiting for you to pick."})
            got = {int(x["i"]): x for x in body.get("items", [])}
            for r in job.review:
                x = got.get(r["i"], {})
                r["keep"] = bool(x.get("keep", True))
                if isinstance(x.get("hook"), list) and len(x["hook"]) == 2:
                    r["hook"] = [safe_hook(h) for h in x["hook"]]
            job.go.set()
            return self.send(200, {"ok": True})
        if p == "/api/ig-cover":
            title = str(body.get("title", "")).strip()[:80]
            if len(title) < 4:
                return self.send(400, {"error": "Type the How To title for the cover first."})
            job = Job("", "instagram cover")
            try:
                ig_post().cover(title, os.path.join(job.dir, "out", "cover.png"), brand()["accent"], cover_font())
            except Exception as e:
                return self.send(400, {"error": f"The cover didn't work: {str(e)[:160]}"})
            job.state = "done"
            return self.send(200, {"cover": f"/files/{job.id}/cover.png", "grid": f"/files/{job.id}/cover-grid.png"})
        if p in ("/api/ig-post", "/api/ig-caption"):
            src_job = JOBS_BY_ID.get(body.get("job"))
            name = os.path.basename(str(body.get("file", "")))
            video = ""
            if src_job and name:
                for folder in (src_job.delivered, os.path.join(src_job.dir, "out")):
                    if folder and os.path.isfile(os.path.join(folder, name)):
                        video = os.path.join(folder, name)
                        break
            if not video:
                return self.send(400, {"error": "I can't find that video anymore."})
            if p == "/api/ig-caption":
                job = Job("", "instagram caption")
                threading.Thread(target=run_ig_caption, args=(job, video, body.get("muse") is True), daemon=True).start()
                return self.send(200, {"job": job.id})
            f = {k: str(body.get(k, "")).strip() for k in ("title", "body", "ending", "trial_ending", "hashtags")}
            if len(f["title"]) < 4 or len(f["body"]) < 10:
                return self.send(400, {"error": "Fill in the cover title and the caption first."})
            if body.get("confirm") is not True:
                return self.send(400, {"error": "Tick the box that says you're ready to post."})
            if not (key("PUBLER_API_KEY") and key("PUBLER_WORKSPACE_ID")):
                return self.send(400, {"error": "Publer isn't connected yet. Add your Publer API key first."})
            job = Job("", "instagram post")
            threading.Thread(target=run_ig_post, args=(job, video, f), daemon=True).start()
            return self.send(200, {"job": job.id})
        if p == "/api/script":
            idea = str(body.get("idea", "")).strip()[:8000]
            if len(idea) < 8:
                return self.send(400, {"error": "Type or paste your idea first. A sentence is enough."})
            job = Job("", "script")
            threading.Thread(target=run_script, args=(job, idea, str(body.get("voice", "")).strip()[:3000]), daemon=True).start()
            return self.send(200, {"job": job.id})
        if p == "/api/study":
            job = Job("", "copycat study")
            job.say("Studying the reels you pasted")
            threading.Thread(target=worker, args=(job, {"template": "study", "links": str(body.get("links", ""))[:4000]}), daemon=True).start()
            return self.send(200, {"job": job.id})
        if p == "/api/run":
            job = JOBS_BY_ID.get(body.get("job"))
            if not job:
                return self.send(404, {"error": "Upload a video first."})
            if not tools_ready():
                return self.send(400, {"error": SETUP_FIRST})
            if body.get("template") == "effect" and body.get("effect") in MY_IDS:
                # 2026-10-31: Green Screen Article brings its picture along as a data URL
                m = re.match(r"data:image/(png|jpe?g|webp);base64,(.+)", str(body.get("picture") or ""), re.S)
                if body["effect"] == "tiff-article-screen":
                    if not m:
                        return self.send(400, {"error": "Add your picture first (a PNG or JPG of the article or screenshot)."})
                    import base64
                    pic = os.path.join(job.dir, "picture." + m.group(1).replace("jpeg", "jpg"))
                    with open(pic, "wb") as fh:
                        fh.write(base64.b64decode(m.group(2)))
                    body["picture"] = pic
                else:
                    body.pop("picture", None)
            elif body.get("template") == "effect" and str(body.get("effect", "")).startswith("style-"):
                if body["effect"] not in {x["id"] for x in saved_styles()}:
                    return self.send(400, {"error": "That saved style isn't on this computer anymore. Study and save it again."})
            elif body.get("template") == "effect":
                if not re.fullmatch(r"[a-z-]+", str(body.get("effect", ""))) or \
                        not os.path.exists(os.path.join(FX_KIT, "engine/effects", f"{body['effect']}.json")):
                    return self.send(400, {"error": "The effects kit isn't set up on this computer yet."})
            elif body.get("template") == "copycat":
                src_job = JOBS_BY_ID.get(body.get("style_job", ""))
                st = next((x for x in (src_job.styles if src_job else []) if x["id"] == body.get("style")), None)
                if not st:
                    return self.send(400, {"error": "Study a creator's reels first, then pick a style."})
                body["style_settings"] = dict(st["settings"])
                body["style_refs"] = st.get("refs", [])
                # 2026-10-27: anything that is the creator's own (handle, call to action, link, price) is asked
                # about first. The person's answer goes on the video, never the creator's words.
                answers, ans = {}, body.get("answers") or {}
                for q in st.get("ask", []):
                    a = str(ans.get(q["id"], "")).strip()[:40]
                    if not a and not ans.get(q["id"] + "_skip"):
                        return self.send(400, {"error": "Answer the questions on the style card first (or tick Leave it out)."})
                    import difflib
                    theirs = re.sub(r"\W", "", q["theirs"].lower())
                    mine = re.sub(r"\W", "", a.lower())
                    if mine and (difflib.SequenceMatcher(None, mine, theirs).ratio() > 0.75 or
                                 any(len(w) > 4 and w in mine for w in re.findall(r"[a-z0-9_.]+", q["theirs"].lower()) if w not in ("following", "follow"))):
                        return self.send(400, {"error": f"\"{a}\" is the creator's own. Put yours there instead."})
                    answers[q["id"]] = a
                body["answers"] = answers
                body["style_moves"] = st.get("moves") or {}
                if body.get("style_font") in ALL_FONTS:              # the person's fix on the card wins over our guess
                    body["style_settings"]["font"] = body["style_font"]
                    if not st["settings"].get("headline"):
                        body["style_settings"]["hook_font"] = body["style_font"]
                if re.fullmatch(r"#[0-9A-Fa-f]{6}", str(body.get("style_accent", ""))):
                    body["style_settings"]["accent"] = body["style_accent"].upper()
                body["template"] = "shorts"
            elif body.get("template") == "mystyle":
                mine = brand().get("my_style")
                if not mine:
                    return self.send(400, {"error": "Study your own reels first and pick your style. Then every video uses it."})
                body["style_settings"] = dict(mine["settings"])
                body["style_refs"] = mine.get("refs", [])
                body["template"] = "shorts"
            elif body.get("template") == "split":
                pass
            elif body.get("template") == "cleanup":
                body["cleanup"] = True
            elif body.get("template") == "fix":
                if not str(body.get("said", "")).strip():
                    return self.send(400, {"error": "Say or type what to fix first."})
                if not getattr(job, "source_words", None):
                    return self.send(400, {"error": "Clean the video first, then tell it what to fix."})
            elif body.get("template") == "reel":
                if not fx_list():
                    return self.send(400, {"error": "The effects kit isn't set up on this computer yet."})
            elif body.get("template") != "shorts":
                return self.send(400, {"error": "That template is coming next. Long Video to Shorts is ready now."})
            job.state = "in line"
            threading.Thread(target=worker, args=(job, body), daemon=True).start()
            return self.send(200, {"ok": True})
        self.send(404, {"error": "not found"})


if __name__ == "__main__":
    try:      # Tiff's own copy only: this file is never copied into a member build
        import mine_routes
        mine_routes.install(H, JOBS_BY_ID, ENGINE, run_cleanup)
        # Tiff, 2026-11-03: "Yes, clean all." Long videos clean too; the working files need about 6 times the video's size
        CLEAN_MAX_SECS, CLEAN_SPACE_X = float("inf"), 6
    except ImportError:
        pass
    reload_jobs()
    port = int(os.environ.get("PORT", 8790))
    print(f"Content Made Easy is on: http://127.0.0.1:{port}   (close this window to turn it off)")
    ThreadingHTTPServer(("127.0.0.1", port), H).serve_forever()
