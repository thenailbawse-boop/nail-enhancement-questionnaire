#!/bin/zsh
# First run of Your Marketing Dashboard: installs everything a video needs, by itself.
# 2026-10-30, Tiff: "Make it so that it installs it when they open it up." A tester skipped the
# Claude Code setup box and her first video stopped on "No such file ... ffprobe".
# Everything lands in the person's own home folder. No password, no Homebrew, no Claude Code.
# Every download is pinned to one exact version. Safe to run again: it skips what is already there.

LOG="$(dirname "$0")/install.log"
B="$HOME/.local/bin"
KITDIR="$HOME/vibe-editing"
VENV="$KITDIR/.venv"
mkdir -p "$B"
case "$(uname -m)" in arm64) A=arm64; R=aarch64; FFV=1789931890_9.0.2 ;; *) A=amd64; R=x86_64; FFV=1789931006_9.0.2 ;; esac
TMP="$(mktemp -d)"
say() { echo "  $1"; echo "$(date '+%H:%M:%S') $1" >> "$LOG"; }
fail() { say "STOPPED: $1"; echo ""; echo "  Something didn't install. Send Tiff a screenshot of this window."; rm -rf "$TMP"; exit 1; }
get() { curl -fsSL --retry 3 -m 900 -o "$2" "$1" >> "$LOG" 2>&1; }

# 1. ffmpeg and ffprobe (static builds, ffmpeg.martin-riedl.de, version 9.0.2)
for t in ffmpeg ffprobe; do
  if ! "$B/$t" -version >/dev/null 2>&1; then
    say "Getting $t..."
    get "https://ffmpeg.martin-riedl.de/download/macos/$A/$FFV/$t.zip" "$TMP/$t.zip" || fail "could not download $t"
    rm -f "$B/$t"
    unzip -qo "$TMP/$t.zip" -d "$B" >> "$LOG" 2>&1 || fail "could not unpack $t"
    chmod +x "$B/$t"; xattr -d com.apple.quarantine "$B/$t" 2>/dev/null
    "$B/$t" -version >/dev/null 2>&1 || fail "$t does not run on this Mac"
  fi
done

# 2. DeepFilterNet, the free background-noise cleaner (version 0.5.6)
if [ ! -x "$B/deep-filter" ]; then
  say "Getting the sound cleaner..."
  get "https://github.com/Rikorose/DeepFilterNet/releases/download/v0.5.6/deep-filter-0.5.6-$R-apple-darwin" "$B/deep-filter" \
    && chmod +x "$B/deep-filter" || { rm -f "$B/deep-filter"; say "Sound cleaner skipped (videos still work)."; }
fi

# 2b. yt-dlp, so Copy an edit can read a reel from its link (version 2026.08.19)
if ! "$B/yt-dlp" --version >/dev/null 2>&1; then
  say "Getting the reel reader..."
  get "https://github.com/yt-dlp/yt-dlp/releases/download/2026.08.19/yt-dlp_macos" "$B/yt-dlp" \
    && chmod +x "$B/yt-dlp" && xattr -d com.apple.quarantine "$B/yt-dlp" 2>/dev/null
  "$B/yt-dlp" --version >/dev/null 2>&1 || { rm -f "$B/yt-dlp"; say "Reel reader skipped (Copy an edit won't work, everything else will)."; }
fi

# 3. The editing kit: fonts, face finder (Vibe Editing, pinned commit)
if [ ! -f "$KITDIR/plugins/vibe-editing/skills/horizontal-to-vertical/scripts/yunet.onnx" ]; then
  say "Getting the editing kit..."
  SHA=83c5ff6006dd79918e8395ef58cfcb4600c21db5
  get "https://codeload.github.com/maddexritter-rgb/vibe-editing/zip/$SHA" "$TMP/kit.zip" || fail "could not download the editing kit"
  unzip -q "$TMP/kit.zip" -d "$TMP" >> "$LOG" 2>&1 || fail "could not unpack the editing kit"
  mkdir -p "$KITDIR"
  cp -Rn "$TMP/vibe-editing-$SHA/." "$KITDIR/" || fail "could not copy the editing kit"
