#!/usr/bin/env python3
"""Finish one short in the owner's brand: 9:16, captions, hook on top.

Copied from ~/vibe-editing/tiff_short.py on 2026-10-26 so the dashboard runs on any Mac with the
Vibe Editing kit (Box 1). The brand comes from --preset, --font and --accent instead of Tiff's files.

usage: finisher.py <cut.mov> <out.mp4> --hook "LINE ONE" "LINE TWO" [--blue word ...] [--preset p.json] [--font f.ttf] [--accent 00A6FF]

<cut.mov> is the already-cut, already-cleaned landscape clip. --blue lists the words that
turn #00A6FF (numbers are always blue). Captions are transcribed with Groq from the clip itself.
Prints a JSON report and exits non-zero if the output's frame count, size or length is off.
"""
import argparse, json, os, re, shutil, subprocess, sys, tempfile
import cv2, numpy as np

HOME = os.path.expanduser("~")
KIT = os.path.join(HOME, "vibe-editing/plugins/vibe-editing")
YUNET = os.path.join(KIT, "skills/horizontal-to-vertical/scripts/yunet.onnx")
SPICE = os.path.join(KIT, "skills/caption-clips/scripts/spice_caption.py")
PRESET = os.path.join(KIT, "skills/caption-clips/presets/spice.json")
FONT = os.path.join(KIT, "skills/caption-clips/fonts/Montserrat-ExtraBold.ttf")
ACCENT = "00A6FF"
PY = os.path.join(HOME, "vibe-editing/.venv/bin/python")
# the kit's own scripts call plain "python3"; the system one (3.9) has none of the packages
os.environ["PATH"] = os.pathsep.join([os.path.join(HOME, "vibe-editing/.venv/bin"), os.path.join(HOME, ".local/bin"),
                                      os.environ.get("PATH", "")])
face_y = 0.4
FIXES = {}


def run(cmd, **kw):
    subprocess.run(cmd, check=True, **kw)


def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-count_packets", "-select_streams", "v:0",
                          "-show_entries", "stream=width,height,nb_read_packets:format=duration",
                          "-of", "json", path], capture_output=True, text=True, check=True).stdout
    d = json.loads(out)
    s = d["streams"][0]
    return int(s["width"]), int(s["height"]), int(s["nb_read_packets"]), float(d["format"]["duration"])


