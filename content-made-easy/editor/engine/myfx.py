#!/usr/bin/env python3
"""Your own effects, written for the Marketing Dashboard on 2026-10-27. Nothing here comes from the
Claude Video FX Kit: original code using ffmpeg, Pillow, OpenCV and the open-source Robust Video Matting
model (GPL-3.0, github.com/PeterL1n/RobustVideoMatting), so they can ship to every member.

Each effect draws on a FINISHED 1080x1920 video (captions already on it) between --start and --end and
writes a new file. Sound is copied untouched.

usage: myfx.py <effect> <in.mp4> <out.mp4> --start S --end E --config '{"accent": "#00A6FF", ...}'
effects: zoom-punch, number-pop, checklist, headline-behind
"""
import argparse, json, os, re, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
FF = shutil.which("ffmpeg", path=os.path.expanduser("~/.local/bin")) or shutil.which("ffmpeg")
RVM = os.path.join(HERE, "models", "rvm_mobilenetv3_fp32.onnx")
RVM_URL = "https://github.com/PeterL1n/RobustVideoMatting/releases/download/v1.0.0/rvm_mobilenetv3_fp32.onnx"


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        raise SystemExit("STOP: " + (r.stderr or r.stdout)[-400:])


def esc(t):
    """Text for ffmpeg drawtext, inside single quotes."""
    return str(t).replace("\\", "\\\\").replace("'", "’").replace(":", "\\:").replace("%", "\\%")


def rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def font_for(cfg, size):
    from PIL import ImageFont
    return ImageFont.truetype(cfg["font"], size)


def zoom_punch(src, out, s, e, cfg):
    """A fast punch-in with a white flash on the strongest line. No cut-out, so it renders in seconds."""
    z = f"if(between(t,{s},{e}),1+0.2*min(1,(t-{s})/0.18),1)"
    flash = f"if(between(t,{s},{s + 0.25}),0.7*(1-(t-{s})/0.25),0)"
    w, h = dims(src)      # any size, so it can run BEFORE the captions go on and never crops them
    run([FF, "-v", "error", "-i", src, "-filter_complex",
         f"[0:v]scale=w='trunc(iw*{z}/2)*2':h='trunc(ih*{z}/2)*2':eval=frame,crop={w}:{h}:(iw-{w})/2:(ih-{h})/2,"
         f"eq=brightness='{flash}':eval=frame,setsar=1[v]",
         "-map", "[v]", "-map", "0:a?", "-c:v", "libx264", "-crf", "15", "-preset", "fast", "-pix_fmt", "yuv420p",
         "-c:a", "copy", "-y", out])


def digital_zoom(src, out, s, e, cfg):
    """Fakes a second camera: the shot steps between wide, close and closer on the moments in cfg, with a fast
    0.1 s push and no flash. Runs before the captions go on, so it never crops them."""
    levels = [1.16, 1.0, 1.28, 1.0]
    at = [float(x) for x in cfg["moments"]]
    terms, prev = [], 1.0
    for i, a in enumerate(at):
        b = at[i + 1] if i + 1 < len(at) else 99999
        lv = levels[i % len(levels)]
        # gte and lt, not between: a frame sitting exactly on a change would count twice and jump to double size
        terms.append(f"gte(t,{a})*lt(t,{b})*({prev - 1:.3f}+{lv - prev:.3f}*min(1,(t-{a})/0.1))")
        prev = lv
    z = "(1+" + "+".join(terms) + ")"
    w, h = dims(src)
    # the crop sits a little above center: a person's head is in the top half, and a center crop cuts it off
    run([FF, "-v", "error", "-i", src, "-filter_complex",
         f"[0:v]scale=w='trunc(iw*{z}/2)*2':h='trunc(ih*{z}/2)*2':eval=frame,crop={w}:{h}:(iw-{w})/2:(ih-{h})*0.38,setsar=1[v]",
         "-map", "[v]", "-map", "0:a?", "-c:v", "libx264", "-crf", "15", "-preset", "fast", "-pix_fmt", "yuv420p",
         "-c:a", "copy", "-y", out])


def _rgb(cfg):
    h = str(cfg.get("accent", "#0A5CFF")).lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _on(rgb):
    """White or near-black words, whichever reads on their brand color."""
    return (6, 21, 61) if 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2] > 170 else (255, 255, 255)


def _enc():
    return ["-c:v", "libx264", "-crf", "16", "-preset", "fast", "-pix_fmt", "yuv420p", "-c:a", "copy"]


def _fit_font(text, font, width, big, small=44):
    from PIL import ImageFont
    for size in range(big, small - 1, -4):
        f = ImageFont.truetype(font, size)
        if f.getbbox(text)[2] <= width:
            return f
    return ImageFont.truetype(font, small)


def cinema_look(src, out, s, e, cfg):
    """Movie look for the whole video: slightly warm, deeper shadows, soft dark corners, black bars."""
    w, h = dims(src)
    bar = int(h * 0.075) if h > w else int(h * 0.11)
    run([FF, "-v", "error", "-i", src, "-filter_complex",
         f"[0:v]eq=contrast=1.08:saturation=0.94,colorbalance=rm=0.03:bm=-0.03:rh=0.02:bh=-0.02,vignette=PI/5,"
         f"drawbox=x=0:y=0:w=iw:h={bar}:color=black:t=fill,drawbox=x=0:y=ih-{bar}:w=iw:h={bar}:color=black:t=fill,setsar=1[v]",
         "-map", "[v]", "-map", "0:a?", *_enc(), "-y", out])


def brand_stage(src, out, s, e, cfg):
    """They talk from a rounded card sitting on their own brand color, for the whole video."""
    from PIL import Image, ImageDraw
    w, h = dims(src)
    rgb = _rgb(cfg)
    work = tempfile.mkdtemp(prefix="stage_")
    bg = Image.new("RGB", (w, h))
    px = bg.load()
    for y in range(h):
        k = 1 - 0.42 * y / max(h - 1, 1)      # the brand color at the top, deeper at the bottom
        c = tuple(int(x * k) for x in rgb)
        for x in range(w):
            px[x, y] = c
    bg_p = os.path.join(work, "bg.png")
    bg.save(bg_p)
    cw, ch = int(w * 0.86) // 2 * 2, int(h * 0.86) // 2 * 2
    mask = Image.new("L", (cw, ch), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, cw - 1, ch - 1], radius=int(w * 0.05), fill=255)
    m_p = os.path.join(work, "mask.png")
    mask.save(m_p)
    # a looped picture runs at 25 frames a second unless told otherwise, and the picture underneath sets the
    # video's rate: without this a 30 fps clip came out 152 frames where 182 belong, 2026-11-02
    fr = subprocess.run([FF.replace("ffmpeg", "ffprobe"), "-v", "error", "-select_streams", "v", "-show_entries", "stream=r_frame_rate",
                         "-of", "csv=p=0", src], capture_output=True, text=True).stdout.strip()
    run([FF, "-v", "error", "-i", src, "-framerate", fr, "-loop", "1", "-i", bg_p, "-framerate", fr, "-loop", "1", "-i", m_p, "-filter_complex",
         f"[0:v]scale={cw}:{ch},format=rgba[c];[2:v]format=gray[m];[c][m]alphamerge[card];"
         f"[1:v][card]overlay=(W-w)/2:(H-h)/2:shortest=1,setsar=1[v]",
         # both pictures loop forever, so only -t ends this (it ran 4 minutes on a 6 s clip without it, 2026-11-02)
         "-map", "[v]", "-map", "0:a?", "-t", f"{probe_secs(src):.3f}", *_enc(), "-y", out])
    shutil.rmtree(work, ignore_errors=True)