fi

# 3b. The fixes made to the kit on Tiff's Mac (ffmpeg 9 flags, mp4 sound, caption colors). Laid over it every
# time, so a member who installed before a fix gets it too. 2026-10-30: without them captions failed.
if [ -d "$(dirname "$0")/kit-fixes" ]; then
  cp -R "$(dirname "$0")/kit-fixes/." "$KITDIR/" || fail "could not add the kit fixes"
fi

# 4. Python and the video packages (uv 0.12.21, Python 3.12, the versions that work on Tiff's Mac)
if ! "$VENV/bin/python" -c "import cv2, numpy, PIL, requests, fontTools, faster_whisper, onnxruntime" >/dev/null 2>&1; then
  if ! "$B/uv" --version >/dev/null 2>&1; then
    say "Getting Python..."
    get "https://github.com/astral-sh/uv/releases/download/0.12.21/uv-$R-apple-darwin.tar.gz" "$TMP/uv.tgz" || fail "could not download uv"
    tar -xzf "$TMP/uv.tgz" -C "$TMP" && cp "$TMP/uv-$R-apple-darwin/uv" "$B/uv" && chmod +x "$B/uv" || fail "could not unpack uv"
  fi
  say "Setting up the video tools (about 2 minutes)..."
  [ -x "$VENV/bin/python" ] || "$B/uv" venv --python 3.12 "$VENV" >> "$LOG" 2>&1 || fail "could not set up Python"
  "$B/uv" pip install --python "$VENV/bin/python" \
    numpy==2.5.4 opencv-python==5.0.0.93 pillow==13.0.0 requests==2.34.2 fonttools==4.67.0 \
    faster-whisper==1.2.1 av==15.1.0 ctranslate2==4.8.3 onnxruntime==1.31.0 tokenizers==0.23.3 huggingface-hub==2.2.0 \
    >> "$LOG" 2>&1 || fail "could not install the video packages"
  "$VENV/bin/python" -c "import cv2, numpy, PIL, requests, fontTools, faster_whisper, onnxruntime" >> "$LOG" 2>&1 \
    || fail "the video packages did not load"
fi

# 5. The speech model that writes down your words (466 MB). Got now so your first video doesn't wait on it.
# 2026-11-11: this ran 4 minutes with nothing moving on screen, and Tiff thought setup was stuck. Now it says
# how far it is every 10 seconds. HF_HUB_DISABLE_XET makes it a plain download, so the file grows where we can
# measure it (the other way writes the whole file at the very end). It also checks for model.bin itself: the
# folder appears before the model does, so a stopped download used to look finished.
M="$HOME/.cache/huggingface/hub/models--Systran--faster-whisper-small.en"
if ! find "$M/snapshots" -name model.bin 2>/dev/null | grep -q .; then
  say "Getting the word writer, 466 MB (about 4 minutes, longer on slow internet)..."
  HF_HUB_DISABLE_XET=1 "$VENV/bin/python" -c "from faster_whisper import WhisperModel; WhisperModel('small.en', device='cpu', compute_type='int8')" >> "$LOG" 2>&1 &
  WP=$!
  while kill -0 $WP 2>/dev/null; do
    for i in 1 2 3 4 5 6 7 8 9 10; do kill -0 $WP 2>/dev/null || break; sleep 1; done
    kill -0 $WP 2>/dev/null || break
    GOT=$(du -sk "$M/blobs" 2>/dev/null | cut -f1)
    echo "  Word writer: $(( ${GOT:-0} / 1024 )) of 466 MB"
  done
  wait $WP || say "Word writer skipped for now (it downloads with your first video)."
fi

rm -rf "$TMP"
say "Everything is ready."