def full_fast(src, dst):
    """2026-11-11: the whole-frame layout with no zooms needs no face tracking, so ffmpeg makes it in one pass
    on the video chip. Python used to hold every frame in memory for this (110 s, 3.4 GB on a 67 s phone video).
    A few frames are still read to find where the face sits, for the captions and the report."""
    global face_y, seams_n
    cap = cv2.VideoCapture(src)
    n, W, H = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)), int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if not (n and W and H):
        cap.release()
        return None
    det = cv2.FaceDetectorYN.create(YUNET, "", (W, H), 0.6)
    fys = []
    for k in range(12):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(n * (k + 0.5) / 12))
        ok, fr = cap.read()
        if not ok:
            continue
        _, fc = det.detect(fr)
        if fc is not None:
            b = max(fc, key=lambda r: r[2] * r[3])
            fys.append((b[1] + b[3] * 0.45) / H)
    cap.release()
    fy = float(np.median(fys)) if fys else 0.4
    fh = int(round(1080 * H / W)) // 2 * 2
    top = (1920 - fh) // 2 - 60
    if fh >= 1920 - 120:      # a phone video is already tall: it fills the frame, as reframe does
        ch = min(H, int(round(W * 16 / 9))) // 2 * 2
        face_y = ((fy * H) - (H - ch) // 2) / ch
        graph = ["-vf", f"fps=30,crop={W}:{ch},scale=1080:1920:flags=lanczos,setsar=1"]
    else:                     # wide: the whole picture on a dark blurred copy of itself, as reframe does
        face_y = (top + fy * fh) / 1920
        graph = ["-filter_complex", f"[0:v]fps=30,split[a][b];[a]scale=-2:1920,crop=1080:1920,scale=270:480,gblur=sigma=6,"
                 f"scale=1080:1920,colorchannelmixer=rr=0.35:gg=0.35:bb=0.35[bg];[b]scale=1080:{fh}:flags=area[fg];"
                 f"[bg][fg]overlay=0:{top},setsar=1[v]", "-map", "[v]", "-map", "0:a?"]
    run(["ffmpeg", "-v", "error", "-y", "-i", src, *graph, *fast_video(), "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", dst])
    seams_n = 1
    return probe(dst)[2], len(fys), 0, 0


def reframe(src, dst, layout="face", zooms=()):
    """Crop a 9:16 window that follows the biggest face, smoothed so it drifts, never jitters.
    zooms = [[t, z], ...]: from t on the picture is z times closer, centred on the face. A copied reel's
    cuts land here as jump-zooms (2026-10-27), drawn BEFORE the captions so the captions never zoom."""
    if layout == "full" and not zooms:
        quick = full_fast(src, dst)
        if quick:
            return quick
    cap = cv2.VideoCapture(src)
    frames = []
    while True:
        ok, f = cap.read()
        if not ok:
            break
        frames.append(f)
    H, W = frames[0].shape[:2]
    cw = int(round(H * 9 / 16)) // 2 * 2
    det = cv2.FaceDetectorYN.create(YUNET, "", (W, H), 0.6)
    raw = np.full(len(frames), np.nan)
    fys = []
    for i in range(0, len(frames), 2):
        _, fc = det.detect(frames[i])
        if fc is not None:
            b = max(fc, key=lambda r: r[2] * r[3])
            raw[i] = b[0] + b[2] / 2
            fys.append((b[1] + b[3] * 0.45) / H)
    idx = np.arange(len(frames))
    good = ~np.isnan(raw)
    # a join between cut pieces shows up as a sudden picture change; smooth each piece on its own,
    # or the crop lags behind at the start of a piece and cuts her face off (2026-10-26)
    small = [cv2.cvtColor(cv2.resize(f, (64, 36)), cv2.COLOR_BGR2GRAY).astype(float) for f in frames]
    seams = [0] + [i for i in range(1, len(frames)) if np.mean(np.abs(small[i] - small[i - 1])) > 18] + [len(frames)]
    cx = np.full(len(frames), W / 2)
    k = 15
    for s, e in zip(seams[:-1], seams[1:]):
        seg, g = idx[s:e], good[s:e]
        part = np.interp(seg, seg[g], raw[s:e][g]) if g.any() else np.full(e - s, W / 2)
        cx[s:e] = np.convolve(np.pad(part, (k // 2, k // 2), mode="edge"), np.ones(k) / k, mode="valid")
    x0 = np.clip(cx - cw / 2, 0, W - cw).astype(int)
    if layout == "full":
        # keep the WHOLE frame, only ever shrunk (never blown up), on a blurred copy of itself.
        # Zoom records her camera small, so zooming in on the face looks waxy (2026-10-26).
        fh = int(round(1080 * H / W)) // 2 * 2
        top = (1920 - fh) // 2 - 60
        bh = 1920; bw = int(round(bh * W / H))
        # a phone video is already tall: there is nothing to put above or below it, so it fills the frame
        # (crashed on a 720x1280 clip on 2026-10-26)
        tall = fh >= 1920 - 120
        ch = min(H, int(round(W * 16 / 9)))
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24",
                          "-s", "1080x1920", "-r", "30", "-i", "-", "-i", src, "-map", "0:v", "-map", "1:a",
                          *fast_video(), "-pix_fmt", "yuv420p",
                          "-c:a", "aac", "-b:a", "192k", "-shortest", dst], stdin=subprocess.PIPE, stderr=open(dst + ".log", "w"))
    fy = float(np.median(fys)) if fys else 0.4          # face height on the source, 0..1
    if layout == "full" and tall:
        ay = ((fy * H) - (H - ch) // 2) / ch * 1920
    elif layout == "full":
        ay = top + fy * fh
    else:
        ay = fy * 1920
    global face_y
    face_y = ay / 1920
    zs = sorted(zooms)

    def zoom(img, t):
        z = next((zz for tt, zz in reversed(zs) if t >= tt), 1.0)
        if z <= 1.001:
            return img
        w, h = int(1080 / z) // 2 * 2, int(1920 / z) // 2 * 2
        y0 = int(min(1920 - h, max(0, ay - h * 0.42)))
        return cv2.resize(img[y0:y0 + h, (1080 - w) // 2:(1080 - w) // 2 + w], (1080, 1920), interpolation=cv2.INTER_LANCZOS4)
    for i, f in enumerate(frames):
        if layout == "full" and tall:
            y0 = (H - ch) // 2
            out = cv2.resize(f[y0:y0 + ch], (1080, 1920), interpolation=cv2.INTER_LANCZOS4)
        elif layout == "full":
            bg = cv2.resize(f, (bw, bh), interpolation=cv2.INTER_AREA)
            bg = bg[:, (bw - 1080) // 2:(bw - 1080) // 2 + 1080]
            bg = (cv2.GaussianBlur(cv2.resize(bg, (270, 480)), (0, 0), 6)).astype(np.float32)
            canvas = (cv2.resize(bg, (1080, 1920)) * 0.35).astype(np.uint8)
            canvas[top:top + fh] = cv2.resize(f, (1080, fh), interpolation=cv2.INTER_AREA)
            out = canvas
        else:
            out = cv2.resize(f[:, x0[i]:x0[i] + cw], (1080, 1920), interpolation=cv2.INTER_LANCZOS4)
        try:
            p.stdin.write(zoom(out, i / 30.0).tobytes())
        except BrokenPipeError:      # 2026-10-27: the writer died when another render filled the disk mid-way
            p.wait()
            raise SystemExit("STOP: the video writer stopped (a full disk does this): " + open(dst + ".log").read()[-200:])
    p.stdin.close()
    p.wait()
    global seams_n
    seams_n = len(seams) - 1
    return len(frames), int(good.sum()), int(x0.min()), int(x0.max())


def fast_video():
    """2026-11-01, Tiff: "why in the hell does it take so long... not mess up quality but with speed." libx264 slow took
    12.7 s on a 12 s clip and the Mac's video chip 2.0 s at 45 Mbps, VMAF 99.3 against 99.1. Other computers keep the software encoder."""
    if sys.platform == "darwin" and "h264_videotoolbox" in subprocess.run(["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True).stdout:
        return ["-c:v", "h264_videotoolbox", "-b:v", "45M", "-maxrate", "60M"]
    return ["-c:v", "libx264", "-crf", "14", "-preset", "fast"]


def one_line_preset(work):
    """2026-10-27, Tiff: "I don't need this black smudge". A two-line caption's words wrapped but its soft
    shadow stayed one long line, leaving a dark bar beside the words. A caption that fits on one line can't
    split from its shadow, so this copy of the look caps each caption at 13 letters. The saved look is untouched."""
    p = json.load(open(PRESET))
    p.setdefault("layout", {})["max_chars_per_line"] = min(13, p.get("layout", {}).get("max_chars_per_line", 13))
    if globals().get("CAP_Y"):       # 2026-11-06: under the chin on edits where the middle is the face
        p["layout"]["y_percent_from_top"] = CAP_Y
    os.makedirs(work, exist_ok=True)       # the caption folder is made by the kit later; this runs first
    out = os.path.join(work, "one_line_preset.json")
    json.dump(p, open(out, "w"), indent=1)
    return out


def captions(src, dst, work, blue, caps=False):
    global PRESET
    PRESET = one_line_preset(work)
    pin = []
    # 2026-10-30: a new member has no Groq key, and the kit's caption tool stops without one ("missing
    # GROQ_API_KEY"). Write the words down on this computer instead and hand them over.
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import transcribe
    known = os.environ.get("CME_WORDS")
    if known and os.path.exists(known):
        pin = ["--words", known]
    elif not transcribe.groq_key():
        words, _ = transcribe.local(src)
        wf = os.path.join(work, "local_words.json")
        json.dump({"words": [{"word": w["word"].strip(), "start": w["start"], "end": w["end"]} for w in words]}, open(wf, "w"))
        pin = ["--words", wf]
    run([PY, SPICE, src, "--gen-only", "--work", work, "--preset", PRESET, "--no-layout"] + pin,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    norm = json.load(open(os.path.join(work, "spice_norm.json")))
    words = transcribe.fix_names(norm["words"])
    for w, nx in zip(words, words[1:]):      # 2026-10-27: "Tiff the air princess" was burned into a caption
        if re.sub(r"[^\w]", "", w["word"]).lower() == "air" and re.sub(r"[^\w]", "", nx["word"]).lower() == "princess":
            w["word"] = re.sub("air", "AI", w["word"], flags=re.I)
    for w in words:
        b = re.sub(r"[^\w]", "", w["word"]).lower()
        if b in FIXES:
            w["word"] = re.sub(b, FIXES[b], w["word"], flags=re.I)
        if caps:
            w["word"] = w["word"].upper()
    json.dump(norm, open(os.path.join(work, "spice_norm.json"), "w"))
    want = {x.lower() for x in blue}
    stream = {"words": {}, "voice_spans": []}
    for i, w in enumerate(words):
        if re.sub(r"[^\w%$-]", "", w["word"]).lower() in want:
            stream["words"][str(i)] = {"w": "emphasis"}
    json.dump(stream, open(os.path.join(work, "director_stream.json"), "w"))
    run([PY, SPICE, src, dst, "--preset", PRESET, "--no-layout", "--burn-from", work],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return " ".join(w["word"] for w in words)


def hook(src, dst, lines, top=150, until=None):
    from PIL import ImageFont
    rgb = tuple(int(ACCENT[i:i + 2], 16) for i in (0, 2, 4))
    ink = "0x06153D" if 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2] > 170 else "white"
    lines = [x for x in lines if x.strip()]
    size = 128
    while size > 44 and max(ImageFont.truetype(FONT, size).getbbox(x)[2] for x in lines) > 840:
        size -= 4

    def dt(t, y):
        t = t.replace("\\", "").replace(":", "\\:").replace("'", "’").replace(" ", "\\ ")
        return (f"drawtext=fontfile={FONT}:text={t}:fontsize={size}:fontcolor={ink}:x=(w-text_w)/2:y={y}:box=1:boxcolor=0x{ACCENT}:boxborderw=26"
                + (f":enable='lt(t,{until})'" if until else ""))
    vf = ",".join(dt(x, top + k * int(size * 1.42)) for k, x in enumerate(lines))
    if os.environ.get("CME_HOOK") == "two-tone" and len(lines) == 2:      # plain words over one line in a white box
        size = min(size, 64)
        safe = [x.replace("\\\\", "").replace(":", "\\\\:").replace("'", "’").replace(" ", "\\\\ ") for x in lines]
        w_ = f":enable='lt(t,{until})'" if until else ""
        vf = (f"drawtext=fontfile={FONT}:text={safe[0]}:fontsize={size}:fontcolor=white:x=(w-text_w)/2:y={top}:shadowcolor=black@0.7:shadowx=2:shadowy=3{w_},"
              f"drawtext=fontfile={FONT}:text={safe[1]}:fontsize={size}:fontcolor=black:x=(w-text_w)/2:y={top + int(size * 1.55)}:box=1:boxcolor=white:boxborderw=14{w_}")
    run(["ffmpeg", "-v", "error", "-i", src, "-vf", vf, *fast_video(),
         "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", "-y", dst])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cut"); ap.add_argument("out")
    ap.add_argument("--hook", nargs=2)
    ap.add_argument("--no-hook", action="store_true", help="no headline on top (copied styles without one)")
    ap.add_argument("--hook-top", type=int, default=150, help="pixels from the top for the first hook line")
    ap.add_argument("--caps", action="store_true", help="captions in ALL CAPS")
    ap.add_argument("--blue", nargs="*", default=[])
    ap.add_argument("--layout", choices=["face", "full"], default="face",
                    help="face = zoom in on her face; full = whole frame shrunk onto a blurred fill")
    ap.add_argument("--preset", default=PRESET)
    ap.add_argument("--font", default=FONT)
    ap.add_argument("--accent", default=ACCENT)
    ap.add_argument("--cap-y", type=int, default=0, help="captions this far down, in percent of the height")
    ap.add_argument("--moves", help="JSON file from a copied reel: {zooms: [[t, z]], hook_until: s}")
    a = ap.parse_args()
    mv = json.load(open(a.moves)) if a.moves else {}
    globals().update(PRESET=a.preset, FONT=a.font, ACCENT=a.accent.lstrip("#").upper(), CAP_Y=a.cap_y)
    work = tempfile.mkdtemp(prefix="tiffshort_")
    vert, capt = os.path.join(work, "vert.mp4"), os.path.join(work, "capt.mp4")
    n_in, faces, xmin, xmax = reframe(a.cut, vert, a.layout, mv.get("zooms", []))
    text = captions(vert, capt, os.path.join(work, "cap"), a.blue, a.caps)
    if a.no_hook or not a.hook:
        shutil.copy(capt, a.out)
    else:
        top = a.hook_top
        if a.moves and abs((top + 110) / 1920 - face_y) < 0.16:     # their headline sat where this face is: move it up
            top = 150
        hook(capt, a.out, a.hook, top, mv.get("hook_until"))
    w, h, n_out, dur = probe(a.out)
    _, _, _, dur_in = probe(a.cut)
    ok = (w, h) == (1080, 1920) and abs(n_out - n_in) <= 2 and abs(dur - dur_in) <= 0.1
    print(json.dumps({"ok": ok, "out": a.out, "size": f"{w}x{h}", "frames_in": n_in, "frames_out": n_out,
                      "seconds": round(dur, 2), "face_found_on_checks": faces, "crop_x_range": [xmin, xmax], "pieces": seams_n,
                      "captions": text, "work": work, "zooms": len(mv.get("zooms", [])), "face_y": round(face_y, 3)}, indent=1))
    if not ok:
        sys.exit("STOP: output size, frame count or length does not match")


if __name__ == "__main__":
    main()