def brand_frame(src, out, s, e, cfg):
    """A clean frame in their color around the picture, and a bar along the bottom that shows how far along it is."""
    from PIL import Image, ImageDraw
    w, h = dims(src)
    rgb = _rgb(cfg)
    work = tempfile.mkdtemp(prefix="frame_")
    t = max(10, w // 60)
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(layer).rounded_rectangle([t // 2, t // 2, w - t // 2 - 1, h - t // 2 - 1], radius=w // 22, outline=rgb + (255,), width=t)
    p = os.path.join(work, "frame.png")
    layer.save(p)
    d = probe_secs(src)
    bar_h = t * 2
    run([FF, "-v", "error", "-i", src, "-loop", "1", "-i", p, "-f", "lavfi", "-i", f"color=c=0x{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}:s={w}x{bar_h}:r=30",
         "-filter_complex", f"[0:v][2:v]overlay=x='-W+W*t/{d:.3f}':y=H-{bar_h}:shortest=1[a];[a][1:v]overlay=0:0:shortest=1,setsar=1[v]",
         "-map", "[v]", "-map", "0:a?", "-t", f"{d:.3f}", *_enc(), "-movflags", "+faststart", "-y", out])
    shutil.rmtree(work, ignore_errors=True)


def top_banner(src, out, s, e, cfg):
    """Their own opening words on a ribbon in their color, up the whole video, so a scroller knows what it's about."""
    from PIL import Image, ImageDraw
    w, h = dims(src)
    rgb = _rgb(cfg)
    text = str(cfg.get("headline") or "").strip().upper()
    work = tempfile.mkdtemp(prefix="banner_")
    pad = w // 20
    f = _fit_font(text, cfg["font"], w - 4 * pad, w // 11)
    box = f.getbbox(text)
    bw, bh = box[2] - box[0] + 2 * pad, box[3] - box[1] + int(1.2 * pad)
    img = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, bw - 1, bh - 1], radius=bh // 4, fill=rgb + (255,))
    d.text((pad - box[0], int(0.6 * pad) - box[1]), text, font=f, fill=_on(rgb) + (255,))
    p = os.path.join(work, "banner.png")
    img.save(p)
    y = int(h * 0.105)
    run([FF, "-v", "error", "-i", src, "-loop", "1", "-i", p, "-filter_complex",
         f"[0:v][1:v]overlay=x=(W-w)/2:y='{y}-{y + bh}*(1-min(1,t/0.25))^3':shortest=1,setsar=1[v]",
         "-map", "[v]", "-map", "0:a?", *_enc(), "-movflags", "+faststart", "-y", out])
    shutil.rmtree(work, ignore_errors=True)


def word_pop(src, out, s, e, cfg):
    """One of their key words pops up huge in their color, right as they say it."""
    from PIL import Image, ImageDraw, ImageFont
    w, h = dims(src)
    rgb = _rgb(cfg)
    work = tempfile.mkdtemp(prefix="pop_")
    ins, filt, last = ["-i", src], [], "0:v"
    words = cfg["words"][:24]      # each word is its own overlay, and a long chain gets slow
    for k, it in enumerate(words):
        text = str(it["w"]).upper()
        f = _fit_font(text, cfg["font"], int(w * 0.86), w // 6)
        stroke = max(4, f.size // 12)
        box = f.getbbox(text, stroke_width=stroke)
        img = Image.new("RGBA", (box[2] - box[0] + 8, box[3] - box[1] + 8), (0, 0, 0, 0))
        ImageDraw.Draw(img).text((4 - box[0], 4 - box[1]), text, font=f, fill=rgb + (255,), stroke_width=stroke, stroke_fill=(255, 255, 255, 255))
        p = os.path.join(work, f"w{k}.png")
        img.save(p)
        ins += ["-loop", "1", "-i", p]
        a, b = float(it["t"]), float(it["t"]) + 0.85
        nxt = f"w{k}"
        filt.append(f"[{last}][{k + 1}:v]overlay=x=(W-w)/2:y='H*0.2+70*max(0,1-(t-{a})/0.12)':shortest=1:enable='between(t,{a},{b})'[{nxt}]")
        last = nxt
    run([FF, "-v", "error", *ins, "-filter_complex", ";".join(filt), "-map", f"[{last}]", "-map", "0:a?",
         "-t", str(probe_secs(src)), *_enc(), "-movflags", "+faststart", "-y", out])
    shutil.rmtree(work, ignore_errors=True)


def split_stage(src, out, s, e, cfg):
    """Screen in two: their own words big on a soft card in their color up top, them talking below. Captions land on the seam."""
    from PIL import Image, ImageDraw
    w, h = dims(src)
    if w >= h:
        raise RuntimeError("Split Stage needs a tall video. Film it on your phone standing up.")
    rgb = _rgb(cfg)
    tint = tuple(int(255 - (255 - x) * 0.14) for x in rgb)
    ink = tuple(int(x * 0.55) for x in rgb)
    top_h = h // 2 // 2 * 2
    fr = subprocess.run([FF.replace("ffmpeg", "ffprobe"), "-v", "error", "-select_streams", "v", "-show_entries", "stream=r_frame_rate",
                         "-of", "csv=p=0", src], capture_output=True, text=True).stdout.strip()
    d = probe_secs(src)
    work = tempfile.mkdtemp(prefix="split_")
    ins, filt, last = ["-i", src, "-f", "lavfi", "-i", f"color=c=0x{tint[0]:02x}{tint[1]:02x}{tint[2]:02x}:s={w}x{top_h}:r={fr}"], [], "1:v"
    lines = cfg["lines"][:24]
    for k, it in enumerate(lines):
        rows, cur = [], ""
        for word in str(it["text"]).split():
            if cur and len(cur) + len(word) > 14:
                rows.append(cur); cur = word
            else:
                cur = (cur + " " + word).strip()
        rows.append(cur)
        f = _fit_font(max(rows, key=len), cfg["font"], int(w * 0.84), w // 7)
        img = Image.new("RGBA", (w, top_h), (0, 0, 0, 0))
        d2 = ImageDraw.Draw(img)
        lh = int(f.size * 1.18)
        y = (top_h - lh * len(rows)) // 2
        for r in rows:
            b = f.getbbox(r)
            d2.text(((w - b[2] + b[0]) // 2 - b[0], y), r, font=f, fill=ink + (255,))
            y += lh
        p = os.path.join(work, f"l{k}.png")
        img.save(p)
        ins += ["-loop", "1", "-framerate", fr, "-i", p]
        a, b = float(it["t0"]), float(it["t1"])
        nxt = f"l{k}"
        filt.append(f"[{last}][{k + 2}:v]overlay=0:0:shortest=1:enable='gte(t,{a})*lt(t,{b})'[{nxt}]")
        last = nxt
    # the crop starts a little down from the top, where a person's head usually sits on a phone video
    filt.append(f"[0:v]crop={w}:{h - top_h}:0:{(h - (h - top_h)) // 5},setsar=1[me]")
    filt.append(f"[{last}]setsar=1[up];[up][me]vstack=2[v]")
    run([FF, "-v", "error", *ins, "-filter_complex", ";".join(filt), "-map", "[v]", "-map", "0:a?", "-t", f"{d:.3f}", *_enc(), "-y", out])
    shutil.rmtree(work, ignore_errors=True)


def note_card(src, out, s, e, cfg):
    """A card in their color up top that fills in line by line with their own words, then starts fresh."""
    from PIL import Image, ImageDraw
    w, h = dims(src)
    rgb = _rgb(cfg)
    work = tempfile.mkdtemp(prefix="note_")
    ins, filt, last = ["-i", src], [], "0:v"
    lines = cfg["lines"][:24]
    pad = w // 22
    cw = int(w * 0.86)
    f = _fit_font("M" * 18, cfg["font"], cw - 2 * pad, w // 17)
    lh = int(f.size * 1.5)
    for k, it in enumerate(lines):
        n = k % 3
        rows = [str(x["text"]) if len(str(x["text"])) <= 24 else str(x["text"])[:25].rsplit(" ", 1)[0] for x in lines[k - n:k + 1]]
        ch = 2 * pad + lh * len(rows)
        img = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([0, 0, cw - 1, ch - 1], radius=w // 28, fill=rgb + (242,))
        for i, r in enumerate(rows):
            d.text((pad, pad + i * lh), r, font=f, fill=_on(rgb) + (255 if i == len(rows) - 1 else 170,))
        p = os.path.join(work, f"n{k}.png")
        img.save(p)
        ins += ["-loop", "1", "-i", p]
        a, b = float(it["t0"]), float(it["t1"])
        nxt = f"n{k}"
        filt.append(f"[{last}][{k + 1}:v]overlay=x=(W-w)/2:y=H*0.09:shortest=1:enable='gte(t,{a})*lt(t,{b})'[{nxt}]")
        last = nxt
    run([FF, "-v", "error", *ins, "-filter_complex", ";".join(filt), "-map", f"[{last}]", "-map", "0:a?",
         "-t", str(probe_secs(src)), *_enc(), "-movflags", "+faststart", "-y", out])
    shutil.rmtree(work, ignore_errors=True)


def glow_words(src, out, s, e, cfg):
    """A key word fades up above their head with a soft glow in their color, in their own font."""
    from PIL import Image, ImageDraw, ImageFilter
    w, h = dims(src)
    rgb = _rgb(cfg)
    work = tempfile.mkdtemp(prefix="glow_")
    ins, filt, last = ["-i", src], [], "0:v"
    for k, it in enumerate(cfg["words"][:24]):
        text = str(it["w"]).lower()
        f = _fit_font(text, cfg["font"], int(w * 0.8), w // 7)
        box = f.getbbox(text)
        m = w // 14
        size = (box[2] - box[0] + 2 * m, box[3] - box[1] + 2 * m)
        mask = Image.new("L", size, 0)
        ImageDraw.Draw(mask).text((m - box[0], m - box[1]), text, font=f, fill=255)
        glow = Image.new("RGBA", size, rgb + (0,))
        glow.putalpha(mask.filter(ImageFilter.GaussianBlur(w // 48)))
        ImageDraw.Draw(glow).text((m - box[0], m - box[1]), text, font=f, fill=(255, 255, 255, 255))
        p = os.path.join(work, f"g{k}.png")
        glow.save(p)
        ins += ["-loop", "1", "-i", p]
        a, b = float(it["t"]), float(it["t"]) + 1.1
        nxt = f"g{k}"
        filt.append(f"[{k + 1}:v]format=rgba,fade=t=in:st={a}:d=0.15:alpha=1[f{k}];[{last}][f{k}]overlay=x=(W-w)/2:y=H*0.12:shortest=1:enable='between(t,{a},{b})'[{nxt}]")
        last = nxt
    run([FF, "-v", "error", *ins, "-filter_complex", ";".join(filt), "-map", f"[{last}]", "-map", "0:a?",
         "-t", str(probe_secs(src)), *_enc(), "-movflags", "+faststart", "-y", out])
    shutil.rmtree(work, ignore_errors=True)


def _wobble(pts, seed, amt):
    import random
    r = random.Random(seed)
    return [(x + r.uniform(-amt, amt), y + r.uniform(-amt, amt)) for x, y in pts]


def _doodle_shape(kind, x, y, w, h):
    """A hand-drawn shape as a list of strokes, each stroke a list of points. Every shape is plain geometry drawn here."""
    import math
    if kind == "circle":
        return [[(x + w / 2 + (w / 2 + 26) * math.cos(a / 40 * 2.15 * math.pi - 2), y + h / 2 + (h / 2 + 22) * math.sin(a / 40 * 2.15 * math.pi - 2)) for a in range(41)]]
    if kind == "underline":
        return [[(x + w * i / 16, y + h + 16 + 7 * math.sin(i * 1.1)) for i in range(17)], [(x + w * (16 - i) / 16, y + h + 36 + 5 * math.sin(i)) for i in range(17)]]
    if kind == "arrow":      # from under the word, curving toward the middle of the screen
        side = 1 if x < 540 else -1
        sx, sy = x + w / 2, y + h + 22
        ex, ey = sx + side * 170, sy + 170
        body = [(sx + (ex - sx) * t / 16 - side * 40 * math.sin(t / 16 * math.pi), sy + (ey - sy) * t / 16) for t in range(17)]
        return [body, [(ex - side * 58, ey - 16), (ex, ey), (ex - side * 6, ey - 58)]]
    if kind == "stars":
        out = []
        for cx, cy, r in ((x - 44, y + 4, 26), (x + w + 44, y + h * 0.3, 34), (x + w * 0.5, y + h + 44, 22)):
            out += [[(cx - r, cy), (cx + r, cy)], [(cx, cy - r), (cx, cy + r)], [(cx - r * 0.65, cy - r * 0.65), (cx + r * 0.65, cy + r * 0.65)], [(cx - r * 0.65, cy + r * 0.65), (cx + r * 0.65, cy - r * 0.65)]]
        return out
    return [[(x + w * 0.1, y + h + 30), (x + w * 0.3, y + h + 64), (x + w * 0.85, y + h - 4)]]      # check


def doodles(src, out, s, e, cfg):
    """Hand-drawn notes: a key word in handwriting with a circle, arrow, underline, stars or check that draws itself on,
    then wiggles the way a flipbook does. All in their color, always up above the face."""
    from PIL import Image, ImageDraw, ImageFont
    import numpy as np
    rgb = _rgb(cfg)
    kinds = ["circle", "arrow", "underline", "stars", "check"]
    notes = []
    for k, it in enumerate(cfg["words"]):
        f = ImageFont.truetype(cfg["hand"], 92)
        text = str(it["w"]).lower()
        while f.size > 44 and f.getbbox(text)[2] > 620:
            f = ImageFont.truetype(cfg["hand"], f.size - 6)
        b = f.getbbox(text)
        tw_, th = b[2] - b[0], b[3] - b[1]
        x = 90 + 40 * (k % 3) if k % 2 == 0 else 1080 - 90 - tw_ - 40 * (k % 3)
        y = 240 + 60 * (k % 3)
        notes.append({"t": float(it["t"]), "text": text, "f": f, "pos": (x - b[0], y - b[1]), "box": (x, y, tw_, th), "kind": kinds[k % 5], "seed": k})
    memo = {}

    def layer(n, step, seed):
        key = (n["seed"], step, seed)
        if key in memo:
            return memo[key]
        if len(memo) > 12:      # only the note on screen is ever needed again
            memo.clear()
        img = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        strokes = _doodle_shape(n["kind"], *n["box"])
        total = sum(len(x) for x in strokes)
        left = int(total * step)
        for width, color in ((22, (255, 255, 255, 255)), (11, rgb + (255,))):      # white edge, so it reads on any background
            budget = left
            for i, st in enumerate(strokes):
                if budget <= 1:
                    break
                d.line(_wobble(st[:budget], n["seed"] * 100 + i + seed, 3.2), fill=color, width=width, joint="curve")
                budget -= len(st)
        ox, oy = n["pos"]
        wig = [(0, 0), (2, -2), (-2, 1)][seed % 3]
        d.text((ox + wig[0], oy + wig[1]), n["text"], font=n["f"], fill=rgb + (255,), stroke_width=8, stroke_fill=(255, 255, 255, 255))
        a = np.asarray(img, dtype=np.float32) / 255.0
        memo[key] = (a[..., :3][..., ::-1].copy(), a[..., 3:4].copy())      # the frames here are blue, green, red
        return memo[key]

    def draw(k, t, fr, a):
        for n in notes:
            dt = t - n["t"]
            if 0 <= dt < 1.5:
                lay, al = layer(n, min(1.0, dt / 0.3), int(t * 8) % 3)      # 8 changes a second: the flipbook wiggle
                fade = min(1.0, (1.5 - dt) / 0.15)
                return fr * (1 - al * fade) + lay * al * fade
        return fr
    per_frame(src, out, 0.0, probe_secs(src), draw)


def orbit(src, out, s, e, cfg):
    """Their key words circle around their head like a ring: behind them on the far side, in front on the near side."""
    from PIL import Image, ImageDraw, ImageFont
    import math, cv2, numpy as np
    rgb = _rgb(cfg)
    f = ImageFont.truetype(cfg["font"], 76)
    sprites = []
    for word in cfg["orbit_words"][:6]:
        text = str(word).upper()
        b = f.getbbox(text, stroke_width=6)
        img = Image.new("RGBA", (b[2] - b[0] + 8, b[3] - b[1] + 8), (0, 0, 0, 0))
        ImageDraw.Draw(img).text((4 - b[0], 4 - b[1]), text, font=f, fill=rgb + (255,), stroke_width=6, stroke_fill=(255, 255, 255, 255))
        a = np.asarray(img, dtype=np.float32) / 255.0
        sprites.append((a[..., [2, 1, 0]], a[..., 3:4]))
    cx, cy, ra, rb = 540, int(1920 * float(cfg.get("face_y", 0.3))), 350, 95      # narrow enough that a long word stays on screen

    def put(canvas, spr, al, x, y, sc, op):
        w, h = max(2, int(spr.shape[1] * sc)), max(2, int(spr.shape[0] * sc))
        sp, a = cv2.resize(spr, (w, h)), cv2.resize(al, (w, h))[..., None] * op
        x0, y0 = int(x - w / 2), int(y - h / 2)
        xa, ya, xb, yb = max(0, x0), max(0, y0), min(1080, x0 + w), min(1920, y0 + h)
        if xa >= xb or ya >= yb:
            return
        sp, a = sp[ya - y0:yb - y0, xa - x0:xb - x0], a[ya - y0:yb - y0, xa - x0:xb - x0]
        canvas[ya:yb, xa:xb] = canvas[ya:yb, xa:xb] * (1 - a) + sp * a

    def draw(k, t, fr, a):
        op = ease(t / 0.3) * ease((e - s - t) / 0.3)
        items = []
        for i, (spr, al) in enumerate(sprites):
            ang = t * 1.5 + i * 2 * math.pi / len(sprites)
            items.append((math.sin(ang), math.cos(ang), spr, al))
        canvas = fr.copy()
        for d, c, spr, al in sorted(items, key=lambda x: x[0]):      # far side first
            if d < 0:
                put(canvas, spr, al, cx + ra * c, cy + rb * d, 0.68 + 0.14 * (d + 1), op * 0.85)
        canvas = canvas * (1 - a) + fr * a      # the person goes over the far side of the ring
        for d, c, spr, al in sorted(items, key=lambda x: x[0]):
            if d >= 0:
                put(canvas, spr, al, cx + ra * c, cy + rb * d, 0.82 + 0.34 * d, op)
        return canvas
    per_frame(src, out, s, e, draw, matte=True)


def pop_out(src, out, s, e, cfg):
    """They shrink into a phone on their brand color, then their head and hands break out over the edges of it."""
    from PIL import ImageDraw
    import cv2, numpy as np
    W, H = 1080, 1920
    pw, ph = 690, 1230
    px, py = (W - pw) // 2, 430
    rgb = _rgb(cfg)
    bg = np.zeros((H, W, 3), np.float32)
    for y in range(H):
        k = 1 - 0.45 * y / H
        bg[y] = [rgb[2] / 255 * k, rgb[1] / 255 * k, rgb[0] / 255 * k]
    m = rgba_layer()
    ImageDraw.Draw(m).rounded_rectangle([px, py, px + pw, py + ph], radius=70, fill=(255, 255, 255, 255))
    screen = np.asarray(m)[..., 3:4].astype(np.float32) / 255.0
    bez = rgba_layer()
    ImageDraw.Draw(bez).rounded_rectangle([px - 16, py - 16, px + pw + 16, py + ph + 16], radius=84, outline=(6, 21, 61, 255), width=18)
    sc = 0.9      # much bigger than the phone, so the head and arms really do break out over its edges

    def draw(k, t, fr, a):
        p = ease(t / 0.4)
        z = 1 + (sc - 1) * p
        w, h = int(W * z), int(H * z)
        small, sa = cv2.resize(fr, (w, h)), cv2.resize(a, (w, h))[..., None]
        x, y = (W - w) // 2, int((H - h) / 2 * (1 - p))
        full, alpha = bg.copy(), np.zeros((H, W, 1), np.float32)
        xa, ya, xb, yb = max(0, x), max(0, y), min(W, x + w), min(H, y + h)
        full[ya:yb, xa:xb] = small[ya - y:yb - y, xa - x:xb - x]
        alpha[ya:yb, xa:xb] = sa[ya - y:yb - y, xa - x:xb - x]
        canvas = bg * (1 - screen) + full * screen
        canvas = paste(canvas, bez)
        return canvas * (1 - alpha) + full * alpha      # the person stays on top of the phone's edges
    per_frame(src, out, s, e, draw, matte=True)


def glass_meter(src, out, s, e, cfg):
    """A small dark glass card under the words: their key word on the left, a bar in their color that fills as they talk."""
    from PIL import Image, ImageDraw, ImageFont
    import numpy as np
    rgb = _rgb(cfg)
    W, H = 1080, 1920
    cw, ch = 640, 150
    cx, cy = (W - cw) // 2, int(H * 0.67)
    f = ImageFont.truetype(cfg["font"], 40)
    moments = [(float(x["t"]), str(x["w"]).lower()[:18]) for x in cfg["words"]] or [(0.0, "")]
    if moments[0][0] > 0:
        moments.insert(0, (0.0, moments[0][1]))
    ends = [m[0] for m in moments[1:]] + [probe_secs(src)]
    base = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    d = ImageDraw.Draw(base)
    d.rounded_rectangle([0, 0, cw - 1, ch - 1], radius=30, fill=(14, 16, 26, 225), outline=(255, 255, 255, 40), width=2)
    d.rounded_rectangle([34, 96, cw - 34, 110], radius=7, fill=(255, 255, 255, 46))
    memo = {}

    def card(i):
        if i not in memo:
            memo.clear()
            img = base.copy()
            ImageDraw.Draw(img).text((34, 28), moments[i][1], font=f, fill=(255, 255, 255, 255))
            a = np.asarray(img, dtype=np.float32) / 255.0
            memo[i] = (a[..., [2, 1, 0]].copy(), a[..., 3:4].copy())
        return memo[i]
    bar = np.array([rgb[2], rgb[1], rgb[0]], np.float32) / 255.0

    def draw(k, t, fr, a):
        i = max(0, min(len(moments) - 1, sum(1 for m in moments if m[0] <= t) - 1))
        lay, al = card(i)
        out_ = fr.copy()
        reg = out_[cy:cy + ch, cx:cx + cw]
        reg[:] = reg * (1 - al) + lay * al
        p = ease((t - moments[i][0]) / max(0.4, ends[i] - moments[i][0]))
        x = 34 + int((cw - 68) * p)
        reg[97:110, 34:max(35, x)] = bar
        ky, kx = np.ogrid[-13:14, -13:14]
        dot = (kx * kx + ky * ky <= 169)
        yy, xx = 103, min(cw - 15, max(15, x))
        reg[yy - 13:yy + 14, xx - 13:xx + 14][dot] = 1.0
        return out_
    per_frame(src, out, 0.0, probe_secs(src), draw)


def _zoom_expr(at, levels=(1.16, 1.0, 1.28, 1.0), push=0.1):
    terms, prev = [], 1.0
    for i, a in enumerate(at):
        b = at[i + 1] if i + 1 < len(at) else 99999
        lv = levels[i % len(levels)]
        terms.append(f"gte(t,{a:.3f})*lt(t,{b:.3f})*({prev - 1:.3f}+{lv - prev:.3f}*min(1,(t-{a:.3f})/{push}))")
        prev = lv
    return "(1+" + "+".join(terms) + ")" if terms else "1"


def _moments(cfg, every=1, most=14):
    return [float(x) for x in (cfg.get("moments") or [])][::every][:most]


def _during(at, before, after):
    return "+".join(f"between(t,{a - before:.3f},{a + after:.3f})" for a in at) or "0"


def _fx(src, out, graph):
    run([FF, "-v", "error", "-i", src, "-filter_complex", graph, "-map", "[v]", "-map", "0:a?", *_enc(), "-y", out])


def lights_on(src, out, s, e, cfg):
    """The room starts dark, the lights flicker on and the picture comes all the way up."""
    up = "pow(min(1,max(0,(t-0.2)/1.5)),1.6)"
    flick = "(between(t,0.28,0.36)+between(t,0.5,0.56))*0.55"
    lit = f"min(1,{up}+{flick})"
    glow = "0.05*between(t,1.7,2.3)*(1-abs(t-2)/0.3)"
    _fx(src, out, f"[0:v]eq=gamma='0.2+0.8*{lit}':brightness='-0.42*(1-{lit})+{glow}':saturation='0.45+0.55*{lit}':eval=frame,setsar=1[v]")


def screen_wipe(src, out, s, e, cfg):
    """The screen starts fogged over and a hand-sized swipe wipes it clear, back and forth from the top down."""
    from PIL import Image, ImageDraw, ImageFilter
    w, h = dims(src)
    mw, mh, fps, frames = 270, 480, 30, 66
    path = []
    rows = 6
    for r in range(rows):
        y = mh * (r + 0.6) / rows
        path += [(-30, y), (mw + 30, y + 24)] if r % 2 == 0 else [(mw + 30, y), (-30, y + 24)]
    steps = []
    for (x0, y0), (x1, y1) in zip(path, path[1:]):
        steps += [(x0 + (x1 - x0) * k / 16, y0 + (y1 - y0) * k / 16) for k in range(16)]
    work = tempfile.mkdtemp(prefix="wipe_")
    raw = os.path.join(work, "mask.raw")
    start, end = 10, 56
    fog = Image.new("L", (mw, mh), 255)
    d = ImageDraw.Draw(fog)
    done = 0
    with open(raw, "wb") as fh:
        for f in range(frames):
            want = int(len(steps) * min(1, max(0, (f - start) / (end - start))))
            for x, y in steps[done:want]:
                d.ellipse((x - 46, y - 46, x + 46, y + 46), fill=0)
            done = want
            look = fog.filter(ImageFilter.GaussianBlur(5))
            if f >= end:
                look = look.point(lambda v: int(v * max(0, 1 - (f - end) / 8)))
            fh.write(look.tobytes())
    run([FF, "-v", "error", "-i", src, "-f", "rawvideo", "-pix_fmt", "gray", "-s", f"{mw}x{mh}", "-r", str(fps), "-i", raw, "-filter_complex",
         f"[0:v]split[a][b];[b]boxblur=26:2,eq=brightness=0.16:saturation=0.55,format=yuva420p[fog];"
         f"[1:v]scale={w}:{h},tpad=stop_mode=clone:stop_duration=99999,format=gray[m];[fog][m]alphamerge[f];[a][f]overlay=shortest=1,setsar=1[v]",
         "-map", "[v]", "-map", "0:a?", *_enc(), "-y", out])


def shutter_strike(src, out, s, e, cfg):
    """A camera shutter snaps shut and open on your key moments, with a white flash and a new framing each time."""
    w, h = dims(src)
    at = _moments(cfg, 2, 10)
    z = _zoom_expr(at, push=0.01)
    p = "+".join(f"max(0,1-abs(t-{a:.3f})/0.1)" for a in at) or "0"
    half = h // 2 + 2
    _fx(src, out, f"[0:v]scale=w='trunc(iw*{z}/2)*2':h='trunc(ih*{z}/2)*2':eval=frame,crop={w}:{h}:(iw-{w})/2:(ih-{h})*0.38,"
                  f"eq=brightness='0.7*({_during(at, 0, 0.04)})':eval=frame[a];"
                  f"color=black:s={w}x{half}:r=30[t];color=black:s={w}x{half}:r=30[b];"
                  f"[a][t]overlay=0:'-{half}+{half}*min(1,({p})*1.3)':eval=frame:shortest=1[x];"
                  f"[x][b]overlay=0:'{h}-{half}*min(1,({p})*1.3)':eval=frame:shortest=1,setsar=1[v]")


def zoom_through(src, out, s, e, cfg):
    """The camera rushes through you into the next shot, with motion blur on the rush."""
    w, h = dims(src)
    at = _moments(cfg, 2, 10)
    rush = "+".join(f"between(t,{a - 0.2:.3f},{a:.3f})*0.95*pow((t-{a - 0.2:.3f})/0.2,2)" for a in at) or "0"
    z = f"({_zoom_expr(at, push=0.01)}+{rush})"
    _fx(src, out, f"[0:v]scale=w='trunc(iw*{z}/2)*2':h='trunc(ih*{z}/2)*2':eval=frame,crop={w}:{h}:(iw-{w})/2:(ih-{h})*0.38,setsar=1,split[a][b];"
                  f"[b]tmix=frames=3:weights='1 1 1',avgblur=sizeX=10:sizeY=10[m];[a][m]overlay=enable='{_during(at, 0.2, 0.04)}'[v]")


def pull_back(src, out, s, e, cfg):
    """Opens tight on your face, then the camera pulls back and keeps drifting slowly toward you."""
    w, h = dims(src)
    z = "(1+0.95*pow(max(0,1-t/1.1),3)+0.05*min(1,t/20))"
    _fx(src, out, f"[0:v]scale=w='trunc(iw*{z}/2)*2':h='trunc(ih*{z}/2)*2':eval=frame,crop={w}:{h}:(iw-{w})/2:(ih-{h})*0.34,setsar=1[v]")


def whip_cut(src, out, s, e, cfg):
    """The shot whips sideways and lands back on you at your key moments, like a fast camera pan."""
    w, h = dims(src)
    at = _moments(cfg, 2, 10)
    x = "+".join(f"{w}*pow(min(1,max(0,(t-{a - 0.11:.3f})/0.22)),2)" for a in at) or "0"
    _fx(src, out, f"[0:v]split[l][r];[l][r]hstack,crop={w}:{h}:x='mod({x},{w})':y=0,setsar=1,split[a][b];"
                  f"[b]avgblur=sizeX=70:sizeY=1[m];[a][m]overlay=enable='{_during(at, 0.12, 0.13)}'[v]")


def flash_cut(src, out, s, e, cfg):
    """A bright flash and a punch of contrast land on each key moment, with a new framing."""
    w, h = dims(src)
    at = _moments(cfg, 1, 14)
    z = _zoom_expr(at, push=0.01)
    f = "+".join(f"max(0,1-abs(t-{a:.3f})/0.12)" for a in at) or "0"
    _fx(src, out, f"[0:v]scale=w='trunc(iw*{z}/2)*2':h='trunc(ih*{z}/2)*2':eval=frame,crop={w}:{h}:(iw-{w})/2:(ih-{h})*0.38,"
                  f"eq=brightness='0.55*({f})':contrast='1+0.25*({f})':eval=frame,setsar=1[v]")


def black_white_beats(src, out, s, e, cfg):
    """The picture snaps between black and white and full color on your key moments."""
    at = _moments(cfg, 1, 14)
    on = "+".join(f"between(t,{a:.3f},{at[i + 1] if i + 1 < len(at) else 99999:.3f})" for i, a in enumerate(at) if i % 2 == 0) or "0"
    _fx(src, out, f"[0:v]eq=saturation='1-min(1,{on})':contrast='1+0.12*min(1,{on})':eval=frame,setsar=1[v]")


def _font(path, size):
    from PIL import ImageFont
    return ImageFont.truetype(path, size)


def _fit(path, text, width, big, small=30):
    for size in range(big, small - 1, -4):
        f = _font(path, size)
        if f.getbbox(text)[2] <= width:
            return f
    return _font(path, small)


def _bright(rgb):
    """Their color, lifted if it would disappear on a dark panel."""
    if 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2] >= 110:
        return rgb
    return tuple(min(255, int(c + (255 - c) * 0.45)) for c in rgb)


def _serif(cfg):
    p = os.path.join(os.path.dirname(cfg["font"]), "DMSerifDisplay.ttf")
    return p if os.path.exists(p) else cfg["font"]


def _plain(cfg):
    p = os.path.join(os.path.dirname(cfg["font"]), "Montserrat-SemiBold.ttf")
    return p if os.path.exists(p) else cfg["font"]


def _head(src, s, e):
    """Where the head sits in this video, (top, chin) on the 1920 tall frame, read from the video itself. Every video is filmed differently."""
    import cv2, glob
    import numpy as np
    found = glob.glob(os.path.expanduser("~/vibe-editing/**/yunet.onnx"), recursive=True)
    tops, chins = [], []
    if found:
        cap = cv2.VideoCapture(src)
        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        det = cv2.FaceDetectorYN.create(found[0], "", (540, 960), 0.6)
        for i in range(14):
            cap.set(cv2.CAP_PROP_POS_FRAMES, int((s + (float(e) - s) * (i + 0.5) / 14) * fps))
            ok, fr = cap.read()
            if not ok:
                continue
            _, fc = det.detect(cv2.resize(fr, (540, 960)))
            if fc is not None and len(fc):
                b = max(fc, key=lambda x: x[3])
                tops.append((b[1] - 0.35 * b[3]) * 2)
                chins.append((b[1] + 1.08 * b[3]) * 2)
        cap.release()
    if not tops:
        return 330, 900      # nobody found: a talking head usually sits about here
    return max(0, int(np.percentile(tops, 25))), min(1920, int(np.percentile(chins, 75)))


def _aim(head, y0, y1):
    """Moves the picture, and shrinks it if it has to, so the whole head sits between y0 and y1. The card then covers the clothes, not the face."""
    import cv2
    top, chin = head
    tall = max(1, chin - top)
    sc = min(1.0, (y1 - y0) / (tall * 1.12))
    off = int(y0 + max(0, (y1 - y0 - tall * sc) * 0.4) - top * sc)
    w, h = int(1080 * sc), int(1920 * sc)

    def move(fr):
        back = cv2.resize(cv2.GaussianBlur(cv2.resize(fr, (108, 192)), (0, 0), 6), (1080, 1920))
        small = fr if sc == 1.0 else cv2.resize(fr, (w, h), interpolation=cv2.INTER_AREA)
        x = (1080 - w) // 2
        a, b = max(0, off), min(1920, off + h)
        back[a:b, x:x + w] = small[a - off:b - off]
        return back
    return move


def _small_you(fr, a, size):
    """You, cut out and smaller, standing on the bottom of the screen. The sides fade so no hard edge shows where your arm left the shot."""
    import cv2
    import numpy as np
    w, h = int(1080 * size), int(1920 * size)
    x, y = (1080 - w) // 2, 1920 - h
    you = cv2.resize(fr, (w, h), interpolation=cv2.INTER_AREA)
    al = cv2.resize(a, (w, h), interpolation=cv2.INTER_AREA)
    al = al.reshape(h, w, 1).copy()
    fade = np.clip(np.minimum(np.arange(w), np.arange(w)[::-1]) / 50, 0, 1).reshape(1, w, 1)
    al *= fade
    return you, al, x, y


def _caption_rows(cfg, most=4):
    rows = _sentences(cfg, most)

    def row_at(t):
        for i, r in enumerate(rows):
            end = rows[i + 1][0]["t"] if i + 1 < len(rows) else r[-1]["e"] + 0.5
            if r[0]["t"] - 0.05 <= t < end:
                return i
        return None
    return rows, row_at


def _caption(d, cfg, rows, i, y, size=70):
    """The words you're saying, drawn right into the design, so they never sit on your face."""
    if i is None:
        return
    line = " ".join(w["w"].strip() for w in rows[i])
    f = _fit(_plain(cfg), line, 980, size, 36)
    box = f.getbbox(line)
    d.text(((1080 - box[2] + box[0]) // 2 - box[0], y - box[1]), line, font=f, fill=(255, 255, 255, 255), stroke_width=4, stroke_fill=(0, 0, 0, 220))


def _graphic(src, out, s, e, state, paint, behind=False, shift=0, gray=False, glass=None, move=None):
    """Draws a designed layer over each frame. state(t) names what's on screen, so a layer is only drawn when it changes."""
    import numpy as np
    from PIL import Image
    cache = {}

    def draw(k, t, fr, a):
        if move:
            fr = move(fr)
        if shift:
            fr = np.concatenate([np.zeros((shift, 1080, 3), np.float32), fr[:1920 - shift]], axis=0)
        if gray is True or (callable(gray) and gray(t)):
            fr = np.repeat(fr.mean(axis=2, keepdims=True), 3, axis=2)
        key = state(t)
        if glass and key is not None:
            import cv2
            for x0, y0, x1, y1 in glass(key):
                fr = fr.copy()
                fr[y0:y1, x0:x1] = cv2.GaussianBlur(fr[y0:y1, x0:x1], (0, 0), 28) * 0.72 + 0.28 * 0.16
        if key is None:
            return fr
        if key not in cache:
            if len(cache) > 40:
                cache.clear()
            img = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
            paint(img, key)
            arr = np.asarray(img, dtype=np.float32) / 255
            cache[key] = (arr[..., 2::-1].copy(), arr[..., 3:4].copy())
        rgb, al = cache[key]
        if behind and a is not None:
            al = al * (1 - a)
        return fr * (1 - al) + rgb * al
    per_frame(src, out, s, e, draw, matte=behind)


def _items(cfg, most):
    """Their typed words if they typed any, otherwise the key words they said, each landing when it's said."""
    keys = [{"w": str(x["w"]), "t": float(x["t"])} for x in (cfg.get("keys") or [])][:most]
    typed = [str(x) for x in (cfg.get("typed") or [])][:most]
    if not typed:
        return keys
    last = keys[-1]["t"] if keys else 0.5
    return [{"w": w, "t": keys[i]["t"] if i < len(keys) else last + 1.5 * (i - len(keys) + 1)} for i, w in enumerate(typed)]


def _title(cfg, fallback="The list"):
    return str(cfg.get("title") or fallback)[:30]


def _tag(d, text, font, rgb, y):
    from PIL import ImageDraw
    box = font.getbbox(text)
    w = box[2] - box[0] + 44
    x = (1080 - w) // 2
    d.rounded_rectangle((x, y, x + w, y + box[3] - box[1] + 34), 14, fill=rgb + (255,))
    d.text((x + 22 - box[0], y + 17 - box[1]), text, font=font, fill=_on(rgb) + (255,))


def _sentences(cfg, most=7):
    rows, cur = [], []
    for w in cfg.get("said") or []:
        cur.append(w)
        if len(cur) >= most or w["w"].rstrip()[-1:] in ".!?,":
            rows.append(cur)
            cur = []
    if cur:
        rows.append(cur)
    return rows


def big_type(src, out, s, e, cfg):
    """Your opening line goes huge behind your head, stacked, with the last line in your color. Every line fits inside the frame."""
    from PIL import ImageDraw
    rgb = _bright(_rgb(cfg))
    said = cfg.get("said") or []
    first = said[:8]
    for i, w in enumerate(first):
        if w["w"].rstrip()[-1:] in ".!?":     # stop on the end of their sentence, not halfway through it
            first = first[:i + 1]
            break
    typed = cfg.get("typed") or []
    words = (" ".join(typed).upper().split() if typed else [w["w"].strip(" ,.!?").upper() for w in first]) or ["WATCH", "THIS"]
    lines, cur = [], ""
    for w in words:
        if cur and (len(cur.split()) >= 2 or len(cur) + len(w) > 13):
            lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    lines = (lines + [cur])[:4]
    end = min(float(e), (first[-1]["e"] if first else 3.0) + 0.8)
    room = max(420, _head(src, 0.0, end)[0] + 140) - 70       # from the top of the frame to just behind the forehead
    big = 280
    while big > 60:
        fonts = [_fit(cfg["font"], x, 1000, big, 40) for x in lines]
        tall = sum(f.getbbox(x)[3] - f.getbbox(x)[1] + 22 for f, x in zip(fonts, lines))
        if tall <= room:
            break
        big -= 10

    def state(t):
        return min(8, int(t / 0.04)) if t < end else None

    def paint(img, k):
        d = ImageDraw.Draw(img)
        y = 70 + (8 - k) * 8
        for i, line in enumerate(lines):
            f = fonts[i]
            fill = rgb if i == len(lines) - 1 else (255, 255, 255)
            box = f.getbbox(line)
            d.text(((1080 - box[2] + box[0]) // 2 - box[0], y - box[1]), line, font=f, fill=fill + (int(255 * min(1, k / 4)),), stroke_width=3, stroke_fill=(0, 0, 0, int(120 * min(1, k / 4))))
            y += box[3] - box[1] + 22
    _graphic(src, out, 0.0, end, state, paint, behind=True)


def glow_stack(src, out, s, e, cfg):
    """Every sentence becomes a stacked design under your chin: small words, then one huge glowing word in your color."""
    from PIL import Image, ImageDraw, ImageFilter
    rgb = _rgb(cfg)
    rows = _sentences(cfg, 7)
    big = [max(range(len(r)), key=lambda i: len(r[i]["w"].strip(" ,.!?"))) for r in rows]

    def state(t):
        for i, r in enumerate(rows):
            end = rows[i + 1][0]["t"] if i + 1 < len(rows) else r[-1]["e"] + 0.5
            if r[0]["t"] - 0.05 <= t < end:
                return (i, sum(1 for w in r if w["t"] <= t))
        return None

    def paint(img, key):
        i, n = key
        r, b = rows[i], big[i]
        d = ImageDraw.Draw(img)
        small = _font(_plain(cfg), 46)
        top = " ".join(w["w"].strip() for w in r[:b][:n])
        low = " ".join(w["w"].strip() for w in r[b + 1:][:max(0, n - b - 1)])
        y = 1200
        if top:
            box = small.getbbox(top)
            d.text(((1080 - box[2]) // 2, y), top, font=small, fill=(255, 255, 255, 255), stroke_width=2, stroke_fill=(0, 0, 0, 170))
        y += 66
        if n > b:
            word = r[b]["w"].strip(" ,.!?").upper()
            f = _fit(cfg["font"], word, 980, 190, 70)
            box = f.getbbox(word)
            x = (1080 - box[2] + box[0]) // 2 - box[0]
            soft = Image.new("RGBA", img.size, (0, 0, 0, 0))
            ImageDraw.Draw(soft).text((x, y - box[1]), word, font=f, fill=rgb + (255,))
            soft = soft.filter(ImageFilter.GaussianBlur(26))
            img.alpha_composite(soft)
            img.alpha_composite(soft)
            ImageDraw.Draw(img).text((x, y - box[1]), word, font=f, fill=(255, 255, 255, 255), stroke_width=3, stroke_fill=rgb + (255,))
            y += box[3] - box[1] + 34
        if low:
            box = small.getbbox(low)
            ImageDraw.Draw(img).text(((1080 - box[2]) // 2, y), low, font=small, fill=(255, 255, 255, 255), stroke_width=2, stroke_fill=(0, 0, 0, 170))
    _graphic(src, out, s, e, state, paint)


def flip_cards(src, out, s, e, cfg):
    """Runs of full-screen cards show one word at a time as you say it, flipping black and white, then back to you."""
    from PIL import ImageDraw
    rgb = _rgb(cfg)
    said = cfg.get("said") or []
    runs = [(float(a), float(a) + 2.6) for a in (cfg.get("moments") or [])[1::3]]

    def state(t):
        for i, (a, b) in enumerate(runs):
            if a <= t < b:
                now = [w for w in said if w["t"] <= t]
                return (now[-1]["w"].strip(" ,.!?").upper() if now else "", int((t - a) / 0.85) % 2, i)
        return None

    def paint(img, key):
        word, flip, _ = key
        back, ink = ((6, 6, 8), (255, 255, 255)) if flip == 0 else ((255, 255, 255), rgb)
        d = ImageDraw.Draw(img)
        d.rectangle((0, 0, 1080, 1920), fill=back + (255,))
        f = _fit(cfg["font"], word or " ", 960, 210, 70)
        box = f.getbbox(word or " ")
        d.text(((1080 - box[2] + box[0]) // 2 - box[0], 900 - (box[3] - box[1]) // 2 - box[1]), word, font=f, fill=ink + (255,))
    _graphic(src, out, s, e, state, paint)


def _board(src, out, s, e, cfg, labels, colors, top):
    """A board on your chest with one row per label. Each key word drops into the next row as you say it."""
    from PIL import ImageDraw
    rgb = _rgb(cfg)
    items = _items(cfg, len(labels))
    title = _title(cfg, "My ranking")

    def state(t):
        n = sum(1 for it in items if it["t"] <= t)
        last = max([it["t"] for it in items if it["t"] <= t], default=-9)
        return (n, min(5, int((t - last) / 0.033)))

    def paint(img, key):
        n, step = key
        d = ImageDraw.Draw(img)
        _tag(d, title, _fit(cfg["font"], title, 860, 56, 34), rgb, 150)
        row = (1860 - top) // len(labels)
        x0, lab, x1 = 70, 110, 1010
        f = _font(cfg["font"], 46)
        cell = _font(cfg["font"], 36)
        for i, name in enumerate(labels):
            y = top + i * row
            d.rectangle((x0, y, x1, y + row - 6), fill=(10, 12, 18, 225))
            d.rectangle((x0, y, x0 + lab, y + row - 6), fill=colors[i % len(colors)] + (255,))
            box = f.getbbox(name)
            d.text((x0 + (lab - box[2] + box[0]) // 2 - box[0], y + (row - 6 - box[3] + box[1]) // 2 - box[1]), name, font=f, fill=(10, 12, 18, 255))
            if i < n:
                word = items[i]["w"].upper()[:22]
                drop = (5 - step) * 12 if i == n - 1 else 0
                w_ = cell.getbbox(word)[2] + 40
                d.rounded_rectangle((x0 + lab + 18, y + 8 - drop, x0 + lab + 18 + w_, y + row - 14 - drop), 10, fill=rgb + (255,))
                d.text((x0 + lab + 38, y + (row - 6 - cell.getbbox(word)[3]) // 2 - drop), word, font=cell, fill=_on(rgb) + (255,))
    _graphic(src, out, s, e, state, paint)


def tier_list(src, out, s, e, cfg):
    """An S to F ranking table on your chest. Each item card drops into its row as you say it."""
    _board(src, out, s, e, cfg, ["S", "A", "B", "C", "D", "E", "F"],
           [(255, 127, 127), (255, 191, 127), (255, 223, 127), (191, 255, 127), (127, 223, 255), (127, 127, 255), (255, 127, 255)], 1230)


def top_five(src, out, s, e, cfg):
    """A numbered 1 to 5 board. Each item card drops into its number as you say it."""
    _board(src, out, s, e, cfg, ["5", "4", "3", "2", "1"], [(255, 255, 255)], 1290)


def always_never(src, out, s, e, cfg):
    """A two column chart over your head. Every thing you name drops into Always or Never."""
    from PIL import ImageDraw
    rgb = _rgb(cfg)
    items = _items(cfg, 8)

    def state(t):
        return sum(1 for it in items if it["t"] <= t)

    def paint(img, n):
        d = ImageDraw.Draw(img)
        d.rectangle((0, 0, 1080, 620), fill=(6, 7, 11, 255))
        for y in range(0, 90):
            d.line((0, 620 + y, 1080, 620 + y), fill=(6, 7, 11, int(255 * (1 - y / 90))))
        h = _font(_serif(cfg), 84)
        d.text((270 - h.getbbox("Always")[2] // 2, 110), "Always", font=h, fill=_bright(rgb) + (255,))
        d.text((810 - h.getbbox("Never")[2] // 2, 110), "Never", font=h, fill=(255, 90, 90, 255))
        d.line((60, 225, 1020, 225), fill=(255, 255, 255, 120), width=3)
        d.line((540, 225, 540, 590), fill=(255, 255, 255, 120), width=3)
        f = _font(_plain(cfg), 36)
        for i in range(min(n, len(items))):
            word = items[i]["w"][:22]
            cx = 270 if i % 2 == 0 else 810
            d.text((cx - f.getbbox(word)[2] // 2, 250 + (i // 2) * 76), word, font=f, fill=(255, 255, 255, 255))
    _graphic(src, out, s, e, state, paint, shift=460)


def numbered_list(src, out, s, e, cfg):
    """A title tag up top, and a numbered list fills in down the side as you say each thing."""
    from PIL import ImageDraw
    rgb = _rgb(cfg)
    items = _items(cfg, 9)
    title = _title(cfg, f"{len(items)} things")

    def state(t):
        return sum(1 for it in items if it["t"] <= t)

    def paint(img, n):
        d = ImageDraw.Draw(img)
        _tag(d, title, _fit(cfg["font"], title, 860, 64, 34), rgb, 170)
        f = _font(_plain(cfg), 44)
        for i in range(len(items)):
            y = 320 + i * 70
            d.text((50, y), f"{i + 1}.", font=f, fill=(255, 255, 255, 235), stroke_width=2, stroke_fill=(0, 0, 0, 170))
            if i < n:
                d.text((122, y), items[i]["w"][:18].capitalize(), font=f, fill=(255, 255, 255, 255), stroke_width=2, stroke_fill=(0, 0, 0, 170))
    _graphic(src, out, s, e, state, paint)


def mono_story(src, out, s, e, cfg):
    """Black and white the whole way, with your key words appearing big in an elegant serif."""
    from PIL import ImageDraw
    items = _items(cfg, 24)

    def state(t):
        for it in items:
            if it["t"] <= t < it["t"] + 1.0:
                return it["w"]
        return "-"

    def paint(img, word):
        if word == "-":
            return
        d = ImageDraw.Draw(img)
        f = _fit(_serif(cfg), word, 960, 170, 70)
        box = f.getbbox(word)
        d.text(((1080 - box[2] + box[0]) // 2 - box[0], 300 - box[1]), word, font=f, fill=(255, 255, 255, 255), stroke_width=2, stroke_fill=(0, 0, 0, 120))
    _graphic(src, out, s, e, state, paint, gray=True)


def explainer_panel(src, out, s, e, cfg):
    """A dark panel across the bottom teaches each idea: a small line, one huge word in your color, and a big faint number."""
    from PIL import ImageDraw
    rgb = _rgb(cfg)
    items = _items(cfg, 16)
    said = cfg.get("said") or []

    def state(t):
        now = [i for i, it in enumerate(items) if it["t"] <= t]
        return now[-1] if now else None

    def paint(img, i):
        d = ImageDraw.Draw(img)
        d.rectangle((0, 1240, 1080, 1920), fill=(7, 8, 13, 255))
        d.line((0, 1240, 1080, 1240), fill=rgb + (255,), width=4)
        it = items[i]
        num = f"{i + 1:02d}"
        fn = _font(cfg["font"], 340)
        box = fn.getbbox(num)
        d.text(((1080 - box[2] + box[0]) // 2 - box[0], 1500 - box[1]), num, font=fn, fill=(32, 34, 44, 255))
        near = [w["w"].strip() for w in said if it["t"] - 1.2 <= w["t"] < it["t"]][-5:]
        line = " ".join(near)
        sf = _fit(_serif(cfg), line or " ", 900, 50, 30)
        d.text(((1080 - sf.getbbox(line or " ")[2]) // 2, 1300), line, font=sf, fill=(255, 255, 255, 230))
        word = it["w"].upper()
        f = _fit(cfg["font"], word, 960, 170, 70)
        box = f.getbbox(word)
        d.text(((1080 - box[2] + box[0]) // 2 - box[0], 1385 - box[1]), word, font=f, fill=_bright(rgb) + (255,))
    _graphic(src, out, s, e, state, paint)


def _pics(cfg):
    from PIL import Image, ImageOps
    out = []
    for path in cfg.get("pictures") or []:
        try:
            out.append(ImageOps.exif_transpose(Image.open(path)).convert("RGB"))
        except OSError:
            pass
    if not out:
        raise RuntimeError("This edit needs at least one of your pictures.")
    return out


def _at_beat(cfg, t):
    """Which picture is up: a new one on every shot change."""
    return sum(1 for m in (cfg.get("moments") or []) if float(m) <= t)


def _card(pic, size, round_=26, line=None):
    from PIL import Image, ImageDraw, ImageOps
    w, h = size
    img = ImageOps.fit(pic, size, Image.LANCZOS, centering=(0.5, 0.18)).convert("RGBA")
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, w - 1, h - 1), round_, fill=255)
    img.putalpha(mask)
    if line:
        ImageDraw.Draw(img).rounded_rectangle((0, 0, w - 1, h - 1), round_, outline=line + (255,), width=6)
    return img


def picture_under(src, out, s, e, cfg):
    """You stay put while one of your pictures at a time sits under your chin, changing on every phrase."""
    pics = _pics(cfg)
    line = _rgb(cfg)

    def state(t):
        return _at_beat(cfg, t) % len(pics)

    def paint(img, i):
        img.alpha_composite(_card(pics[i], (800, 560), 30, line), (140, 1200))
    _graphic(src, out, s, e, state, paint)


def picture_above(src, out, s, e, cfg):
    """You move down in the frame and each thing you name shows up above your head, one picture at a time."""
    pics = _pics(cfg)
    line = _rgb(cfg)

    def state(t):
        return _at_beat(cfg, t) % len(pics)

    def paint(img, i):
        img.alpha_composite(_card(pics[i], (900, 620), 34, line), (90, 70))
    _graphic(src, out, s, e, state, paint, shift=520)


def photo_split(src, out, s, e, cfg):
    """Your picture fills the top half and you talk from the bottom half, with a new picture on every phrase."""
    from PIL import Image, ImageOps
    pics = _pics(cfg)

    def state(t):
        return _at_beat(cfg, t) % len(pics)

    def paint(img, i):
        img.paste(ImageOps.fit(pics[i], (1080, 860), Image.LANCZOS, centering=(0.5, 0.18)).convert("RGBA"), (0, 0))
    _graphic(src, out, s, e, state, paint, shift=660)


def photo_world(src, out, s, e, cfg):
    """You shrink down and stand in front of your own pictures, so the whole picture shows, a new world for each idea."""
    from PIL import Image, ImageDraw, ImageFilter, ImageOps
    import numpy as np
    pics = _pics(cfg)
    rows, row_at = _caption_rows(cfg)
    SIZE = 0.60
    backs, words = {}, {}

    def back(i):
        if i not in backs:
            backs.clear()
            pic = pics[i]
            img = ImageOps.fit(pic, (1080, 1920), Image.LANCZOS).filter(ImageFilter.GaussianBlur(40)).point(lambda v: int(v * 0.55)).convert("RGB")
            whole = ImageOps.contain(pic, (1020, 1240), Image.LANCZOS)
            img.paste(whole, ((1080 - whole.width) // 2, 50))
            backs[i] = np.asarray(img, dtype=np.float32)[..., ::-1] / 255
        return backs[i]

    def caption(i):
        if i not in words:
            words.clear()
            img = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
            _caption(ImageDraw.Draw(img), cfg, rows, i, 1690)
            arr = np.asarray(img, dtype=np.float32) / 255
            words[i] = (arr[..., 2::-1].copy(), arr[..., 3:4].copy())
        return words[i]

    def draw(k, t, fr, a):
        pic = back(_at_beat(cfg, t) % len(pics)).copy()
        you, al, x, y = _small_you(fr, a, SIZE)
        pic[y:y + you.shape[0], x:x + you.shape[1]] = pic[y:y + you.shape[0], x:x + you.shape[1]] * (1 - al) + you * al
        rgb, cal = caption(row_at(t))
        return pic * (1 - cal) + rgb * cal
    per_frame(src, out, s, e, draw, matte=True)


def testimonial_wall(src, out, s, e, cfg):
    """A wall of your testimonials scrolls behind you, one pops up big on every idea, and you stand in front."""
    from PIL import Image, ImageDraw, ImageOps
    import numpy as np
    pics = _pics(cfg)
    rgb0 = _rgb(cfg)
    rows, row_at = _caption_rows(cfg)
    SIZE = 0.58
    CW, GAP = 340, 16
    strips = []
    for c in range(3):
        cards, tall = [], 0
        k = c
        while tall < 2600:
            pic = pics[k % len(pics)]
            h = min(560, int(CW * pic.height / max(1, pic.width)))
            cards.append((ImageOps.fit(pic, (CW, h), Image.LANCZOS, centering=(0.5, 0.1)), tall))
            tall += h + GAP
            k += 1
        strip = Image.new("RGB", (CW + GAP, tall), tuple(int(v * 0.25) for v in rgb0))
        for card, y in cards:
            strip.paste(card, (GAP // 2, y))
        strips.append(np.asarray(strip, dtype=np.float32)[..., ::-1] / 255)
    speeds = (46, 70, 56)
    pops, words = {}, {}

    def pop(i):
        if i not in pops:
            pops.clear()
            pic = pics[i]
            card = ImageOps.contain(pic, (960, 820), Image.LANCZOS).convert("RGBA")
            img = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
            x, y = (1080 - card.width) // 2, 70
            d = ImageDraw.Draw(img)
            d.rounded_rectangle((x - 14, y - 14, x + card.width + 14, y + card.height + 14), 26, fill=rgb0 + (255,))
            img.alpha_composite(card, (x, y))
            arr = np.asarray(img, dtype=np.float32) / 255
            pops[i] = (arr[..., 2::-1].copy(), arr[..., 3:4].copy())
        return pops[i]

    def caption(i):
        if i not in words:
            words.clear()
            img = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
            _caption(ImageDraw.Draw(img), cfg, rows, i, 1700)
            arr = np.asarray(img, dtype=np.float32) / 255
            words[i] = (arr[..., 2::-1].copy(), arr[..., 3:4].copy())
        return words[i]

    def draw(k, t, fr, a):
        wall = np.zeros((1920, 1080, 3), np.float32)
        for c, strip in enumerate(strips):
            y0 = int(t * speeds[c]) % (strip.shape[0] - 1920)
            wall[:, c * 360:c * 360 + strip.shape[1]] = strip[y0:y0 + 1920][:, :1080 - c * 360]
        wall *= 0.5
        pr, pa = pop(_at_beat(cfg, t) % len(pics))
        wall = wall * (1 - pa) + pr * pa
        you, al, x, y = _small_you(fr, a, SIZE)
        wall[y:y + you.shape[0], x:x + you.shape[1]] = wall[y:y + you.shape[0], x:x + you.shape[1]] * (1 - al) + you * al
        rgb, cal = caption(row_at(t))
        return wall * (1 - cal) + rgb * cal
    per_frame(src, out, s, e, draw, matte=True)


def photo_grid(src, out, s, e, cfg):
    """You're cut out and centered over a grid of 4 of your pictures that change together."""
    from PIL import Image, ImageOps
    pics = _pics(cfg)

    def state(t):
        return _at_beat(cfg, t) // 2

    def paint(img, n):
        for k in range(4):
            tile = ImageOps.fit(pics[(n * 4 + k) % len(pics)], (536, 956), Image.LANCZOS, centering=(0.5, 0.18)).convert("RGBA")
            img.paste(tile, ((k % 2) * 544, (k // 2) * 964))
    _graphic(src, out, s, e, state, paint, behind=True)


def float_up(src, out, s, e, cfg):
    """Your pictures rise from behind your head and float in the space above you."""
    pics = _pics(cfg)
    line = _rgb(cfg)
    spots = [(70, 150), (640, 120), (360, 60)]

    def state(t):
        n = _at_beat(cfg, t)
        at = [float(m) for m in (cfg.get("moments") or []) if float(m) <= t]
        return (n, min(6, int((t - at[-1]) / 0.05)) if at else 6)

    def paint(img, key):
        n, step = key
        for k in range(min(3, n + 1)):
            i = (n - k) % len(pics)
            x, y = spots[(n - k) % 3]
            rise = (6 - step) * 55 if k == 0 else 0
            img.alpha_composite(_card(pics[i], (370, 370), 26, line), (x, y + rise))
    _graphic(src, out, s, e, state, paint, behind=True)


def photo_cluster(src, out, s, e, cfg):
    """You sit low in the frame and a cluster of your pictures fills the space above your head."""
    pics = _pics(cfg)

    def state(t):
        return _at_beat(cfg, t)

    def paint(img, n):
        spots = [((40, 70), (500, 340)), ((560, 50), (480, 300)), ((90, 430), (420, 300)), ((530, 370), (500, 360))]
        for k, ((x, y), size) in enumerate(spots):
            img.alpha_composite(_card(pics[(n + k) % len(pics)], size, 22), (x, y))
    _graphic(src, out, s, e, state, paint, shift=640)


def behind_you(src, out, s, e, cfg):
    """A big panel with your picture floats on the wall behind your head, like it's really in the room."""
    pics = _pics(cfg)
    line = _rgb(cfg)

    def state(t):
        return _at_beat(cfg, t) % len(pics)

    def paint(img, i):
        img.alpha_composite(_card(pics[i], (960, 760), 34, line), (60, 110))
    _graphic(src, out, s, e, state, paint, behind=True)


def ear_to_ear(src, out, s, e, cfg):
    """Your words fade up either side of your head at eye level, one at a time: left, then right."""
    from PIL import ImageDraw
    said = cfg.get("said") or []

    def state(t):
        now = [i for i, w in enumerate(said) if w["t"] <= t < w["e"] + 0.25]
        return now[-1] if now else None

    def paint(img, i):
        d = ImageDraw.Draw(img)
        word = said[i]["w"].strip(" ,.!?").upper()
        f = _fit(_serif(cfg), word, 330, 84, 34)
        x = 40 if i % 2 == 0 else 1040 - f.getbbox(word)[2]
        d.text((x, 640), word, font=f, fill=(255, 255, 255, 255), stroke_width=2, stroke_fill=(0, 0, 0, 170))
    _graphic(src, out, s, e, state, paint)


def fitted_stack(src, out, s, e, cfg):
    """One big word in your color, with the rest of the line fitted around it, filling in word by word."""
    from PIL import ImageDraw
    rgb = _rgb(cfg)
    rows = _sentences(cfg, 6)
    big = [max(range(len(r)), key=lambda i: len(r[i]["w"].strip(" ,.!?"))) for r in rows]

    def state(t):
        for i, r in enumerate(rows):
            end = rows[i + 1][0]["t"] if i + 1 < len(rows) else r[-1]["e"] + 0.5
            if r[0]["t"] - 0.05 <= t < end:
                return (i, sum(1 for w in r if w["t"] <= t))
        return None

    def paint(img, key):
        i, n = key
        r, b = rows[i], big[i]
        d = ImageDraw.Draw(img)
        y = 1120
        for part, color, top in ((r[:b], (255, 255, 255), 96), (r[b:b + 1], _bright(rgb), 210), (r[b + 1:], (255, 255, 255), 96)):
            shown = [w["w"].strip(" ,.!?").upper() for k, w in enumerate(part) if w in r[:n]]
            if not part:
                continue
            line = " ".join(shown)
            whole = " ".join(w["w"].strip(" ,.!?").upper() for w in part)
            f = _fit(cfg["font"], whole, 980, top, 44)
            box = f.getbbox(whole)
            if line:
                d.text(((1080 - box[2] + box[0]) // 2 - box[0], y - box[1]), line, font=f, fill=color + (255,), stroke_width=4, stroke_fill=(0, 0, 0, 200))
            y += box[3] - box[1] + 20
    _graphic(src, out, s, e, state, paint)


def if_then(src, out, s, e, cfg):
    """A colored grid over your head that fills in row by row as you walk through it."""
    from PIL import ImageDraw
    rgb = _rgb(cfg)
    items = _items(cfg, 8)
    colors = [_bright(rgb), (255, 196, 84), (84, 214, 160), (255, 120, 120)]

    def state(t):
        return sum(1 for it in items if it["t"] <= t)

    def paint(img, n):
        d = ImageDraw.Draw(img)
        d.rectangle((0, 0, 1080, 660), fill=(8, 9, 14, 255))
        hf = _font(_serif(cfg), 62)
        d.text((90, 40), "If", font=hf, fill=(255, 255, 255, 255))
        d.text((590, 40), "Then", font=hf, fill=(255, 255, 255, 255))
        f = _font(cfg["font"], 36)
        for i in range(4):
            y = 130 + i * 128
            for c in range(2):
                x = 60 + c * 500
                k = i * 2 + c
                on = k < min(n, len(items))
                d.rounded_rectangle((x, y, x + 460, y + 112), 16, fill=(colors[i] + (255,)) if on else (28, 30, 40, 255))
                if on:
                    word = items[k]["w"][:18]
                    d.text((x + 24, y + 34), word, font=f, fill=(8, 9, 14, 255))
    _graphic(src, out, s, e, state, paint, shift=500)


def quadrant(src, out, s, e, cfg):
    """A 4 box grid on a dark card over your head reveals one box at a time, frosted until it's your turn."""
    from PIL import ImageDraw
    rgb = _rgb(cfg)
    items = _items(cfg, 4)
    title = _title(cfg, "The 4 boxes")

    def state(t):
        return sum(1 for it in items if it["t"] <= t)

    def paint(img, n):
        d = ImageDraw.Draw(img)
        d.rectangle((0, 0, 1080, 840), fill=(6, 7, 11, 255))
        tf = _fit(_serif(cfg), title, 940, 66, 34)
        d.text(((1080 - tf.getbbox(title)[2]) // 2, 44), title, font=tf, fill=(255, 255, 255, 255))
        f = _fit(cfg["font"], max((i["w"].upper()[:14] for i in items), key=len, default="W"), 350, 58, 26)
        q = _font(cfg["font"], 110)
        for k in range(4):
            x, y = 130 + (k % 2) * 420, 150 + (k // 2) * 330
            on = k < min(n, len(items))
            d.rounded_rectangle((x, y, x + 400, y + 310), 22, fill=(_bright(rgb) + (255,)) if on else (24, 26, 34, 255), outline=(255, 255, 255, 60), width=2)
            text = items[k]["w"][:14].upper() if on else "?"
            font = f if on else q
            box = font.getbbox(text)
            d.text((x + (400 - box[2] + box[0]) // 2 - box[0], y + (310 - box[3] + box[1]) // 2 - box[1]), text, font=font, fill=(8, 9, 14, 255) if on else (80, 84, 100, 255))
    _graphic(src, out, s, e, state, paint, shift=640)


def cinema_type(src, out, s, e, cfg):
    """Black title cards in an elegant serif cut in between your shots, like a movie trailer."""
    from PIL import ImageDraw
    items = _items(cfg, 12)
    rgb = _bright(_rgb(cfg))

    def state(t):
        for i, it in enumerate(items):
            if i % 2 == 0 and it["t"] <= t < it["t"] + 0.9:
                return it["w"]
        return None

    def paint(img, word):
        d = ImageDraw.Draw(img)
        d.rectangle((0, 0, 1080, 1920), fill=(5, 5, 7, 255))
        f = _fit(_serif(cfg), word, 940, 190, 70)
        box = f.getbbox(word)
        d.text(((1080 - box[2] + box[0]) // 2 - box[0], 880 - box[1]), word, font=f, fill=(255, 255, 255, 255))
        d.line((440, 1120, 640, 1120), fill=rgb + (255,), width=6)
    _graphic(src, out, s, e, state, paint)


def line_by_line(src, out, s, e, cfg):
    """Every line picks its own look: you with small words, a black card, or one huge word in your color."""
    from PIL import ImageDraw
    rgb = _rgb(cfg)
    rows = _sentences(cfg, 6)

    def state(t):
        for i, r in enumerate(rows):
            end = rows[i + 1][0]["t"] if i + 1 < len(rows) else r[-1]["e"] + 0.5
            if r[0]["t"] - 0.05 <= t < end:
                return (i, sum(1 for w in r if w["t"] <= t))
        return None

    def paint(img, key):
        i, n = key
        d = ImageDraw.Draw(img)
        words = [w["w"].strip() for w in rows[i][:n]]
        line = " ".join(words)
        if i % 3 == 1:
            d.rectangle((0, 0, 1080, 1920), fill=(5, 5, 7, 255))
            f = _font(_serif(cfg), 92)
            lines, cur = [], ""
            for w in words:
                if f.getbbox(cur + " " + w)[2] > 940:
                    lines.append(cur)
                    cur = w
                else:
                    cur = (cur + " " + w).strip()
            lines.append(cur)
            for k, x in enumerate(lines):
                d.text(((1080 - f.getbbox(x)[2]) // 2, 780 + k * 120), x, font=f, fill=(255, 255, 255, 255))
        elif i % 3 == 2:
            word = max((w.strip(" ,.!?") for w in words), key=len, default=" ").upper()
            f = _fit(cfg["font"], word, 980, 200, 70)
            box = f.getbbox(word)
            d.text(((1080 - box[2] + box[0]) // 2 - box[0], 1180 - box[1]), word, font=f, fill=_bright(rgb) + (255,), stroke_width=4, stroke_fill=(0, 0, 0, 220))
        else:
            f = _fit(_plain(cfg), line or " ", 980, 54, 32)
            d.text(((1080 - f.getbbox(line or " ")[2]) // 2, 1260), line, font=f, fill=(255, 255, 255, 255), stroke_width=3, stroke_fill=(0, 0, 0, 200))
    _graphic(src, out, s, e, state, paint)


def short_box(src, out, s, e, cfg):
    """A clean white text box hook up top for the first few seconds, with small two line outlined captions the whole way."""
    from PIL import ImageDraw
    said = cfg.get("said") or []
    hook = " ".join(w["w"].strip() for w in said[:7]).strip(" ,.")
    groups = [said[i:i + 5] for i in range(0, len(said), 5)]
    typed = (cfg.get("typed") or [None])[0]
    hook = typed or hook

    def state(t):
        g = next((i for i, x in enumerate(groups) if x[0]["t"] <= t < (groups[i + 1][0]["t"] if i + 1 < len(groups) else x[-1]["e"] + 0.4)), None)
        return (t < 4, g)

    def paint(img, key):
        show, g = key
        d = ImageDraw.Draw(img)
        if show:
            f = _font(_plain(cfg), 50)
            lines, cur = [], ""
            for w in hook.split():
                if f.getbbox(cur + " " + w)[2] > 880:
                    lines.append(cur)
                    cur = w
                else:
                    cur = (cur + " " + w).strip()
            lines.append(cur)
            for k, x in enumerate(lines[:3]):
                w_ = f.getbbox(x)[2]
                d.rounded_rectangle(((1080 - w_) // 2 - 20, 200 + k * 76, (1080 + w_) // 2 + 20, 200 + k * 76 + 72), 12, fill=(255, 255, 255, 255))
                d.text(((1080 - w_) // 2, 208 + k * 76), x, font=f, fill=(0, 0, 0, 255))
        if g is not None:
            f = _font(_plain(cfg), 44)
            words = [w["w"].strip() for w in groups[g]]
            for k, x in enumerate([" ".join(words[:3]), " ".join(words[3:])]):
                if x:
                    d.text(((1080 - f.getbbox(x)[2]) // 2, 1340 + k * 60), x, font=f, fill=(255, 255, 255, 255), stroke_width=3, stroke_fill=(0, 0, 0, 255))
    _graphic(src, out, s, e, state, paint)


def voice_note(src, out, s, e, cfg):
    """A voice message bubble floats over you with a moving waveform and a running time."""
    from PIL import ImageDraw
    import math
    rgb = _rgb(cfg)
    bars = [0.35 + 0.65 * abs(math.sin(i * 0.9) * math.cos(i * 0.37)) for i in range(26)]
    length = max(1.0, float(e) - float(s))

    def state(t):
        return min(int(t / 0.1), int(length * 10))

    def paint(img, k):
        d = ImageDraw.Draw(img)
        d.rounded_rectangle((70, 200, 1010, 390), 70, fill=rgb + (255,))
        on = _on(rgb)
        d.ellipse((100, 230, 230, 360), fill=on + (255,))
        d.polygon([(148, 262), (148, 328), (200, 295)], fill=rgb + (255,))
        now = k / (length * 10)
        for i, b in enumerate(bars):
            x = 262 + i * 22
            h = int(84 * b * (0.7 + 0.3 * math.sin(k * 0.6 + i)))
            d.rounded_rectangle((x, 295 - h // 2, x + 11, 295 + h // 2), 5, fill=on + (255 if i / len(bars) <= now else 110,))
        f = _font(_plain(cfg), 38)
        sec = int(k / 10)
        d.text((850, 270), f"{sec // 60}:{sec % 60:02d}", font=f, fill=on + (255,))
    _graphic(src, out, s, e, state, paint)


def headline_wall(src, out, s, e, cfg):
    """Your key words stack into a growing wall of big headlines behind your head."""
    from PIL import ImageDraw
    rgb = _bright(_rgb(cfg))
    items = _items(cfg, 8)

    def state(t):
        return sum(1 for it in items if it["t"] <= t)

    def paint(img, n):
        d = ImageDraw.Draw(img)
        y = 90
        for i in range(min(n, len(items))):
            word = items[i]["w"].upper()
            f = _fit(cfg["font"], word, 1020, 170, 80)
            box = f.getbbox(word)
            d.text(((1080 - box[2] + box[0]) // 2 - box[0], y - box[1]), word, font=f, fill=(rgb if i % 2 else (255, 255, 255)) + (255,))
            y += box[3] - box[1] + 22
            if y > 1100:
                break
    _graphic(src, out, s, e, state, paint, behind=True)


def cover_story(src, out, s, e, cfg):
    """You're the cover, and your keyword sits at the top the whole video: Comment "AI" For The Free Guide."""
    from PIL import Image, ImageDraw
    rgb = _bright(_rgb(cfg))
    typed = ", ".join(cfg.get("typed") or []).strip()
    if not typed:
        keys = _items(cfg, 1)
        typed = 'Comment "%s" For More' % (keys[0]["w"].strip(" ,.!?").upper() if keys else "INFO")
    parts = re.split(r"\s+(for)\s+", typed, maxsplit=1, flags=re.I)
    ask = parts[0].upper()
    get = ("FOR " + parts[2]).upper() if len(parts) == 3 else ""
    room = max(300, _head(src, 0.0, float(e))[0] + 40)

    def state(t):
        return 1

    def paint(img, _):
        d = ImageDraw.Draw(img)
        for y in range(0, 620):
            d.line((0, y, 1080, y), fill=(0, 0, 0, int(190 * (1 - y / 620))))
        d.rectangle((36, 36, 1044, 1884), outline=rgb + (255,), width=10)
        big = _fit(_serif(cfg), ask, 960, 170, 50)
        small = _fit(cfg["font"], get or " ", 940, 74, 34)
        tall = big.getbbox(ask)[3] - big.getbbox(ask)[1]
        if get and tall + 90 > room - 80:
            big = _fit(_serif(cfg), ask, 960, max(50, room - 180), 50)
        box = big.getbbox(ask)
        x = (1080 - box[2] + box[0]) // 2 - box[0]
        y = 86
        pieces = re.split(r'(["\u201c\u201d][^"\u201c\u201d]+["\u201c\u201d])', ask)
        for piece in pieces:            # the keyword itself goes in their color, so it's what the eye lands on
            hot = piece[:1] in ('"', "\u201c", "\u201d")
            d.text((x, y - box[1]), piece, font=big, fill=(rgb if hot else (255, 255, 255)) + (255,), stroke_width=2, stroke_fill=(0, 0, 0, 200))
            x += big.getlength(piece)
        y += box[3] - box[1] + 26
        if get:
            _center(d, get, small, y, (255, 255, 255, 255), stroke_width=3, stroke_fill=(0, 0, 0, 200))
    _graphic(src, out, 0.0, float(e), state, paint)


def paper_cut(src, out, s, e, cfg):
    """A rough torn paper edge frames the bottom of the screen, and your key words are written on it."""
    from PIL import ImageDraw
    import random
    rgb = _rgb(cfg)
    items = _items(cfg, 16)
    rnd = random.Random(7)
    edge = [(0, 1500)] + [(x, 1500 + rnd.randint(-22, 22)) for x in range(40, 1081, 40)] + [(1080, 1500), (1080, 1920), (0, 1920)]
    hand = cfg.get("hand") or _serif(cfg)

    def state(t):
        now = [i for i, it in enumerate(items) if it["t"] <= t]
        return now[-1] if now else -1

    def paint(img, i):
        d = ImageDraw.Draw(img)
        d.polygon([(x, y + 12) for x, y in edge], fill=(0, 0, 0, 90))
        d.polygon(edge, fill=(247, 243, 232, 255))
        if i >= 0:
            word = items[i]["w"]
            f = _fit(hand, word, 900, 150, 60)
            box = f.getbbox(word)
            d.text(((1080 - box[2] + box[0]) // 2 - box[0], 1610 - box[1]), word, font=f, fill=rgb + (255,))
    _graphic(src, out, s, e, state, paint)


def vertigo(src, out, s, e, cfg):
    """The movie moment: you hold still while the whole room rushes away behind you, with speed blur, on your first few seconds."""
    import cv2
    import numpy as np
    end = min(float(e), 5.0)
    W, H = 1080, 1920
    held = {"sum": None, "weight": None, "plate": None, "n": 0}

    def build():
        # one clean picture of the room, you painted out: everything you uncovered as you moved, the rest filled from around it
        room = held["sum"] / (held["weight"] + 1e-3)
        hole = (held["weight"][..., 0] < 0.6).astype(np.uint8) * 255
        small = cv2.resize((room.clip(0, 1) * 255).astype(np.uint8), (270, 480))
        fill = cv2.inpaint(small, cv2.resize(hole, (270, 480), interpolation=cv2.INTER_NEAREST), 9, cv2.INPAINT_TELEA)
        fill = cv2.resize(cv2.GaussianBlur(fill, (0, 0), 3), (W, H)).astype(np.float32) / 255
        mask = cv2.GaussianBlur(hole.astype(np.float32) / 255, (0, 0), 12)[..., None]
        return room * (1 - mask) + fill * mask

    def zoomed(plate, z):
        w, h = int(W * z), int(H * z)
        big = cv2.resize(plate, (w, h), interpolation=cv2.INTER_LINEAR)
        x, y = (w - W) // 2, (h - H) // 2
        return big[y:y + H, x:x + W]

    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    dark = (1 - 0.62 * np.clip(((xx - W / 2) / (W * 0.62)) ** 2 + ((yy - H * 0.42) / (H * 0.62)) ** 2, 0, 1))[..., None]

    def draw(k, t, fr, a):
        keep = (1 - a) ** 4
        if held["sum"] is None:
            held["sum"], held["weight"] = fr * keep, keep.copy()
        elif k % 4 == 0 and k < 40:
            held["sum"] += fr * keep
            held["weight"] += keep
        if k < 40:          # settle first: the rush starts once the room is known
            held["plate"] = None
            return fr
        if held["plate"] is None:
            held["plate"] = build()
        go = min(1.0, (t - 40 / 30) / max(end - 40 / 30 - 0.2, 0.5))
        z = 1.0 + 1.25 * go ** 2.2
        speed = 0.09 * go ** 1.2
        room = sum(zoomed(held["plate"], z * (1 + speed * i / 5)) for i in range(6)) / 6
        room = room * (1 - (1 - dark) * go)
        return room * (1 - a) + fr * a
    per_frame(src, out, 0.0, end, draw, matte=True)


def _wrap(text, font, width):
    lines, cur = [], ""
    for w in str(text).split():
        if font.getbbox((cur + " " + w).strip())[2] > width and cur:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    return lines + ([cur] if cur else [])


def _center(d, text, font, y, fill, **kw):
    box = font.getbbox(text)
    d.text(((1080 - box[2] + box[0]) // 2 - box[0], y - box[1]), text, font=font, fill=fill, **kw)
    return box[3] - box[1]


def _now(items, t):
    hit = [i for i, it in enumerate(items) if it["t"] <= t]
    return hit[-1] if hit else None


def _line_chart(d, x0, y0, x1, y1, step, color):
    """A line that climbs as you talk. No numbers on it, because no number was said."""
    pts = [(0, .12), (.14, .2), (.28, .18), (.42, .38), (.56, .44), (.7, .66), (.84, .74), (1, .96)]
    upto = max(2, int(2 + step * 6))
    xy = [(x0 + (x1 - x0) * a, y1 - (y1 - y0) * b) for a, b in pts[:upto]]
    for g in range(1, 4):
        gy = y0 + (y1 - y0) * g / 4
        d.line((x0, gy, x1, gy), fill=(255, 255, 255, 50), width=2)
    d.line(xy, fill=color + (255,), width=12, joint="curve")
    x, y = xy[-1]
    d.ellipse((x - 16, y - 16, x + 16, y + 16), fill=(255, 255, 255, 255))


def growth_chart(src, out, s, e, cfg):
    """A line chart climbs on a dark card below your face as you talk, with your words on the card. Your whole face stays clear."""
    from PIL import ImageDraw
    rgb = _bright(_rgb(cfg))
    items = _items(cfg, 6)
    rows, row_at = _caption_rows(cfg)
    move = _aim(_head(src, s, e), 70, 1250)

    def state(t):
        return (sum(1 for it in items if it["t"] <= t), row_at(t))

    def paint(img, key):
        n, i = key
        d = ImageDraw.Draw(img)
        d.rounded_rectangle((60, 1290, 1020, 1840), 34, fill=(9, 11, 18, 245))
        _caption(d, cfg, rows, i, 1325, 62)
        word = items[min(n, len(items)) - 1]["w"].upper() if n else ""
        if word:
            d.text((120, 1420), word, font=_fit(cfg["font"], word, 800, 42, 28), fill=rgb + (255,))
        _line_chart(d, 120, 1490, 960, 1800, n / max(1, len(items)), rgb)
    _graphic(src, out, s, e, state, paint, move=move)


def glass_graph(src, out, s, e, cfg):
    """A frosted glass card sits below your face with a line climbing on it and your words on the glass."""
    from PIL import ImageDraw
    rgb = _bright(_rgb(cfg))
    items = _items(cfg, 6)
    rows, row_at = _caption_rows(cfg)
    move = _aim(_head(src, s, e), 70, 1250)

    def state(t):
        return (sum(1 for it in items if it["t"] <= t), row_at(t))

    def paint(img, key):
        n, i = key
        d = ImageDraw.Draw(img)
        d.rounded_rectangle((60, 1290, 1020, 1840), 40, outline=(255, 255, 255, 170), width=3)
        _caption(d, cfg, rows, i, 1325, 62)
        word = items[min(n, len(items)) - 1]["w"] if n else ""
        if word:
            d.text((120, 1420), word, font=_fit(_serif(cfg), word, 800, 46, 28), fill=(255, 255, 255, 255))
        _line_chart(d, 120, 1490, 960, 1800, n / max(1, len(items)), rgb)
    _graphic(src, out, s, e, state, paint, glass=lambda k: [(60, 1290, 1020, 1840)], move=move)


def wall_words(src, out, s, e, cfg):
    """Your key word looks painted huge on the wall behind you, changing with each idea."""
    from PIL import ImageDraw
    rgb = _bright(_rgb(cfg))
    items = _items(cfg, 16)

    def state(t):
        return _now(items, t)

    def paint(img, i):
        if i is None:
            return
        d = ImageDraw.Draw(img)
        word = items[i]["w"].upper()
        y = 120
        for part in (word[:len(word) // 2 + 1], word[len(word) // 2 + 1:]) if len(word) > 8 else (word,):
            y += _center(d, part, _fit(cfg["font"], part, 1040, 330, 120), y, rgb + (205,)) + 30
    _graphic(src, out, s, e, state, paint, behind=True)


def glass_words(src, out, s, e, cfg):
    """Your key words land on a frosted glass strip across the middle of the picture."""
    from PIL import ImageDraw
    items = _items(cfg, 20)

    def state(t):
        i = _now(items, t)
        return i if i is not None and t < items[i]["t"] + 1.6 else None

    def paint(img, i):
        d = ImageDraw.Draw(img)
        d.rounded_rectangle((60, 1130, 1020, 1400), 40, outline=(255, 255, 255, 170), width=3)
        word = items[i]["w"]
        f = _fit(_serif(cfg), word, 880, 150, 50)
        box = f.getbbox(word)
        d.text(((1080 - box[2] + box[0]) // 2 - box[0], 1265 - (box[3] - box[1]) // 2 - box[1]), word, font=f, fill=(255, 255, 255, 255))
    _graphic(src, out, s, e, state, paint, glass=lambda k: [(60, 1130, 1020, 1400)])


def glass_panel(src, out, s, e, cfg):
    """A frosted panel across the bottom with a small business graphic and one key word as you teach."""
    from PIL import ImageDraw
    rgb = _bright(_rgb(cfg))
    items = _items(cfg, 16)

    def state(t):
        return _now(items, t)

    def paint(img, i):
        if i is None:
            return
        d = ImageDraw.Draw(img)
        d.rounded_rectangle((50, 1220, 1030, 1840), 44, outline=(255, 255, 255, 170), width=3)
        _center(d, items[i]["w"].upper(), _fit(cfg["font"], items[i]["w"].upper(), 860, 110, 44), 1280, (255, 255, 255, 255))
        for k in range(5):
            h = 60 + (k + i) % 5 * 62
            x = 240 + k * 130
            d.rounded_rectangle((x, 1780 - h, x + 84, 1780), 14, fill=rgb + (255,) if k <= i % 5 else (255, 255, 255, 70))
    _graphic(src, out, s, e, state, paint, glass=lambda k: [(50, 1220, 1030, 1840)])


def match_cut(src, out, s, e, cfg):
    """Every shot change flips and reframes you, like it was shot from the other side of the room."""
    w, h = dims(src)
    at = _moments(cfg, 1, 14)
    z = _zoom_expr(at, levels=(1.2, 1.06, 1.3, 1.12), push=0.01)
    flip = "+".join(f"between(t,{a:.3f},{at[i + 1] if i + 1 < len(at) else 99999:.3f})" for i, a in enumerate(at) if i % 2 == 0) or "0"
    _fx(src, out, f"[0:v]split[a][b];[b]hflip,eq=contrast=1.05:saturation=1.08[f];[a][f]overlay=enable='{flip}',"
                  f"scale=w='trunc(iw*{z}/2)*2':h='trunc(ih*{z}/2)*2':eval=frame,crop={w}:{h}:(iw-{w})/2:(ih-{h})*0.38,setsar=1[v]")


def shoulder_push(src, out, s, e, cfg):
    """The camera drifts in from one side and then the other, like it's looking over a shoulder."""
    w, h = dims(src)
    at = _moments(cfg, 1, 14)
    z = "(1.32+0.06*sin(t*0.5))"
    side = "+".join(f"between(t,{a:.3f},{at[i + 1] if i + 1 < len(at) else 99999:.3f})" for i, a in enumerate(at) if i % 2 == 0) or "0"
    _fx(src, out, f"[0:v]scale=w='trunc(iw*{z}/2)*2':h='trunc(ih*{z}/2)*2':eval=frame,crop={w}:{h}:'(iw-{w})*(0.15+0.7*min(1,{side}))':'(ih-{h})*0.3',setsar=1[v]")


def _screen_take(src, out, s, e, cfg, zoom):
    """Your screenshot pushes in and takes the whole frame while you shrink into a corner, then you come back."""
    import cv2
    import numpy as np
    from PIL import Image, ImageOps
    pics = _pics(cfg)
    at = _moments(cfg, 2, 8)
    W, H = 1080, 1920
    shots = [np.asarray(ImageOps.fit(p, (W, H), Image.LANCZOS, centering=(0.5, 0.18)), np.float32)[..., ::-1] / 255 for p in pics]

    def draw(k, t, fr, a):
        for i, m in enumerate(at):
            if m <= t < m + 3.0:
                shot, u = shots[i % len(shots)], t - m
                inn = min(1, u / 0.25)
                if zoom:
                    z = 1 + 0.25 * min(1, u / 3)
                    bw, bh = int(W * z), int(H * z)
                    big = cv2.resize(shot, (bw, bh))
                    shot = big[(bh - H) // 2:(bh - H) // 2 + H, (bw - W) // 2:(bw - W) // 2 + W]
                x = int(W * (1 - inn))
                img = fr.copy()
                img[:, x:] = shot[:, :W - x]
                pw, ph = 360, 640
                small = cv2.resize(fr, (pw, ph))
                img[H - ph - 60:H - 60, W - pw - 50:W - 50] = small
                return img
        return fr
    per_frame(src, out, s, e, draw)


def screen_slide(src, out, s, e, cfg):
    """Your screenshot slides in and fills the frame while you shrink to the corner, then you're back."""
    _screen_take(src, out, s, e, cfg, False)


def screen_zoom(src, out, s, e, cfg):
    """Your screenshot slides in and slowly pushes closer while you talk from the corner."""
    _screen_take(src, out, s, e, cfg, True)


def end_stack(src, out, s, e, cfg):
    """Your call to action stacks up in cards for the last few seconds."""
    from PIL import ImageDraw
    rgb = _rgb(cfg)
    cta = str(cfg.get("cta") or "Follow for more")
    words = cta.split()
    cards = [" ".join(words[i:i + 3]) for i in range(0, len(words), 3)][:4]
    start = max(0.0, float(e) - 5.0)

    def state(t):
        return min(len(cards), int((t - start) / 0.7) + 1) if t >= start else None

    def paint(img, n):
        d = ImageDraw.Draw(img)
        y = 1730 - 146 * len(cards) + 16      # low on the screen, under your face, with the last card on the bottom
        for i in range(n):
            f = _fit(cfg["font"], cards[i].upper(), 820, 74, 36)
            d.rounded_rectangle((90 + i * 8, y, 990 - i * 8, y + 130), 26, fill=(rgb if i % 2 == 0 else (255, 255, 255)) + (255,))
            box = f.getbbox(cards[i].upper())
            d.text(((1080 - box[2] + box[0]) // 2 - box[0], y + (130 - box[3] + box[1]) // 2 - box[1]), cards[i].upper(), font=f, fill=(_on(rgb) if i % 2 == 0 else rgb) + (255,))
            y += 146
    _graphic(src, out, s, e, state, paint)


def app_world(src, out, s, e, cfg):
    """You're cut out in front of floating app screens that fill in with your key words."""
    from PIL import ImageDraw
    rgb = _bright(_rgb(cfg))
    items = _items(cfg, 12)

    def state(t):
        return sum(1 for it in items if it["t"] <= t)

    def paint(img, n):
        d = ImageDraw.Draw(img)
        d.rectangle((0, 0, 1080, 1920), fill=(7, 11, 28, 255))
        for gx in range(0, 1080, 90):
            d.line((gx, 0, gx, 1920), fill=(255, 255, 255, 14))
        f = _font(_plain(cfg), 32)
        spots = [(40, 90), (590, 170), (60, 620), (630, 720), (30, 1120), (640, 1260)]
        for k, (x, y) in enumerate(spots):
            d.rounded_rectangle((x, y, x + 410, y + 430), 30, fill=(20, 26, 52, 255), outline=(255, 255, 255, 60), width=2)
            for c, col in enumerate(((255, 96, 92), (255, 190, 46), (40, 200, 64))):
                d.ellipse((x + 22 + c * 30, y + 22, x + 42 + c * 30, y + 42), fill=col + (255,))
            for r in range(3):
                j = k * 2 + r
                if j < min(n, len(items)):
                    d.rounded_rectangle((x + 24, y + 74 + r * 110, x + 386, y + 164 + r * 110), 18, fill=rgb + (255,))
                    d.text((x + 46, y + 100 + r * 110), items[j]["w"][:16], font=f, fill=(6, 10, 26, 255))
                else:
                    d.rounded_rectangle((x + 24, y + 74 + r * 110, x + 386, y + 164 + r * 110), 18, fill=(38, 44, 72, 255))
    _graphic(src, out, s, e, state, paint, behind=True)


def picture_stack(src, out, s, e, cfg):
    """Your pictures cut in full screen on your key lines, with big stacked words over them."""
    from PIL import Image, ImageDraw, ImageOps
    pics = _pics(cfg)
    rgb = _bright(_rgb(cfg))
    items = _items(cfg, 16)

    def state(t):
        for i, it in enumerate(items):
            if i % 2 == 0 and it["t"] <= t < it["t"] + 1.4:
                return i
        return None

    def paint(img, i):
        img.paste(ImageOps.fit(pics[(i // 2) % len(pics)], (1080, 1920), Image.LANCZOS, centering=(0.5, 0.18)).convert("RGBA"), (0, 0))
        d = ImageDraw.Draw(img)
        word = items[i]["w"].upper()
        _center(d, word, _fit(cfg["font"], word, 980, 220, 80), 1120, rgb + (255,), stroke_width=6, stroke_fill=(255, 255, 255, 255))
    _graphic(src, out, s, e, state, paint)


def story_room(src, out, s, e, cfg):
    """A calm story in your real room. Your pictures and short quote cards appear behind you as you talk."""
    from PIL import ImageDraw
    pics = _pics(cfg)
    rows = _sentences(cfg, 7)

    def state(t):
        n = _at_beat(cfg, t)
        return n

    def paint(img, n):
        if n % 3 == 2:
            d = ImageDraw.Draw(img)
            line = " ".join(w["w"].strip() for w in rows[n % len(rows)]) if rows else ""
            d.rounded_rectangle((90, 110, 990, 700), 30, fill=(248, 244, 234, 255))
            f = _font(_serif(cfg), 66)
            y = 180
            for x in _wrap(line, f, 780)[:5]:
                y += _center(d, x, f, y, (30, 26, 22, 255)) + 26
        else:
            img.alpha_composite(_card(pics[n % len(pics)], (900, 620), 18), (90, 90))
    _graphic(src, out, s, e, state, paint, behind=True)


def then_and_now(src, out, s, e, cfg):
    """Your opening plays your old photos with a year and one line each, then it drops into you talking."""
    from PIL import Image, ImageDraw, ImageOps
    pics = _pics(cfg)
    typed = list(cfg.get("typed") or [])
    each = 1.6
    last = len(pics) * each

    def state(t):
        return int(t / each) if t < last else None

    def paint(img, i):
        img.paste(ImageOps.fit(pics[i], (1080, 1920), Image.LANCZOS, centering=(0.5, 0.18)).convert("RGBA"), (0, 0))
        d = ImageDraw.Draw(img)
        if i < len(typed):
            parts = _wrap(typed[i], _font(cfg["font"], 96), 960)
            y = 300
            for x in parts[:2]:
                y += _center(d, x, _font(cfg["font"], 96), y, (255, 255, 255, 255), stroke_width=4, stroke_fill=(0, 0, 0, 200)) + 18
    _graphic(src, out, s, e, state, paint, gray=lambda t: t < last)


def proof_above(src, out, s, e, cfg):
    """You stay in one spot while 3 frames of real proof sit above your head, and they light up in turn."""
    from PIL import ImageDraw
    pics = _pics(cfg)
    rgb = _bright(_rgb(cfg))

    def state(t):
        return _at_beat(cfg, t)

    def paint(img, n):
        d = ImageDraw.Draw(img)
        d.rectangle((0, 0, 1080, 520), fill=(6, 7, 11, 255))
        for k in range(3):
            on = k == n % 3
            x, size = 40 + k * 340, (320, 440)
            img.alpha_composite(_card(pics[(n // 3 * 3 + k) % len(pics)], size, 24, rgb if on else None), (x, 40))
            if not on:
                d.rounded_rectangle((x, 40, x + 320, 480), 24, fill=None, outline=(255, 255, 255, 60), width=2)
    _graphic(src, out, s, e, state, paint, shift=480)


def word_morph(src, out, s, e, cfg):
    """The words you say turn into things: each key word becomes a price-tag sticker that swings in."""
    from PIL import Image, ImageDraw
    rgb = _rgb(cfg)
    items = _items(cfg, 16)

    def state(t):
        i = _now(items, t)
        if i is None or t >= items[i]["t"] + 1.5:
            return None
        return (i, min(6, int((t - items[i]["t"]) / 0.035)))

    def paint(img, key):
        i, step = key
        word = items[i]["w"].upper()
        f = _fit(cfg["font"], word, 620, 110, 44)
        box = f.getbbox(word)
        w, h = box[2] - box[0] + 130, box[3] - box[1] + 76
        tag = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(tag)
        d.rounded_rectangle((0, 0, w - 1, h - 1), 24, fill=(255, 255, 255, 255), outline=rgb + (255,), width=8)
        d.ellipse((22, h // 2 - 15, 52, h // 2 + 15), fill=rgb + (255,))
        d.text((88 - box[0], 38 - box[1]), word, font=f, fill=rgb + (255,))
        tag = tag.rotate((6 - step) * 7 - 5, expand=True, resample=Image.BICUBIC)
        img.alpha_composite(tag, ((1080 - tag.width) // 2, 1160))
    _graphic(src, out, s, e, state, paint)


def word_swap(src, out, s, e, cfg):
    """Your captions run across the screen and your pictures replace the key word right in the line."""
    from PIL import ImageDraw
    pics = _pics(cfg)
    rows = _sentences(cfg, 6)
    big = [max(range(len(r)), key=lambda i: len(r[i]["w"].strip(" ,.!?"))) for r in rows]

    def state(t):
        for i, r in enumerate(rows):
            end = rows[i + 1][0]["t"] if i + 1 < len(rows) else r[-1]["e"] + 0.5
            if r[0]["t"] - 0.05 <= t < end:
                return (i, sum(1 for w in r if w["t"] <= t))
        return None

    def paint(img, key):
        i, n = key
        d = ImageDraw.Draw(img)
        f = _font(cfg["font"], 60)
        x, y = 70, 1240
        for k, w in enumerate(rows[i][:n]):
            word = w["w"].strip()
            if k == big[i]:
                if x + 240 > 1010:
                    x, y = 70, y + 170
                img.alpha_composite(_card(pics[i % len(pics)], (220, 150), 18), (x, y - 40))
                x += 240
                continue
            ww = f.getbbox(word + " ")[2]
            if x + ww > 1010:
                x, y = 70, y + 170
            d.text((x, y), word, font=f, fill=(255, 255, 255, 255), stroke_width=3, stroke_fill=(0, 0, 0, 220))
            x += ww
    _graphic(src, out, s, e, state, paint)


def phase_reel(src, out, s, e, cfg):
    """Your video moves through phases: a glowing hook, one big word at a time, black and white, then flip cards."""
    from PIL import ImageDraw
    rgb = _bright(_rgb(cfg))
    said = cfg.get("said") or []
    total = max(1.0, float(e))
    cut = [total * x for x in (0.18, 0.45, 0.72)]

    def state(t):
        now = [w for w in said if w["t"] <= t]
        word = now[-1]["w"].strip(" ,.!?").upper() if now else ""
        if t < cut[0]:
            return (0, " ".join(w["w"].strip(" ,.!?") for w in said[:5]).upper())
        if t < cut[1]:
            return (1, word)
        if t < cut[2]:
            return (2, word)
        return (3, word, int(t / 0.9) % 2)

    def paint(img, key):
        d = ImageDraw.Draw(img)
        if key[0] == 0:
            f = _font(cfg["font"], 110)
            y = 1200
            for x in _wrap(key[1], f, 980)[:3]:
                y += _center(d, x, f, y, (255, 255, 255, 255), stroke_width=5, stroke_fill=rgb + (255,)) + 18
        elif key[0] == 1:
            _center(d, key[1], _fit(cfg["font"], key[1] or " ", 960, 190, 70), 1300, (255, 255, 255, 255), stroke_width=5, stroke_fill=(0, 0, 0, 220))
        elif key[0] == 2:
            _center(d, key[1].lower(), _fit(_serif(cfg), key[1] or " ", 960, 170, 70), 1320, (255, 255, 255, 255))
        else:
            back, ink = ((6, 6, 8), (255, 255, 255)) if key[2] else ((255, 255, 255), rgb)
            d.rectangle((0, 1040, 1080, 1920), fill=back + (255,))
            _center(d, key[1], _fit(cfg["font"], key[1] or " ", 960, 190, 70), 1400, ink + (255,))
    _graphic(src, out, s, e, state, paint, gray=lambda t: cut[1] <= t < cut[2])


def logo_spot(src, out, s, e, cfg):
    """You alternate with a full screen spotlight on one logo or picture, tinted in your color."""
    from PIL import Image, ImageDraw, ImageFilter, ImageOps
    pics = _pics(cfg)
    rgb = _rgb(cfg)
    items = _items(cfg, 14)

    def state(t):
        for i, it in enumerate(items):
            if i % 2 == 0 and it["t"] <= t < it["t"] + 1.3:
                return i
        return None

    def paint(img, i):
        d = ImageDraw.Draw(img)
        d.rectangle((0, 0, 1080, 1920), fill=(5, 6, 10, 255))
        glow = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(glow).ellipse((90, 460, 990, 1360), fill=rgb + (200,))
        img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(120)))
        img.alpha_composite(_card(pics[(i // 2) % len(pics)], (520, 520), 60), (280, 650))
        word = items[i]["w"].upper()
        _center(ImageDraw.Draw(img), word, _fit(cfg["font"], word, 900, 90, 40), 1290, (255, 255, 255, 255))
    _graphic(src, out, s, e, state, paint)


def split_steps(src, out, s, e, cfg):
    """Your whole face up top and a diagram below that draws itself, box by box, with your key words and what you're saying."""
    from PIL import ImageDraw
    rgb = _bright(_rgb(cfg))
    items = _items(cfg, 6)
    rows, row_at = _caption_rows(cfg)
    move = _aim(_head(src, s, e), 40, 960)

    def state(t):
        return (sum(1 for it in items if it["t"] <= t), row_at(t))

    def paint(img, key):
        n, c = key
        d = ImageDraw.Draw(img)
        d.rectangle((0, 1000, 1080, 1920), fill=(7, 9, 16, 255))
        _caption(d, cfg, rows, c, 1040, 60)
        spots = [(70, 1150), (580, 1150), (70, 1380), (580, 1380), (70, 1610), (580, 1610)]
        for i in range(min(n, len(items))):
            x, y = spots[i]
            if i:
                px, py = spots[i - 1]
                d.line((px + 215, py + 85, x + 215, y + 85), fill=rgb + (255,), width=6)
        for i in range(min(n, len(items))):
            x, y = spots[i]
            d.rounded_rectangle((x, y, x + 430, y + 170), 24, fill=rgb + (255,))
            word = items[i]["w"].strip(" ,.!?").upper()
            f = _fit(cfg["font"], word, 390, 52, 28)
            box = f.getbbox(word)
            d.text((x + 215 - (box[2] + box[0]) // 2, y + 85 - (box[3] + box[1]) // 2), word, font=f, fill=_on(rgb) + (255,))
    _graphic(src, out, s, e, state, paint, move=move)


def business_rotate(src, out, s, e, cfg):
    """Rotates full screen, split with a step label, and a full screen word card, with a text hook up top."""
    from PIL import ImageDraw
    rgb = _rgb(cfg)
    items = _items(cfg, 16)
    hook = _title(cfg, "Watch this")

    def state(t):
        i = _now(items, t)
        return (-1 if i is None else i, t < 3.5)

    def paint(img, key):
        i, top = key
        d = ImageDraw.Draw(img)
        if i >= 0 and i % 3 == 1:
            d.rectangle((0, 1160, 1080, 1920), fill=(8, 9, 15, 255))
            _tag(d, f"Step {i // 3 + 1}", _font(cfg["font"], 42), rgb, 1210)
            word = items[i]["w"].upper()
            _center(d, word, _fit(cfg["font"], word, 960, 170, 60), 1400, (255, 255, 255, 255))
        elif i >= 0 and i % 3 == 2:
            d.rectangle((0, 0, 1080, 1920), fill=rgb + (255,))
            word = items[i]["w"].upper()
            _center(d, word, _fit(cfg["font"], word, 960, 190, 60), 880, _on(rgb) + (255,))
        if top and not (i >= 0 and i % 3 == 2):
            _tag(d, hook, _fit(cfg["font"], hook, 880, 62, 34), (255, 255, 255), 150)
    _graphic(src, out, s, e, state, paint)


def fast_personal(src, out, s, e, cfg):
    """A fast personal reel: your own pictures flash on the cuts with one word captions."""
    from PIL import Image, ImageDraw, ImageOps
    pics = _pics(cfg)
    said = cfg.get("said") or []
    at = _moments(cfg, 1, 14)

    def state(t):
        now = [w for w in said if w["t"] <= t < w["e"] + 0.2]
        word = now[-1]["w"].strip(" ,.!?") if now else ""
        shot = next((i for i, a in enumerate(at) if a <= t < a + 0.9), None)
        return (word, shot)

    def paint(img, key):
        word, shot = key
        if shot is not None:
            img.paste(ImageOps.fit(pics[shot % len(pics)], (1080, 1920), Image.LANCZOS, centering=(0.5, 0.18)).convert("RGBA"), (0, 0))
        if word:
            _center(ImageDraw.Draw(img), word, _font(cfg["font"], 92), 1300, (255, 255, 255, 255), stroke_width=4, stroke_fill=(0, 0, 0, 220))
    _graphic(src, out, s, e, state, paint)


class _Clips:
    """Their extra videos, read frame by frame next to the main one, looping if one runs out."""

    def __init__(self, cfg):
        import cv2
        self.cv2 = cv2
        self.caps = [cv2.VideoCapture(x) for x in cfg.get("clips") or []]
        if not self.caps:
            raise RuntimeError("This edit needs your other video.")
        self.last = [None] * len(self.caps)

    def frame(self, i, size):
        import numpy as np
        i %= len(self.caps)
        ok, fr = self.caps[i].read()
        if not ok:
            self.caps[i].set(self.cv2.CAP_PROP_POS_FRAMES, 0)
            ok, fr = self.caps[i].read()
        if ok:
            self.last[i] = fr
        fr = self.last[i]
        w, h = size
        fh, fw = fr.shape[:2]
        scale = max(w / fw, h / fh)
        big = self.cv2.resize(fr, (int(fw * scale) + 1, int(fh * scale) + 1))
        y, x = (big.shape[0] - h) // 2, (big.shape[1] - w) // 2
        return big[y:y + h, x:x + w].astype(np.float32) / 255


def screen_and_you(src, out, s, e, cfg):
    """Your screen recording fills the frame with you in the corner, cutting back to you full screen on some lines."""
    clips = _Clips(cfg)
    at = _moments(cfg, 1, 14)

    def draw(k, t, fr, a):
        beat = sum(1 for m in at if m <= t)
        screen = clips.frame(0, (1080, 1920))
        if beat % 3 == 2:
            return fr
        img = screen.copy()
        small = clips.cv2.resize(fr, (340, 604))
        img[1920 - 604 - 70:1920 - 70, 1080 - 340 - 50:1080 - 50] = small
        return img
    per_frame(src, out, s, e, draw)


def doc_split(src, out, s, e, cfg):
    """Your document or screen on the top half, you on the bottom half, the whole way through."""
    clips = _Clips(cfg)

    def draw(k, t, fr, a):
        img = fr.copy()
        img[:960] = clips.frame(0, (1080, 960))
        img[960:] = clips.cv2.resize(fr, (1080, 1920))[480:1440]
        img[952:968] = 1.0
        return img
    per_frame(src, out, s, e, draw)


def twin_versus(src, out, s, e, cfg):
    """You twice, side by side. Your main video on the left, your other take on the right."""
    clips = _Clips(cfg)

    def draw(k, t, fr, a):
        img = fr.copy()
        img[:, :540] = fr[:, 270:810]
        img[:, 540:] = clips.frame(0, (540, 1920))
        img[:, 534:546] = 1.0
        return img
    per_frame(src, out, s, e, draw)


def two_roles(src, out, s, e, cfg):
    """One person, two roles. The picture cuts between your two takes on every shot change."""
    clips = _Clips(cfg)
    at = _moments(cfg, 1, 14)

    def draw(k, t, fr, a):
        other = clips.frame(0, (1080, 1920))
        return other if sum(1 for m in at if m <= t) % 2 else fr
    per_frame(src, out, s, e, draw)


def day_reel(src, out, s, e, cfg):
    """Your clips play over your voice in order, changing on every shot change, like a day in your life."""
    clips = _Clips(cfg)
    at = _moments(cfg, 1, 14)

    def draw(k, t, fr, a):
        beat = sum(1 for m in at if m <= t)
        return clips.frame(beat, (1080, 1920)) if beat else fr
    per_frame(src, out, s, e, draw)


def screen_karaoke(src, out, s, e, cfg):
    """Big words over your screen recording, lighting up word by word as you say them."""
    from PIL import ImageDraw
    rgb = _rgb(cfg)
    rows = _sentences(cfg, 5)

    def state(t):
        for i, r in enumerate(rows):
            end = rows[i + 1][0]["t"] if i + 1 < len(rows) else r[-1]["e"] + 0.5
            if r[0]["t"] - 0.05 <= t < end:
                return (i, sum(1 for w in r if w["t"] <= t))
        return None

    def paint(img, key):
        i, n = key
        d = ImageDraw.Draw(img)
        f = _font(cfg["font"], 74)
        d.rounded_rectangle((40, 1400, 1040, 1830), 30, fill=(6, 8, 14, 235))
        x, y = 80, 1450
        for k, w in enumerate(rows[i]):
            word = w["w"].strip().upper()
            ww = f.getbbox(word + " ")[2]
            if x + ww > 1010:
                x, y = 80, y + 112
            d.text((x, y), word, font=f, fill=(_bright(rgb) if k == n - 1 else (255, 255, 255) if k < n else (110, 114, 130)) + (255,))
            x += ww
    _graphic(src, out, s, e, state, paint)


def big_screen_caps(src, out, s, e, cfg):
    """Big one-line captions on a solid bar, made so they read clearly on top of a screen recording."""
    from PIL import ImageDraw
    rgb = _rgb(cfg)
    rows = _sentences(cfg, 4)

    def state(t):
        for i, r in enumerate(rows):
            end = rows[i + 1][0]["t"] if i + 1 < len(rows) else r[-1]["e"] + 0.5
            if r[0]["t"] - 0.05 <= t < end:
                return i
        return None

    def paint(img, i):
        d = ImageDraw.Draw(img)
        line = " ".join(w["w"].strip() for w in rows[i])
        f = _fit(cfg["font"], line, 980, 76, 40)
        d.rectangle((0, 1560, 1080, 1760), fill=rgb + (255,))
        box = f.getbbox(line)
        d.text(((1080 - box[2] + box[0]) // 2 - box[0], 1660 - (box[3] - box[1]) // 2 - box[1]), line, font=f, fill=_on(rgb) + (255,))
    _graphic(src, out, s, e, state, paint)


def split_kinetic(src, out, s, e, cfg):
    """Your video up top. On the bottom half, your words slam in big and stack as you say them."""
    from PIL import ImageDraw
    rgb = _bright(_rgb(cfg))
    rows = _sentences(cfg, 4)
    move = _aim(_head(src, s, e), 40, 980)

    def state(t):
        for i, r in enumerate(rows):
            end = rows[i + 1][0]["t"] if i + 1 < len(rows) else r[-1]["e"] + 0.5
            if r[0]["t"] - 0.05 <= t < end:
                return (i, sum(1 for w in r if w["t"] <= t))
        return None

    def paint(img, key):
        i, n = key
        d = ImageDraw.Draw(img)
        d.rectangle((0, 1020, 1080, 1920), fill=(6, 7, 11, 255))
        y = 1080
        for k, w in enumerate(rows[i][:n]):
            word = w["w"].strip(" ,.!?").upper()
            y += _center(d, word, _fit(cfg["font"], word, 980, 180, 70), y, (rgb if k == n - 1 else (255, 255, 255)) + (255,)) + 26
    _graphic(src, out, s, e, state, paint, move=move)


def tool_cards(src, out, s, e, cfg):
    """Each tool you name pops up as a clean card with its name. Add a logo for each one if you want."""
    from PIL import ImageDraw
    pics = [] if not cfg.get("pictures") else _pics(cfg)
    rgb = _rgb(cfg)
    items = _items(cfg, 12)

    def state(t):
        i = _now(items, t)
        return i if i is not None and t < items[i]["t"] + 1.8 else None

    def paint(img, i):
        d = ImageDraw.Draw(img)
        d.rounded_rectangle((140, 1160, 940, 1400), 34, fill=(255, 255, 255, 255), outline=rgb + (255,), width=6)
        word = items[i]["w"]
        if pics:
            img.alpha_composite(_card(pics[i % len(pics)], (160, 160), 26), (180, 1200))
        f = _fit(cfg["font"], word, 500 if pics else 720, 90, 36)
        box = f.getbbox(word)
        x = 370 if pics else (1080 - box[2] + box[0]) // 2 - box[0]
        d.text((x, 1280 - (box[3] - box[1]) // 2 - box[1]), word, font=f, fill=rgb + (255,))
    _graphic(src, out, s, e, state, paint)


def _wide(src, out, state, paint):
    """Like _graphic, for wide videos: draws at the video's own size, so nothing gets stretched to a phone shape."""
    import cv2
    import numpy as np
    from PIL import Image
    W, H = dims(src)
    W -= W % 2
    H -= H % 2
    with tempfile.TemporaryDirectory(prefix="wide_") as work:
        cap = cv2.VideoCapture(src)
        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        raw = os.path.join(work, "raw.mp4")
        wr = cv2.VideoWriter(raw, cv2.VideoWriter_fourcc(*"mp4v"), fps, (W, H))
        cache, k = {}, 0
        while True:
            ok, fr = cap.read()
            if not ok:
                break
            fr = cv2.resize(fr, (W, H)).astype(np.float32) / 255
            key = state(k / fps)
            if key is not None:
                if key not in cache:
                    if len(cache) > 40:
                        cache.clear()
                    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
                    paint(img, key, W, H)
                    arr = np.asarray(img, dtype=np.float32) / 255
                    cache[key] = (arr[..., 2::-1].copy(), arr[..., 3:4].copy())
                rgb, al = cache[key]
                fr = fr * (1 - al) + rgb * al
            wr.write((fr * 255).clip(0, 255).astype(np.uint8))
            k += 1
        wr.release()
        cap.release()
        run([FF, "-v", "error", "-i", raw, "-i", src, "-map", "0:v", "-map", "1:a?", "-c:v", "libx264", "-crf", "17", "-preset", "fast",
             "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-y", out])


def _wide_caps(d, cfg, groups, g, W, H, u):
    if g is None:
        return
    line = " ".join(w["w"].strip() for w in groups[g])
    f = _fit(_plain(cfg), line, int(W * 0.82), int(46 * u), 20)
    box = f.getbbox(line)
    pad = int(14 * u)
    x, y = (W - box[2]) // 2, int(H * 0.875)
    d.rounded_rectangle((x - pad * 2, y - pad, x + box[2] + pad * 2, y + box[3] + pad), int(12 * u), fill=(0, 0, 0, 205))
    d.text((x, y), line, font=f, fill=(255, 255, 255, 255))


def _groups(cfg, n=7):
    said = cfg.get("said") or []
    return [said[i:i + n] for i in range(0, len(said), n)]


def _group_at(groups, t):
    for i, x in enumerate(groups):
        end = groups[i + 1][0]["t"] if i + 1 < len(groups) else x[-1]["e"] + 0.5
        if x[0]["t"] - 0.05 <= t < end:
            return i
    return None


def wide_minimal(src, out, s, e, cfg):
    """A clean wide YouTube edit: tight cuts, a simple title on the opening and small captions."""
    from PIL import ImageDraw
    groups = _groups(cfg)
    title = _title(cfg, "Watch this")

    def state(t):
        return (_group_at(groups, t), t < 4)

    def paint(img, key, W, H):
        g, top = key
        u = W / 1920
        d = ImageDraw.Draw(img)
        if top:
            f = _fit(cfg["font"], title, int(W * 0.8), int(70 * u), 24)
            d.text((int(70 * u), int(60 * u)), title, font=f, fill=(255, 255, 255, 255), stroke_width=int(3 * u) + 1, stroke_fill=(0, 0, 0, 220))
        _wide_caps(d, cfg, groups, g, W, H, u)
    _wide(src, out, state, paint)


def wide_lesson(src, out, s, e, cfg):
    """A wide lesson: captions the whole way, with a clean side card when you land on a key idea."""
    from PIL import ImageDraw
    rgb = _rgb(cfg)
    groups = _groups(cfg)
    items = _items(cfg, 16)

    def state(t):
        i = _now(items, t)
        return (_group_at(groups, t), i if i is not None and t < items[i]["t"] + 2.2 else None)

    def paint(img, key, W, H):
        g, i = key
        u = W / 1920
        d = ImageDraw.Draw(img)
        if i is not None:
            word = items[i]["w"]
            f = _fit(cfg["font"], word, int(520 * u), int(70 * u), 22)
            x0, y0, x1, y1 = int(W - 620 * u), int(90 * u), int(W - 50 * u), int(290 * u)
            d.rounded_rectangle((x0, y0, x1, y1), int(26 * u), fill=rgb + (255,))
            box = f.getbbox(word)
            d.text(((x0 + x1 - box[2]) // 2, (y0 + y1 - box[3]) // 2), word, font=f, fill=_on(rgb) + (255,))
        _wide_caps(d, cfg, groups, g, W, H, u)
    _wide(src, out, state, paint)


def wide_tips(src, out, s, e, cfg):
    """A wide list video: a chapter marker for each point and a progress bar along the bottom."""
    from PIL import ImageDraw
    rgb = _bright(_rgb(cfg))
    groups = _groups(cfg)
    items = _items(cfg, 12)

    def state(t):
        return (_group_at(groups, t), _now(items, t))

    def paint(img, key, W, H):
        g, i = key
        u = W / 1920
        d = ImageDraw.Draw(img)
        if i is not None:
            f = _font(cfg["font"], int(44 * u))
            label = f"{i + 1}. {items[i]['w']}"
            d.rounded_rectangle((int(50 * u), int(50 * u), int(50 * u) + f.getbbox(label)[2] + int(60 * u), int(140 * u)), int(18 * u), fill=(6, 8, 14, 220), outline=rgb + (255,), width=int(4 * u) + 1)
            d.text((int(80 * u), int(70 * u)), label, font=f, fill=(255, 255, 255, 255))
        step = W / max(1, len(items))
        for k in range(len(items)):
            on = i is not None and k <= i
            d.rectangle((int(k * step) + 3, H - int(14 * u), int((k + 1) * step) - 3, H), fill=(rgb if on else (255, 255, 255)) + (255 if on else 90,))
        _wide_caps(d, cfg, groups, g, W, H, u)
    _wide(src, out, state, paint)


def wide_steps(src, out, s, e, cfg):
    """A wide lesson: step titles on a glowing black screen cut in between your teaching."""
    from PIL import Image, ImageDraw, ImageFilter
    rgb = _bright(_rgb(cfg))
    groups = _groups(cfg)
    items = _items(cfg, 12)

    def state(t):
        for i, it in enumerate(items):
            if i % 2 == 0 and it["t"] <= t < it["t"] + 1.2:
                return ("card", i // 2 + 1, it["w"])
        return ("talk", _group_at(groups, t))

    def paint(img, key, W, H):
        u = W / 1920
        d = ImageDraw.Draw(img)
        if key[0] == "talk":
            _wide_caps(d, cfg, groups, key[1], W, H, u)
            return
        d.rectangle((0, 0, W, H), fill=(4, 4, 7, 255))
        glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(glow).ellipse((W // 4, H // 5, W * 3 // 4, H * 4 // 5), fill=rgb + (130,))
        img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(int(120 * u))))
        d = ImageDraw.Draw(img)
        small = _font(_plain(cfg), int(44 * u))
        tag = f"Step {key[1]}"
        d.text(((W - small.getbbox(tag)[2]) // 2, int(H * 0.34)), tag, font=small, fill=rgb + (255,))
        f = _fit(_serif(cfg), key[2], int(W * 0.8), int(170 * u), 40)
        d.text(((W - f.getbbox(key[2])[2]) // 2, int(H * 0.44)), key[2], font=f, fill=(255, 255, 255, 255))
    _wide(src, out, state, paint)


def wide_board(src, out, s, e, cfg):
    """A soft teaching video: an agenda fills in on a clean white board beside you."""
    from PIL import ImageDraw
    rgb = _rgb(cfg)
    groups = _groups(cfg)
    items = _items(cfg, 6)

    def state(t):
        return (_group_at(groups, t), sum(1 for it in items if it["t"] <= t))

    def paint(img, key, W, H):
        g, n = key
        u = W / 1920
        d = ImageDraw.Draw(img)
        x0, y0, x1, y1 = int(W - 700 * u), int(70 * u), int(W - 50 * u), int(H - 200 * u)
        d.rounded_rectangle((x0, y0, x1, y1), int(22 * u), fill=(250, 250, 247, 255), outline=(40, 44, 60, 255), width=int(4 * u) + 1)
        head = _font(_serif(cfg), int(60 * u))
        d.text((x0 + int(40 * u), y0 + int(30 * u)), "Today", font=head, fill=(20, 22, 30, 255))
        f = _fit(_plain(cfg), "WWWWWWWWWWWWWW", int(560 * u), int(46 * u), 18)
        for k in range(min(n, len(items))):
            y = y0 + int((130 + k * 92) * u)
            d.ellipse((x0 + int(44 * u), y + int(14 * u), x0 + int(66 * u), y + int(36 * u)), fill=rgb + (255,))
            d.text((x0 + int(84 * u), y), items[k]["w"][:18], font=f, fill=(20, 22, 30, 255))
        _wide_caps(d, cfg, groups, g, W, H, u)
    _wide(src, out, state, paint)


def phone_peek(src, out, s, e, cfg):
    """2026-11-05, from a reel Tiff sent: a small phone pops up in a top corner showing one of your pictures,
    a new picture and the other corner on every shot change, while you keep talking full screen."""
    from PIL import Image, ImageDraw
    pics = _pics(cfg)
    rgb = _rgb(cfg)
    at = [0.0] + [float(m) for m in (cfg.get("moments") or [])]
    W, H, R = 300, 600, 44

    def state(t):
        i = _at_beat(cfg, t)
        return (i, min(6, int((t - at[min(i, len(at) - 1)]) / 0.033)))

    def paint(img, key):
        i, step = key
        ph = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(ph)
        d.rounded_rectangle((0, 0, W - 1, H - 1), R, fill=(12, 12, 14, 255), outline=rgb + (255,), width=5)
        ph.alpha_composite(_card(pics[i % len(pics)], (W - 24, H - 24), R - 12), (12, 12))
        d.rounded_rectangle((W // 2 - 46, 22, W // 2 + 46, 46), 12, fill=(12, 12, 14, 255))
        sc = 0.55 + 0.45 * _ease_out(step / 6)
        ph = ph.resize((max(1, int(W * sc)), max(1, int(H * sc))), Image.LANCZOS)
        ph = ph.rotate(-6 if i % 2 else 6, expand=True, resample=Image.BICUBIC)
        x = 1080 - 56 - ph.width if i % 2 else 56
        img.alpha_composite(ph, (x, 120 + int((H - ph.height) / 2 * (1 - sc))))
    _graphic(src, out, s, e, state, paint)


def _ease_out(x):
    x = max(0.0, min(1.0, x))
    return 1 - (1 - x) ** 3


def info_cards(src, out, s, e, cfg):
    """2026-11-05, from a reel Tiff sent: a clean white card with a header bar in your color drops in up top on
    each key word. The header is the words you said leading up to it, the big line is the key word itself.
    Nothing on a card is made up: every word on it was said, or typed by you."""
    from PIL import Image, ImageDraw
    rgb = _rgb(cfg)
    items = _items(cfg, 10)
    if not items:
        raise RuntimeError("Info Cards needs a few key words. Try a video that's at least 5 seconds.")
    said = [{"w": str(w["w"]).strip(), "t": float(w["t"])} for w in (cfg.get("said") or [])]

    def lead(t):
        before = [w["w"] for w in said if w["t"] < t - 0.01][-6:]
        cut = max([k for k, w in enumerate(before) if w.endswith((".", "!", "?"))] or [-1])
        words = [w.strip(" ,.!?\"").upper() for w in before[cut + 1:]][-4:]
        return " ".join(x for x in words if x) or str(cfg.get("brand_name") or "").upper()[:28]

    heads = [lead(it["t"]) for it in items]

    def state(t):
        i = _now(items, t)
        if i is None:
            return None
        end = min(items[i]["t"] + 2.4, items[i + 1]["t"] if i + 1 < len(items) else 1e9)
        if t >= end:
            return None
        return (i, min(6, int((t - items[i]["t"]) / 0.033)))

    def paint(img, key):
        i, step = key
        word = items[i]["w"].strip(" ,.!?\"").upper()
        head = heads[i][:30]
        cw, ch = 760, 300
        card = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
        d = ImageDraw.Draw(card)
        d.rounded_rectangle((0, 0, cw - 1, ch - 1), 26, fill=(250, 248, 242, 255))
        d.rounded_rectangle((0, 0, cw - 1, 74), 26, fill=rgb + (255,))
        d.rectangle((0, 48, cw - 1, 74), fill=rgb + (255,))
        if head:
            hf = _fit(cfg["font"], head, cw - 64, 34, 22)
            hb = hf.getbbox(head)
            d.text((32 - hb[0], 37 - (hb[3] + hb[1]) // 2), head, font=hf, fill=_on(rgb) + (255,))
        bf = _fit(cfg["font"], word, cw - 80, 120, 48)
        bb = bf.getbbox(word)
        d.text((40 - bb[0], 74 + (ch - 74 - (bb[3] - bb[1])) // 2 - bb[1]), word, font=bf, fill=(18, 18, 22, 255))
        sh = Image.new("RGBA", (cw + 40, ch + 40), (0, 0, 0, 0))
        ImageDraw.Draw(sh).rounded_rectangle((20, 26, cw + 20, ch + 26), 26, fill=(0, 0, 0, 90))
        k = _ease_out(step / 6)
        x, y = (1080 - cw) // 2, 110 - int(60 * (1 - k))
        img.alpha_composite(sh, (x - 20, y - 20))
        img.alpha_composite(card, (x, y))
        if k < 1:
            a = img.getchannel("A").point(lambda v: int(v * (0.25 + 0.75 * k)))
            img.putalpha(a)
    _graphic(src, out, s, e, state, paint)


MORE_EFFECTS = {"lights-on": lights_on, "screen-wipe": screen_wipe, "shutter-strike": shutter_strike, "zoom-through": zoom_through,
                "pull-back": pull_back, "whip-cut": whip_cut, "flash-cut": flash_cut, "black-white-beats": black_white_beats,
                "big-type": big_type, "glow-stack": glow_stack, "flip-cards": flip_cards, "tier-list": tier_list, "top-five": top_five,
                "always-never": always_never, "numbered-list": numbered_list, "mono-story": mono_story, "explainer-panel": explainer_panel,
                "picture-under": picture_under, "picture-above": picture_above, "photo-split": photo_split, "photo-world": photo_world, "testimonial-wall": testimonial_wall,
                "photo-grid": photo_grid, "float-up": float_up, "photo-cluster": photo_cluster, "behind-you": behind_you,
                "ear-to-ear": ear_to_ear, "fitted-stack": fitted_stack, "if-then": if_then, "quadrant": quadrant, "cinema-type": cinema_type,
                "line-by-line": line_by_line, "short-box": short_box, "voice-note": voice_note, "headline-wall": headline_wall,
                "cover-story": cover_story, "paper-cut": paper_cut, "vertigo": vertigo,
                "growth-chart": growth_chart, "glass-graph": glass_graph, "wall-words": wall_words, "glass-words": glass_words, "glass-panel": glass_panel,
                "match-cut": match_cut, "shoulder-push": shoulder_push, "screen-slide": screen_slide, "screen-zoom": screen_zoom, "end-stack": end_stack,
                "app-world": app_world, "picture-stack": picture_stack, "story-room": story_room, "then-and-now": then_and_now, "proof-above": proof_above,
                "word-morph": word_morph, "word-swap": word_swap, "phase-reel": phase_reel, "logo-spot": logo_spot,
                "split-steps": split_steps, "business-rotate": business_rotate, "fast-personal": fast_personal,
                "screen-and-you": screen_and_you, "doc-split": doc_split, "twin-versus": twin_versus, "two-roles": two_roles, "day-reel": day_reel,
                "screen-karaoke": screen_karaoke, "big-screen-caps": big_screen_caps, "split-kinetic": split_kinetic, "tool-cards": tool_cards,
                "wide-minimal": wide_minimal, "wide-lesson": wide_lesson, "wide-tips": wide_tips, "wide-steps": wide_steps, "wide-board": wide_board, "phone-peek": phone_peek, "info-cards": info_cards}


def number_pop(src, out, s, e, cfg):
    """A number they say counts up big in their color, bounces in, then sits above their head."""
    n = float(cfg.get("number", 0) or 0)
    pre, suf = esc(cfg.get("prefix", "")), esc(cfg.get("suffix", ""))
    label = esc(cfg.get("label", ""))
    whole = n == int(n)
    count = (f"%{{eif\\:min({n}\\,{n}*(t-{s})/0.9)\\:d}}" if whole else
             f"%{{eif\\:min({n * 10}\\,{n * 10}*(t-{s})/0.9)/10\\:d}}")
    size = f"if(lt(t-{s},0.25),80+190*(t-{s})/0.25,if(lt(t-{s},0.4),270-30*(t-{s}-0.25)/0.15,240))"
    col = cfg.get("accent", "#00A6FF").lstrip("#")
    fnt = cfg["font"].replace(":", "\\:")
    on = f"between(t,{s},{e})"
    final = esc(cfg.get("prefix", "") + (f"{int(n):,}" if whole else f"{n:,.1f}") + cfg.get("suffix", ""))
    look = (f"fontcolor=0x{col}:borderw=10:bordercolor=black@0.55:shadowx=0:shadowy=8:shadowcolor=black@0.35:x=(w-text_w)/2:y=h*0.13")
    # counts up for 0.9 s, then lands on the real number with its commas ("$5,000")
    vf = (f"drawtext=fontfile='{fnt}':text='{pre}{count}{suf}':fontsize='{size}':{look}:enable='between(t,{s},{s + 0.9})',"
          f"drawtext=fontfile='{fnt}':text='{final}':fontsize='{size}':{look}:enable='between(t,{s + 0.9},{e})'")
    if label:
        vf += (f",drawtext=fontfile='{fnt}':text='{label}':fontsize=64:fontcolor=white:borderw=6:bordercolor=black@0.55:"
               f"x=(w-text_w)/2:y=h*0.13+270:enable='between(t,{s + 0.35},{e})'")
    run([FF, "-v", "error", "-i", src, "-vf", vf, "-c:v", "libx264", "-crf", "17", "-preset", "fast",
         "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", "-y", out])


def checklist(src, out, s, e, cfg):
    """A clean card lists the steps; each one ticks off as they say it."""
    from PIL import Image, ImageDraw
    items = [i for i in cfg.get("items", []) if str(i.get("text", "")).strip()][:4] or [{"text": "Step one", "at": s}]
    acc = rgb(cfg.get("accent", "#00A6FF"))
    W, pad, rowh = 900, 44, 118
    H = pad * 2 + rowh * len(items) + 70
    f_item, f_head = font_for(cfg, 52), font_for(cfg, 40)
    work = tempfile.mkdtemp(prefix="myfx_")
    ins, chain, last = ["-i", src], "[0:v]", "0:v"
    for k in range(len(items) + 1):          # card with 0, 1, 2 ... ticks done
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([0, 0, W - 1, H - 1], radius=40, fill=(255, 255, 255, 240))
        d.rounded_rectangle([0, 0, W - 1, 18], radius=9, fill=acc + (255,))
        d.text((pad, pad - 4), str(cfg.get("title", "THE STEPS")).upper()[:28], font=f_head, fill=acc + (255,))
        for i, it in enumerate(items):
            y = pad + 70 + i * rowh
            done = i < k
            cx, cy, r = pad + 34, y + 38, 30
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=acc + (255,) if done else (232, 238, 248, 255))
            if done:
                d.line([(cx - 14, cy), (cx - 3, cy + 12), (cx + 16, cy - 12)], fill=(255, 255, 255, 255), width=8)
            txt = str(it["text"])[:30]
            d.text((pad + 90, y + 6), txt, font=f_item, fill=(6, 21, 61, 255) if done else (90, 107, 140, 255))
        p = os.path.join(work, f"c{k}.png")
        img.save(p)
        ins += ["-loop", "1", "-i", p]
    times = [s] + [max(s, min(e, float(it.get("at", s)))) for it in items] + [e]
    filt = []
    for k in range(len(items) + 1):
        a, b = times[k], times[k + 1] if k < len(items) else e
        if k < len(items):
            b = times[k + 1]
        nxt = f"v{k}"
        filt.append(f"[{last}][{k + 1}:v]overlay=x=(W-w)/2:y=H*0.11:shortest=1:enable='between(t,{a},{b})'[{nxt}]")
        last = nxt
    run([FF, "-v", "error", *ins, "-filter_complex", ";".join(filt), "-map", f"[{last}]", "-map", "0:a?",
         "-t", str(probe_secs(src)), "-c:v", "libx264", "-crf", "17", "-preset", "fast", "-pix_fmt", "yuv420p",
         "-c:a", "copy", "-movflags", "+faststart", "-y", out])
    shutil.rmtree(work, ignore_errors=True)


def headline_behind(src, out, s, e, cfg):
    """Their key words in huge letters BEHIND them: the person is cut out (open-source matting) and
    stands in front of the words."""
    import cv2, numpy as np, onnxruntime as ort
    from PIL import Image, ImageDraw
    if not os.path.exists(RVM):
        os.makedirs(os.path.dirname(RVM), exist_ok=True)
        run(["curl", "-sL", "-o", RVM, RVM_URL])
    sess = ort.InferenceSession(RVM, providers=["CPUExecutionProvider"])
    words = str(cfg.get("headline", "")).upper().split()[:4] or ["THIS"]
    acc = rgb(cfg.get("accent", "#00A6FF"))
    W, H = 1080, 1920
    W0, H0 = W, H
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    # up to 2 lines, as big as fits, high in the frame so it reads around their head
    lines = [" ".join(words)] if len(words) <= 2 else [" ".join(words[:len(words) // 2]), " ".join(words[len(words) // 2:])]
    size = 260
    while size > 90:
        f = font_for(cfg, size)
        if max(d.textlength(l, font=f) for l in lines) <= W * 0.94:
            break
        size -= 8
    f = font_for(cfg, size)
    y = int(H * 0.05)
    for i, l in enumerate(lines):
        x = (W - d.textlength(l, font=f)) / 2
        d.text((x, y), l, font=f, fill=acc + (255,) if i == len(lines) - 1 else (255, 255, 255, 255),
               stroke_width=6, stroke_fill=(0, 0, 0, 120))
        y += int(size * 1.0)
    text = np.array(layer).astype(np.float32) / 255.0
    work = tempfile.mkdtemp(prefix="myfx_")
    seg = os.path.join(work, "seg.mp4")
    cap = cv2.VideoCapture(src)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(round(s * fps)))
    n = int(round((e - s) * fps))
    wr = cv2.VideoWriter(os.path.join(work, "raw.mp4"), cv2.VideoWriter_fourcc(*"mp4v"), fps, (W0, H0))
    rec = [np.zeros((1, 1, 1, 1), np.float32)] * 4
    ratio = np.array([0.25], np.float32)
    for k in range(n):
        ok, fr = cap.read()
        if not ok:
            break
        fr = cv2.resize(fr, (W, H))
        x = cv2.cvtColor(fr, cv2.COLOR_BGR2RGB).astype(np.float32).transpose(2, 0, 1)[None] / 255.0
        _, pha, *rec = sess.run(None, {"src": x, "r1i": rec[0], "r2i": rec[1], "r3i": rec[2], "r4i": rec[3], "downsample_ratio": ratio})
        a = pha[0, 0][..., None]
        appear = min(1.0, k / (0.3 * fps))     # words slide up and fade in over 0.3 s
        shift = int((1 - appear) * 80)
        t = np.roll(text, -shift, axis=0) if shift else text
        ta = t[..., 3:4] * appear
        base = fr.astype(np.float32) / 255.0
        bg = base * (1 - ta) + t[..., [2, 1, 0]] * ta
        comp = bg * (1 - a) + base * a
        wr.write((comp * 255).clip(0, 255).astype(np.uint8))
    wr.release(); cap.release()
    run([FF, "-v", "error", "-i", os.path.join(work, "raw.mp4"), "-c:v", "libx264", "-crf", "16", "-preset", "fast",
         "-pix_fmt", "yuv420p", "-y", seg])
    run([FF, "-v", "error", "-i", src, "-i", seg, "-filter_complex",
         f"[1:v]setpts=PTS-STARTPTS+{s}/TB[fx];[0:v][fx]overlay=eof_action=pass:enable='between(t,{s},{e})'[v]",
         "-map", "[v]", "-map", "0:a?", "-c:v", "libx264", "-crf", "17", "-preset", "fast", "-pix_fmt", "yuv420p",
         "-c:a", "copy", "-movflags", "+faststart", "-y", out])
    shutil.rmtree(work, ignore_errors=True)


def dims(path):
    fp = shutil.which("ffprobe", path=os.path.expanduser("~/.local/bin")) or shutil.which("ffprobe")
    w, h = subprocess.run([fp, "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0", path],
                          capture_output=True, text=True).stdout.strip().split(",")[:2]
    return int(w), int(h)


def probe_secs(path):
    fp = shutil.which("ffprobe", path=os.path.expanduser("~/.local/bin")) or shutil.which("ffprobe")
    return float(subprocess.run([fp, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                                capture_output=True, text=True).stdout)


# ---------------------------------------------------------------- batch 2 (2026-10-27)
# Every effect below draws frame by frame between s and e with the same helper, so they all share one way
# of reading, compositing and splicing back. Layers are drawn with Pillow; the cut-out uses the same
# open-source Robust Video Matting model as Headline Behind Me.

def ease(x):
    x = max(0.0, min(1.0, x))
    return 1 - (1 - x) ** 3


def rgba_layer():
    from PIL import Image
    return Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))


def paste(base, layer, alpha=1.0, dx=0, dy=0):
    """Put an RGBA Pillow layer over a BGR float frame."""
    import numpy as np
    t = np.asarray(layer).astype(np.float32) / 255.0
    if dx or dy:
        t = np.roll(np.roll(t, int(dy), axis=0), int(dx), axis=1)
    a = t[..., 3:4] * alpha
    return base * (1 - a) + t[..., [2, 1, 0]] * a


def per_frame(src, out, s, e, draw, matte=False):
    """Read the frames between s and e, hand each one to draw(k, t, frame, person_alpha), splice the result
    back over the original. Sound untouched."""
    import cv2, numpy as np
    sess = None
    if matte:
        import onnxruntime as ort
        if not os.path.exists(RVM):
            os.makedirs(os.path.dirname(RVM), exist_ok=True)
            run(["curl", "-sL", "-o", RVM, RVM_URL])
        sess = ort.InferenceSession(RVM, providers=["CPUExecutionProvider"])
    W, H = 1080, 1920
    W0, H0 = dims(src)      # drawn at 1080x1920, written back at the source's own size, so the room effects
    work = tempfile.mkdtemp(prefix="myfx_")   # can run BEFORE the captions go on and never smear them
    cap = cv2.VideoCapture(src)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(round(s * fps)))
    n = int(round((e - s) * fps))
    wr = cv2.VideoWriter(os.path.join(work, "raw.mp4"), cv2.VideoWriter_fourcc(*"mp4v"), fps, (W0, H0))
    rec = [np.zeros((1, 1, 1, 1), np.float32)] * 4
    ratio = np.array([0.25], np.float32)
    for k in range(n):
        ok, fr = cap.read()
        if not ok:
            break
        fr = cv2.resize(fr, (W, H))
        a = None
        if sess:
            x = cv2.cvtColor(fr, cv2.COLOR_BGR2RGB).astype(np.float32).transpose(2, 0, 1)[None] / 255.0
            _, pha, *rec = sess.run(None, {"src": x, "r1i": rec[0], "r2i": rec[1], "r3i": rec[2], "r4i": rec[3], "downsample_ratio": ratio})
            a = pha[0, 0][..., None]
        img = draw(k, k / fps, fr.astype(np.float32) / 255.0, a)
        img = (img * 255).clip(0, 255).astype(np.uint8)
        wr.write(img if (W0, H0) == (W, H) else cv2.resize(img, (W0, H0), interpolation=cv2.INTER_AREA))
    wr.release(); cap.release()
    seg = os.path.join(work, "seg.mp4")
    run([FF, "-v", "error", "-i", os.path.join(work, "raw.mp4"), "-c:v", "libx264", "-crf", "16", "-preset", "fast", "-pix_fmt", "yuv420p", "-y", seg])
    run([FF, "-v", "error", "-i", src, "-i", seg, "-filter_complex",
         f"[1:v]setpts=PTS-STARTPTS+{s}/TB[fx];[0:v][fx]overlay=eof_action=pass:enable='between(t,{s},{e})'[v]",
         "-map", "[v]", "-map", "0:a?", "-c:v", "libx264", "-crf", "17", "-preset", "fast", "-pix_fmt", "yuv420p",
         "-c:a", "copy", "-movflags", "+faststart", "-y", out])
    shutil.rmtree(work, ignore_errors=True)


def gradient(cfg):
    """Their color into deep navy, top to bottom: the brand backdrop for several effects."""
    import numpy as np
    acc = np.array(rgb(cfg.get("accent", "#00A6FF"))[::-1], np.float32) / 255.0
    navy = np.array((61, 21, 6), np.float32) / 255.0
    y = np.linspace(0, 1, 1920, dtype=np.float32)[:, None, None]
    g = acc * (1 - y) * 0.85 + navy * (0.15 + y * 0.85)
    return np.repeat(g, 1080, axis=1)


def lower_third(src, out, s, e, cfg):
    """Their name and what they do on a bar that slides in, like TV."""
    from PIL import ImageDraw
    acc = rgb(cfg.get("accent", "#00A6FF"))
    lay = rgba_layer(); d = ImageDraw.Draw(lay)
    name, title = str(cfg.get("name") or "Your Name")[:28], str(cfg.get("title") or "")[:36]
    fn, ft = font_for(cfg, 64), font_for(cfg, 40)
    w = int(max(d.textlength(name, font=fn), d.textlength(title, font=ft)) + 110)
    y = int(1920 * 0.585)
    d.rounded_rectangle([40, y, 40 + w, y + 96], radius=22, fill=acc + (255,))
    d.text((80, y + 14), name, font=fn, fill=(255, 255, 255, 255))
    if title:
        d.rounded_rectangle([40, y + 104, 40 + int(d.textlength(title, font=ft)) + 80, y + 170], radius=18, fill=(6, 21, 61, 235))
        d.text((80, y + 114), title, font=ft, fill=(255, 255, 255, 255))
    L = e - s
    per_frame(src, out, s, e, lambda k, t, fr, a: paste(fr, lay, 1.0, dx=-(1 - ease(t / 0.35)) * (w + 80) if t < 0.35 else
                                                        (-(ease((t - (L - 0.3)) / 0.3)) * (w + 80) if t > L - 0.3 else 0)))


def quote_card(src, out, s, e, cfg):
    """Their own sentence lands on a card, word by word, as they say it."""
    from PIL import ImageDraw
    acc = rgb(cfg.get("accent", "#00A6FF"))
    words = [w for w in cfg.get("words", []) if str(w.get("w", "")).strip()][:18] or [{"w": "Say it like you mean it", "t": s}]
    f = font_for(cfg, 62)
    cache = {}

    def card(n):
        if n not in cache:
            lay = rgba_layer(); d = ImageDraw.Draw(lay)
            lines, cur = [], ""
            for w in [x["w"] for x in words]:
                test = (cur + " " + w).strip()
                if d.textlength(test, font=f) > 1080 * 0.74 and cur:
                    lines.append(cur); cur = w
                else:
                    cur = test
            lines.append(cur)
            h = 110 + 82 * len(lines)
            y0 = int(1920 * 0.1)
            d.rounded_rectangle([70, y0, 1010, y0 + h], radius=36, fill=(255, 255, 255, 242))
            d.text((100, y0 - 40), "“", font=font_for(cfg, 180), fill=acc + (255,))
            shown, y = 0, y0 + 60
            for line in lines:
                x = 120
                for w in line.split():
                    col = (6, 21, 61, 255) if shown < n else (6, 21, 61, 40)
                    d.text((x, y), w, font=f, fill=col)
                    x += d.textlength(w + " ", font=f)
                    shown += 1
                y += 82
            cache[n] = lay
        return cache[n]
    times = [float(w.get("t", s)) - s for w in words]
    per_frame(src, out, s, e, lambda k, t, fr, a: paste(fr, card(sum(1 for x in times if x <= t + 0.05)), ease(t / 0.25)))


def marker_swipe(src, out, s, e, cfg):
    """A key word, big, with a hand-drawn highlighter swiping in behind it."""
    from PIL import ImageDraw
    acc = rgb(cfg.get("accent", "#00A6FF"))
    word = str(cfg.get("headline") or "THIS").upper()[:18]
    lay = rgba_layer(); d = ImageDraw.Draw(lay)
    size = 200
    while size > 80 and d.textlength(word, font=font_for(cfg, size)) > 1080 * 0.86:
        size -= 8
    f = font_for(cfg, size)
    tw = d.textlength(word, font=f)
    x0, y0 = (1080 - tw) / 2, int(1920 * 0.12)
    d.text((x0, y0), word, font=f, fill=(255, 255, 255, 255), stroke_width=5, stroke_fill=(6, 21, 61, 200))

    def mark(p):
        m = rgba_layer(); md = ImageDraw.Draw(m)
        right = x0 - 20 + (tw + 40) * p
        top, bot = y0 + size * 0.45, y0 + size * 1.05
        md.polygon([(x0 - 20, top + 8), (right, top), (right + 6, bot - 4), (x0 - 24, bot)], fill=acc + (215,))
        return m
    marks = [mark(i / 12) for i in range(13)]
    per_frame(src, out, s, e, lambda k, t, fr, a: paste(paste(fr, marks[min(12, int(ease((t - 0.15) / 0.45) * 12))]), lay, ease(t / 0.2)))


def stat_bars(src, out, s, e, cfg):
    """Three bars race up; the tallest lands on their number."""
    from PIL import ImageDraw
    acc = rgb(cfg.get("accent", "#00A6FF"))
    n = float(cfg.get("number", 0) or 0)
    label = cfg.get("prefix", "") + (f"{int(n):,}" if n == int(n) else f"{n:,.1f}") + cfg.get("suffix", "")
    sub = str(cfg.get("label", "") or "")[:22].upper()
    fl, fs = font_for(cfg, 96), font_for(cfg, 40)
    x0, base_y, maxh, bw, gap = 190, int(1920 * 0.42), 520, 170, 70
    heights = [0.32, 0.58, 1.0]

    def frame_layer(p):
        lay = rgba_layer(); d = ImageDraw.Draw(lay)
        d.rounded_rectangle([110, base_y - maxh - 190, 970, base_y + 80], radius=40, fill=(255, 255, 255, 236))
        for i, hf in enumerate(heights):
            q = ease((p - i * 0.12) / 0.7)
            h = maxh * hf * q
            x = x0 + i * (bw + gap)
            col = acc + (255,) if i == 2 else (200, 214, 236, 255)
            d.rounded_rectangle([x, base_y - h, x + bw, base_y], radius=18, fill=col)
        if p > 0.75:
            d.text((540 - d.textlength(label, font=fl) / 2, base_y - maxh - 160), label, font=fl, fill=acc + (255,))
            if sub:
                d.text((540 - d.textlength(sub, font=fs) / 2, base_y + 18), sub, font=fs, fill=(6, 21, 61, 255))
        return lay
    frames = {}
    def get(p):
        q = round(min(1.0, p) * 24) / 24
        if q not in frames:
            frames[q] = frame_layer(q)
        return frames[q]
    per_frame(src, out, s, e, lambda k, t, fr, a: paste(fr, get(t / 1.1)))


def phone_frame(src, out, s, e, cfg):
    """They shrink into a phone on their brand backdrop, with a title above."""
    import cv2, numpy as np
    from PIL import ImageDraw
    bg = gradient(cfg)
    title = str(cfg.get("headline") or "").upper()[:20]
    lay = rgba_layer(); d = ImageDraw.Draw(lay)
    if title:
        f = font_for(cfg, 96)
        d.text((540 - d.textlength(title, font=f) / 2, 120), title, font=f, fill=(255, 255, 255, 255))
    pw, ph = 600, 1066
    px, py = (1080 - pw) // 2, 300
    mask = np.zeros((1920, 1080), np.uint8)
    cv2.rectangle(mask, (0, 0), (1, 1), 0)
    m = rgba_layer(); md = ImageDraw.Draw(m)
    md.rounded_rectangle([px, py, px + pw, py + ph], radius=70, fill=(255, 255, 255, 255))
    screen = np.asarray(m)[..., 3:4].astype(np.float32) / 255.0
    bez = rgba_layer(); bd = ImageDraw.Draw(bez)
    bd.rounded_rectangle([px - 16, py - 16, px + pw + 16, py + ph + 16], radius=84, outline=(6, 21, 61, 255), width=18)
    bd.rounded_rectangle([540 - 70, py + 14, 540 + 70, py + 40], radius=13, fill=(6, 21, 61, 255))

    def draw(k, t, fr, a):
        p = ease(t / 0.35)
        if p < 1:      # zoom out from full screen into the phone
            sc = 1 - (1 - pw / 1080) * p
            w, h = int(1080 * sc), int(1920 * sc)
            small = cv2.resize(fr, (w, h))
            canvas = bg.copy()
            x, y = (1080 - w) // 2, int((1920 - h) / 2 * (1 - p) + (py - (h - ph) / 2) * p)
            y = max(0, min(1920 - h, y))
            canvas[y:y + h, x:x + w] = small
            return canvas
        small = cv2.resize(fr, (pw, int(1920 * pw / 1080)))
        canvas = bg.copy()
        top = py - (small.shape[0] - ph) // 2
        canvas[py:py + ph, px:px + pw] = small[py - top:py - top + ph] if top <= py else small[:ph]
        canvas = bg * (1 - screen) + canvas * screen
        return paste(paste(canvas, bez), lay, ease((t - 0.3) / 0.3))
    per_frame(src, out, s, e, draw)


def brand_backdrop(src, out, s, e, cfg):
    """The room disappears: they stand on their own brand gradient (a green screen without the green)."""
    bg = gradient(cfg)
    per_frame(src, out, s, e, lambda k, t, fr, a: (lambda p: fr * (1 - p) + (bg * (1 - a) + fr * a) * p)(ease(t / 0.3)), matte=True)


def spotlight(src, out, s, e, cfg):
    """The room blurs and darkens; they stay sharp and bright."""
    import cv2, numpy as np
    yy, xx = np.mgrid[0:1920, 0:1080].astype(np.float32)
    vig = (1 - 0.55 * (((xx - 540) / 700) ** 2 + ((yy - 760) / 1100) ** 2)).clip(0.35, 1)[..., None]

    def draw(k, t, fr, a):
        p = ease(t / 0.3)
        back = cv2.GaussianBlur(fr, (0, 0), 18) * 0.55 * vig
        return fr * (1 - p) + (back * (1 - a) + fr * a) * p
    per_frame(src, out, s, e, draw, matte=True)


def step_counter(src, out, s, e, cfg):
    """STEP 1, STEP 2, STEP 3: a chip with the step and its words, swapping as they say each one."""
    from PIL import ImageDraw
    acc = rgb(cfg.get("accent", "#00A6FF"))
    items = [i for i in cfg.get("items", []) if str(i.get("text", "")).strip()][:5] or [{"text": "Start here", "at": s}]
    fb, ft = font_for(cfg, 46), font_for(cfg, 58)
    chips = []
    for i, it in enumerate(items, 1):
        lay = rgba_layer(); d = ImageDraw.Draw(lay)
        tag, txt = f"STEP {i}", str(it["text"])[:24]
        tw = d.textlength(tag, font=fb) + 60
        y = int(1920 * 0.1)
        d.rounded_rectangle([60, y, 60 + tw, y + 84], radius=42, fill=acc + (255,))
        d.text((90, y + 14), tag, font=fb, fill=(255, 255, 255, 255))
        d.rounded_rectangle([60, y + 96, 60 + d.textlength(txt, font=ft) + 60, y + 196], radius=26, fill=(255, 255, 255, 240))
        d.text((90, y + 110), txt, font=ft, fill=(6, 21, 61, 255))
        chips.append(lay)
    times = [max(0.0, float(it.get("at", s)) - s) for it in items]

    def draw(k, t, fr, a):
        i = max(0, sum(1 for x in times if x <= t) - 1)
        since = t - times[i]
        return paste(fr, chips[i], ease(since / 0.2), dy=-(1 - ease(since / 0.25)) * 40)
    per_frame(src, out, s, e, draw)



# ---------------------------------------------------------------- paper scribble (2026-10-27, Tiff's idea)
# She holds up a blank sheet. The sheet gets a white sticker outline and her words scribble onto it as she
# says them; the next note flips the sheet over. The sheet is found in every frame (no cut-out model).

def find_paper(fr):
    """The held-up sheet: the biggest bright, colourless, nearly 4-sided shape. 4 corners (tl, tr, br, bl) or None."""
    import cv2, numpy as np
    h, w = fr.shape[:2]
    hsv = cv2.cvtColor(fr, cv2.COLOR_BGR2HSV)
    m = ((hsv[..., 1] < 45) & (hsv[..., 2] > 135)).astype(np.uint8) * 255   # 135, not 165: the shaded half counts too
    k = max(3, w // 144)
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((k, k), np.uint8))
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((2 * k, 2 * k), np.uint8))
    cs, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    best = None
    for c in cs:
        a = cv2.contourArea(c)
        if a < 0.015 * w * h:
            continue
        hull = cv2.convexHull(c)
        if a / max(cv2.contourArea(hull), 1) < 0.85:
            continue
        q = cv2.approxPolyDP(hull, 0.03 * cv2.arcLength(hull, True), True)
        if 4 <= len(q) <= 6 and (best is None or a > best[0]):
            pts = q.reshape(-1, 2).astype(np.float32)
            if len(q) != 4 or cv2.contourArea(pts) < 0.85 * a:      # a hand on the corner: the sheet's box instead
                pts = cv2.boxPoints(cv2.minAreaRect(hull))
            best = (a, pts)
    if best is None:
        return None
    pts = best[1]
    sm, df = pts.sum(1), np.diff(pts, axis=1).ravel()
    return np.float32([pts[sm.argmin()], pts[df.argmin()], pts[sm.argmax()], pts[df.argmax()]])


def paper_scan(src, step=0.2):
    """Where a sheet is held up: [[start, end], ...] in seconds, each at least 0.6 s long."""
    import cv2
    cap = cv2.VideoCapture(src)
    secs, spans, on, t, miss = probe_secs(src), [], None, 0.0, False
    while t < secs:
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, fr = cap.read()
        if not ok:
            break
        seen = find_paper(fr) is not None
        if not seen and on is not None and not miss:      # one missed look (a hand, a blur) does not end a hold
            miss, t = True, t + step
            continue
        miss = False
        if seen and on is None:
            on = t
        if not seen and on is not None:
            if t - on >= 0.6:
                spans.append([round(on, 2), round(t, 2)])
            on = None
        t += step
    if on is not None and t - on >= 0.6:
        spans.append([round(on, 2), round(min(t, secs), 2)])
    return spans


def paper_scribble(src, out, s, e, cfg):
    """notes: [{"text", "start", "end"}] in seconds. Each note scribbles on as it is said; the next one flips the sheet."""
    import cv2, numpy as np
    from PIL import Image, ImageDraw, ImageFont
    notes = sorted([n for n in cfg.get("notes", []) if str(n.get("text", "")).strip()], key=lambda n: n["start"])
    if not notes:
        raise SystemExit("paper-scribble needs at least one note")
    ink = tuple(rgb(cfg.get("ink") or cfg.get("accent", "#093AD6")))
    hand = cfg.get("hand") or os.path.join(os.path.expanduser("~/vibe-editing/plugins/vibe-editing/skills/caption-clips/fonts"), "Caveat.ttf")
    CW, CH = 600, 800
    cards = {}

    def card(i, p):
        """The note's ink on a sheet-shaped canvas, written p (0 to 1) of the way."""
        key = (i, round(p, 2))
        if key not in cards:
            txt = notes[i]["text"].strip()
            bullets = [str(x).strip() for x in notes[i].get("lines") or [] if str(x).strip()]
            size = 280 if not bullets and len(txt) <= 8 else 170      # one short word ("HELP!") fills the sheet
            while True:
                f = ImageFont.truetype(hand, size)
                try:
                    f.set_variation_by_name("Bold")
                except Exception:
                    pass
                d = ImageDraw.Draw(Image.new("RGBA", (CW, CH)))
                lines, cur = [], ""
                for b in bullets:          # a long bullet wraps under itself, so the writing stays big
                    row = "• "
                    for w in b.split():
                        if d.textlength((row + " " + w).strip(), font=f) > CW * 0.86 and row.strip() != "•":
                            lines.append(row); row = "   " + w
                        else:
                            row = (row + " " + w) if row.strip() != "•" else row + w
                    lines.append(row)
                for w in ([] if bullets else txt.split()):
                    test = (cur + " " + w).strip()
                    if d.textlength(test, font=f) > CW * 0.84 and cur:
                        lines.append(cur); cur = w
                    else:
                        cur = test
                if cur or not bullets:
                    lines.append(cur)
                if size <= 70 or (len(lines) * size * 1.05 < CH * (0.86 if bullets else 0.7) and max(d.textlength(l, font=f) for l in lines) <= CW * 0.88):
                    break
                size -= 10
            im = Image.new("RGBA", (CW, CH), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
            lh = size * 1.05
            y0 = (CH - lh * len(lines)) / 2 - 30
            total = sum(d.textlength(l, font=f) for l in lines)
            left = total * min(1.0, p if bullets else p / 0.82)    # the words take 82% of the time, the underline the rest
            for n, l in enumerate(lines):
                lw = d.textlength(l, font=f)
                x = CW * 0.08 if bullets else (CW - lw) / 2
                line = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
                ImageDraw.Draw(line).text((x, y0 + n * lh), l, font=f, fill=ink + (255,), stroke_width=max(2, size // 40), stroke_fill=ink + (255,))
                show = max(0.0, min(lw, left))
                left -= lw
                if show > 0:
                    m = Image.new("L", (CW, CH), 0)
                    ImageDraw.Draw(m).rectangle([0, 0, int(x + show), CH], fill=255)
                    im.paste(line, (0, 0), Image.composite(line, Image.new("RGBA", (CW, CH)), m).split()[3])
            u = 0.0 if bullets else max(0.0, (p - 0.82) / 0.18)
            if u > 0:      # a quick hand-drawn underline, two passes
                yb = y0 + lh * len(lines) + 6
                xs = np.linspace(CW * 0.14, CW * 0.86, 40)
                ys = yb + 7 * np.sin(xs / 23.0)
                pts = [(float(a), float(b)) for a, b in zip(xs, ys)][:max(2, int(40 * u))]
                ImageDraw.Draw(im).line(pts, fill=ink + (255,), width=9, joint="curve")
            cards[key] = np.asarray(im).astype(np.float32) / 255.0
        return cards[key]

    def write_secs(n):
        chars = sum(len(str(x)) + 2 for x in n["lines"]) if n.get("lines") else len(n["text"])
        return max(0.45, chars / float(n.get("chars_per_sec") or cfg.get("chars_per_sec", 16)))

    st = {"q": None, "miss": 99}
    src_quad = np.float32([[0, 0], [CW, 0], [CW, CH], [0, CH]])

    def draw(k, t, fr, a):
        T = s + t
        q = find_paper((fr * 255).astype(np.uint8))
        if q is not None and st["q"] is not None and st["miss"] <= 3 and cv2.contourArea(q) < 0.75 * cv2.contourArea(st["q"]):
            q = None       # only part of the sheet was found this frame: keep the last good one
        if q is not None:
            st["q"] = q if st["q"] is None or st["miss"] > 3 else st["q"] * 0.45 + q * 0.55
            st["miss"] = 0
        else:
            st["miss"] += 1
        live = [i for i, n in enumerate(notes) if n["start"] - 0.25 <= T <= n["end"]]
        if st["q"] is None or st["miss"] > 4 or not live:
            return fr
        vis = 1.0 - st["miss"] / 5.0
        i = live[-1]; n = notes[i]
        H, W = fr.shape[:2]
        poly = st["q"].astype(np.int32)
        sheet = np.zeros((H, W), np.uint8); cv2.fillConvexPoly(sheet, poly, 255)
        grow = cv2.dilate(sheet, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (31, 31)))
        shadow = cv2.GaussianBlur(np.roll(grow, 14, axis=0), (0, 0), 12).astype(np.float32)[..., None] / 255.0
        img = fr * (1 - 0.38 * shadow * vis)
        hsv = cv2.cvtColor((fr * 255).astype(np.uint8), cv2.COLOR_BGR2HSV)
        papery = cv2.GaussianBlur(((hsv[..., 1] < 55) & (hsv[..., 2] > 120)).astype(np.float32), (0, 0), 2)[..., None]
        lift = sheet.astype(np.float32)[..., None] / 255.0 * vis * 0.6 * papery     # the sheet reads clean white, like a cut-out
        img = img * (1 - lift) + (1 - (1 - img) * 0.35) * lift
        ring = ((grow > 0) & (sheet == 0)).astype(np.float32)
        ring = cv2.GaussianBlur(ring, (0, 0), 1.2)[..., None] * vis
        img = img * (1 - ring) + ring
        # the flip: the sheet turns edge-on at a note's start (after the first) and end
        fl = 0.18
        if T < n["start"] and i > 0:
            sx = abs(np.cos(np.pi / 2 * (1 - (T - (n["start"] - 0.25)) / 0.25)))
        elif T > n["end"] - fl and i < len(notes) - 1:
            sx = abs(np.cos(np.pi / 2 * (T - (n["end"] - fl)) / fl))
        else:
            sx = 1.0
        p = 0.0 if T < n["start"] else min(1.0, (T - n["start"]) / write_secs(n))
        c = card(i, p)
        if sx < 0.999:     # squash the ink toward the sheet's middle, and wash the sheet white while it turns
            cw = max(2, int(CW * sx))
            c2 = np.zeros_like(c); x0 = (CW - cw) // 2
            c2[:, x0:x0 + cw] = cv2.resize(c, (cw, CH))
            c = c2
            wash = (1 - sx) * 0.85
            sh = sheet.astype(np.float32)[..., None] / 255.0 * wash * vis
            img = img * (1 - sh) + sh
        M = cv2.getPerspectiveTransform(src_quad, st["q"])
        warped = cv2.warpPerspective(c, M, (W, H), flags=cv2.INTER_LINEAR, borderValue=(0, 0, 0, 0))
        al = warped[..., 3:4] * vis * (sheet.astype(np.float32)[..., None] / 255.0) * papery
        return img * (1 - al) + warped[..., [2, 1, 0]] * al
    if cfg.get("sound", True):
        tmp = out + ".silent" + os.path.splitext(out)[1]
        per_frame(src, tmp, s, e, draw)
        wav = out + ".scribble.wav"
        scribble_sound(wav, probe_secs(tmp), [(n["start"], n["start"] + write_secs(n)) for n in notes])
        mp4 = out.lower().endswith(".mp4")
        run([FF, "-v", "error", "-i", tmp, "-i", wav, "-filter_complex",
             "[0:a]aresample=48000[v];[1:a]volume=1.0[s];[v][s]amix=inputs=2:duration=first:normalize=0[a]",
             "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac" if mp4 else "pcm_s16le", *(["-b:a", "192k"] if mp4 else []),
             "-y", out])
        os.remove(tmp); os.remove(wav)
    else:
        per_frame(src, out, s, e, draw)


def scribble_sound(path, secs, spans, rate=48000):
    """A pencil on paper, made from noise: short scratchy strokes while the ink writes. Nothing downloaded."""
    import numpy as np, wave
    rng = np.random.default_rng(7)
    out = np.zeros(int(secs * rate) + 1, np.float32)
    for a, b in spans:
        t = a
        while t < b:
            n = int(rng.uniform(0.05, 0.13) * rate)
            x = rng.standard_normal(n).astype(np.float32)
            hi = x - np.convolve(x, np.ones(6) / 6, "same")          # the hiss of graphite
            lo = np.convolve(x, np.ones(40) / 40, "same") * 3.0      # the paper under it
            env = np.minimum(1, np.arange(n) / (0.006 * rate)) * np.exp(-np.arange(n) / (0.07 * rate))
            env *= 1 + 0.5 * np.sin(np.arange(n) / rate * 2 * np.pi * rng.uniform(18, 30))
            i = int(t * rate)
            seg = (hi * 0.8 + lo * 0.35) * env * rng.uniform(0.6, 1.0)
            out[i:i + n] += seg[:max(0, len(out) - i)]
            t += n / rate + rng.uniform(0.01, 0.045)
    out = np.clip(out / (np.abs(out).max() or 1) * 0.7, -1, 1)   # loud enough to hear under a voice
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
        w.writeframes((out * 32767).astype(np.int16).tobytes())

def cta_pop(src, out, s, e, cfg):
    """The person's own call to action pops in on a white pill, like the follow buttons creators drop into
    their reels. With a button it flips from Follow to Following halfway. Built for the reel copycat
    (2026-10-27): it goes where the copied creator's own call to action was, with the person's words."""
    from PIL import ImageDraw
    acc = rgb(cfg.get("accent", "#00A6FF"))
    text, button = str(cfg.get("text") or "")[:40], str(cfg.get("button") or "")[:12]
    ft, fb = font_for(cfg, 52), font_for(cfg, 40)
    probe_d = ImageDraw.Draw(rgba_layer())
    tw = probe_d.textlength(text, font=ft)
    bw = probe_d.textlength(button + "ing", font=fb) + 70 if button else 0
    w = int(min(1000, 130 + tw + (bw + 30 if button else 0) + 40))
    x0, y = (1080 - w) // 2, int(1920 * min(0.8, max(0.1, float(cfg.get("y", 0.2)))))

    def layer(pressed):
        lay = rgba_layer(); d = ImageDraw.Draw(lay)
        d.rounded_rectangle([x0 + 6, y + 10, x0 + w + 6, y + 120], radius=55, fill=(0, 0, 0, 70))
        d.rounded_rectangle([x0, y, x0 + w, y + 110], radius=55, fill=(255, 255, 255, 250))
        d.ellipse([x0 + 22, y + 20, x0 + 92, y + 90], fill=acc + (255,))
        d.ellipse([x0 + 40, y + 38, x0 + 74, y + 72], outline=(255, 255, 255, 255), width=6)
        d.text((x0 + 112, y + 55), text, font=ft, fill=(6, 21, 61, 255), anchor="lm")
        if button:
            bx = x0 + w - 30 - bw
            label = button + "ing" if pressed else button
            d.rounded_rectangle([bx, y + 22, bx + bw, y + 88], radius=20,
                                fill=(225, 230, 240, 255) if pressed else acc + (255,))
            d.text((bx + bw / 2, y + 55), label, font=fb, fill=(6, 21, 61, 255) if pressed else (255, 255, 255, 255), anchor="mm")
        return lay
    up, down = layer(False), layer(True)
    L = e - s

    def draw(k, t, fr, a):
        a_in = ease(t / 0.3) if t < 0.3 else (1 - ease((t - (L - 0.25)) / 0.25) if t > L - 0.25 else 1.0)
        return paste(fr, down if button and t > L * 0.45 else up, a_in, dy=-(1 - a_in) * 60)
    per_frame(src, out, s, e, draw)


def article_screen(src, out, s, e, cfg):
    """2026-10-31, Tiff's green screen from the article video: the room melts into their picture (an article,
    a screenshot, a site) and they glide down small to the bottom middle, fading into it. Same settings as her
    5 Minute Upgrade: picture covers the frame from 18% down, they shrink to 62%, the lower body fades."""
    import cv2, numpy as np
    W, H = 1080, 1920
    pic = cv2.imread(cfg["picture"], cv2.IMREAD_COLOR)
    if pic is None:
        raise RuntimeError("couldn't open the picture")
    ph, pw = pic.shape[:2]
    k0 = max(W / pw, H / ph)
    pic = cv2.resize(pic, (max(W, round(pw * k0)), max(H, round(ph * k0))), interpolation=cv2.INTER_AREA)
    oy, ox = int((pic.shape[0] - H) * 0.18), (pic.shape[1] - W) // 2
    bg = pic[oy:oy + H, ox:ox + W].astype(np.float32) / 255.0
    SC, L = 0.62, e - s
    ys = np.linspace(0, 1, H, dtype=np.float32)[:, None, None]
    fade = np.clip((1 - ys) / 0.14, 0, 1)                 # the bottom of the person melts into the picture

    def person(fr, a, sc):
        w, h = round(W * sc), round(H * sc)
        f2, a2 = cv2.resize(fr, (w, h), interpolation=cv2.INTER_AREA), cv2.resize(a, (w, h), interpolation=cv2.INTER_AREA)[..., None]
        xs = np.linspace(0, 1, w, dtype=np.float32)[None, :, None]
        side = np.clip(np.minimum(xs, 1 - xs) / 0.08, 0, 1) if sc < 0.999 else 1.0
        F, A = np.zeros((H, W, 3), np.float32), np.zeros((H, W, 1), np.float32)
        x0, y0 = (W - w) // 2, H - h                        # bottom stays on the bottom edge
        F[y0:, x0:x0 + w], A[y0:, x0:x0 + w] = f2, a2 * side
        return F, A * (fade if sc < 0.999 else 1.0)

    def draw(k, t, fr, a):
        p = ease(t / 0.5) if t < 0.5 else (1 - ease((t - (L - 0.4)) / 0.4) if cfg.get("back") and t > L - 0.4 else 1.0)
        F, A = person(fr, a, 1 + (SC - 1) * p)
        base = fr * (1 - p) + bg * p
        return base * (1 - A) + F * A
    per_frame(src, out, s, e, draw, matte=True)


EFFECTS = {**MORE_EFFECTS, "digital-zoom": digital_zoom, "cinema-look": cinema_look, "brand-stage": brand_stage, "brand-frame": brand_frame,
           "top-banner": top_banner, "word-pop": word_pop, "split-stage": split_stage, "note-card": note_card, "glow-words": glow_words, "doodles": doodles, "glass-meter": glass_meter, "orbit": orbit, "pop-out": pop_out, "zoom-punch": zoom_punch, "cta-pop": cta_pop, "number-pop": number_pop, "checklist": checklist, "headline-behind": headline_behind,
           "lower-third": lower_third, "quote-card": quote_card, "marker-swipe": marker_swipe, "stat-bars": stat_bars,
           "phone-frame": phone_frame, "brand-backdrop": brand_backdrop, "spotlight": spotlight, "step-counter": step_counter,
           "paper-scribble": paper_scribble, "article-screen": article_screen}

if __name__ == "__main__" and len(sys.argv) == 3 and sys.argv[1] == "paper-scan":
    print(json.dumps(paper_scan(sys.argv[2])))
    sys.exit(0)

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("effect", choices=list(EFFECTS)); ap.add_argument("src"); ap.add_argument("out")
    ap.add_argument("--start", type=float, required=True); ap.add_argument("--end", type=float, required=True)
    ap.add_argument("--config", default="{}")
    a = ap.parse_args()
    cfg = json.loads(a.config)
    cfg.setdefault("font", os.path.join(os.path.expanduser("~/vibe-editing/plugins/vibe-editing/skills/caption-clips/fonts"), "Montserrat-ExtraBold.ttf"))
    EFFECTS[a.effect](a.src, a.out, a.start, a.end, cfg)
    print(json.dumps({"ok": True, "out": a.out}))
