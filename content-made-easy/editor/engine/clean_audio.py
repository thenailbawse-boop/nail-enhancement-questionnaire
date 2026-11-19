#!/usr/bin/env python3
"""Clean the voice on a video with DeepFilterNet. The video picture is copied untouched.

Usage: clean_audio.py <video> [--strength 100]
Writes "<name> CLEAN.<ext>" next to the original and checks it before saying done.
strength = how much noise to remove in dB (100 = all of it, 20 to 30 = gentle, keeps some room sound).
"""
import json, os, shutil, subprocess, sys, tempfile

HOME = os.path.expanduser("~")
BIN = os.path.join(HOME, ".local", "bin")
FFMPEG = shutil.which("ffmpeg", path=BIN) or shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe", path=BIN) or shutil.which("ffprobe")
DF = os.path.join(BIN, "deep-filter") if os.path.exists(os.path.join(BIN, "deep-filter")) else (shutil.which("deep-filter") or os.path.join(BIN, "deep-filter"))


def probe(path):
    out = subprocess.run([FFPROBE, "-v", "error", "-show_entries",
                          "format=duration:stream=index,codec_type,channels,sample_rate",
                          "-of", "json", path], capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def main():
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    src = os.path.abspath(args[0])
    strength = args[args.index("--strength") + 1] if "--strength" in args else "100"
    for tool, name in ((FFMPEG, "ffmpeg"), (FFPROBE, "ffprobe"), (DF if os.path.exists(DF) else None, "deep-filter")):
        if not tool:
            sys.exit(f"STOP: {name} is not installed")
    info = probe(src)
    audio = [s for s in info["streams"] if s["codec_type"] == "audio"]
    if not audio:
        sys.exit("STOP: this video has no sound to clean")
    dur = float(info["format"]["duration"])
    ch = min(int(audio[0].get("channels", 1)), 2)
    base, ext = os.path.splitext(src)
    dst = f"{base} CLEAN{ext or '.mp4'}"
    # free space: output is about the size of the input, plus working audio
    need = os.path.getsize(src) * 1.2 + dur * 48000 * 4 * ch * 2
    free = shutil.disk_usage(os.path.dirname(src)).free
    if free < need:
        sys.exit(f"STOP: need {need/1e9:.1f} GB free, only {free/1e9:.1f} GB")

    work = tempfile.mkdtemp(prefix="cleanaudio_")
    try:
        wav = os.path.join(work, "voice.wav")
        subprocess.run([FFMPEG, "-v", "error", "-i", src, "-map", "0:a:0", "-vn", "-ac", str(ch),
                        "-ar", "48000", "-c:a", "pcm_s16le", "-y", wav], check=True)
        outdir = os.path.join(work, "out")
        # -D lines the cleaned audio back up with the lips (removes the filter's built-in delay)
        subprocess.run([DF, "-D", "-a", str(strength), "-o", outdir, wav], check=True,
                       capture_output=True)
        clean = os.path.join(outdir, "voice.wav")
        # picture copied as-is; audio padded/trimmed to the exact original length
        subprocess.run([FFMPEG, "-v", "error", "-i", src, "-i", clean,
                        "-map", "0:v?", "-map", "1:a:0", "-c:v", "copy",
                        "-af", f"apad,atrim=0:{dur:.6f}", "-c:a", "aac", "-b:a", "256k",
                        "-movflags", "+faststart", "-y", dst], check=True)
    finally:
        shutil.rmtree(work, ignore_errors=True)

    # prove it: plays, same length, picture untouched
    a, b = probe(src), probe(dst)
    d0, d1 = float(a["format"]["duration"]), float(b["format"]["duration"])
    v0 = [s for s in a["streams"] if s["codec_type"] == "video"]
    v1 = [s for s in b["streams"] if s["codec_type"] == "video"]
    ok = abs(d0 - d1) <= 0.05 and len(v0) == len(v1)
    print(json.dumps({"ok": ok, "output": dst, "original_seconds": round(d0, 3),
                      "clean_seconds": round(d1, 3), "strength_db": strength}, indent=1))
    if not ok:
        sys.exit("STOP: the cleaned file does not match the original length or lost its picture")


if __name__ == "__main__":
    main()
