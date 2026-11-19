#!/usr/bin/env python3
"""Cut exact stretches out of a FINISHED video, the way Tiff marks them by ear (2026-10-28):
"between 14 and 16 seconds I say 'and' and it cuts off, then I say 'and'. Cut off that first 'and'."

usage: trim_cuts.py <in.mp4> <out.mp4> '[[a, b], [a, b]]'
Cuts are in seconds of the video given. Each edge lands on a whole frame (picture and sound stay the same length),
every join gets a 15 ms fade so it never clicks, and it is encoded once at a quality setting (4K stays sharp).
Prints JSON: {"ok", "seconds", "frames", "want_frames", "audio_packets", "want_packets", "mbps"}.
"""
import json, os, shutil, subprocess, sys

FF = shutil.which("ffmpeg", path=os.path.expanduser("~/.local/bin")) or shutil.which("ffmpeg")
FP = shutil.which("ffprobe", path=os.path.expanduser("~/.local/bin")) or shutil.which("ffprobe")


def probe(path, *entries):
    out = subprocess.run([FP, "-v", "error", "-show_entries", ":".join(entries), "-of", "json", path],
                         capture_output=True, text=True).stdout
    return json.loads(out)


src, dst, cuts = sys.argv[1], sys.argv[2], json.loads(sys.argv[3])
info = probe(src, "format=duration", "stream=codec_type,r_frame_rate")
secs = float(info["format"]["duration"])
num, den = (int(x) for x in next(s for s in info["streams"] if s["codec_type"] == "video")["r_frame_rate"].split("/"))
fps = num / den
snap = lambda t: round(t * fps) / fps

keep, t = [], 0.0
for a, b in sorted((snap(a), snap(b)) for a, b in cuts):
    if a - t >= 0.25:        # never leave a sliver between two cuts: it stutters
        keep.append((t, a))
    t = max(t, b)
if snap(secs) - t >= 0.25:
    keep.append((t, snap(secs)))

n = len(keep)
fc = [f"[0:v]split={n}" + "".join(f"[vs{i}]" for i in range(n)),
      f"[0:a]aresample=48000,asplit={n}" + "".join(f"[as{i}]" for i in range(n))]
for i, (x, y) in enumerate(keep):
    fc.append(f"[vs{i}]trim=start={x:.4f}:end={y:.4f},setpts=PTS-STARTPTS[v{i}]")
    fc.append(f"[as{i}]atrim=start={x:.4f}:end={y:.4f},asetpts=PTS-STARTPTS,"
              f"afade=t=in:d=0.015,areverse,afade=t=in:d=0.015,areverse[a{i}]")
fc.append("".join(f"[v{i}][a{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=1[v][a]")
script = dst + ".filter.txt"
open(script, "w").write(";\n".join(fc))
subprocess.run([FF, "-v", "error", "-i", src, "-/filter_complex", script, "-map", "[v]", "-map", "[a]",
                "-c:v", "libx264", "-crf", "14", "-preset", "fast", "-pix_fmt", "yuv420p", "-profile:v", "high",
                "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-y", dst], check=True)
os.remove(script)

# count the thing, not the summary of the thing
c = json.loads(subprocess.run([FP, "-v", "error", "-count_packets", "-show_entries",
                               "stream=codec_type,nb_read_packets,sample_rate:format=duration", "-of", "json", dst],
                              capture_output=True, text=True).stdout)
dur = float(c["format"]["duration"])
v = next(s for s in c["streams"] if s["codec_type"] == "video")
a = next(s for s in c["streams"] if s["codec_type"] == "audio")
frames, packets = int(v["nb_read_packets"]), int(a["nb_read_packets"])
want_f, want_p = dur * fps, dur * int(a["sample_rate"]) / 1024
mbps = os.path.getsize(dst) * 8 / dur / 1e6
ok = abs(frames - want_f) <= 2 and abs(packets - want_p) <= 3 and mbps >= 8
print(json.dumps({"ok": ok, "seconds": round(dur, 2), "frames": frames, "want_frames": round(want_f, 1),
                  "audio_packets": packets, "want_packets": round(want_p, 1), "mbps": round(mbps, 1)}))
