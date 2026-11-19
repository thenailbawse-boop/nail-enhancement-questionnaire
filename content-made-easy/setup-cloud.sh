#!/bin/bash
# Gets Content Made Easy ready on a Linux cloud machine (a Claude Code cloud session, started from the Claude
# app on a phone), so videos can be edited with no laptop. Safe to run again: it skips what is already there.
# Run it from anywhere: bash setup-cloud.sh
# Every download comes from PyPI, GitHub releases or Hugging Face, on the cloud machine's own internet,
# so none of it uses the phone's data.
set -u
REPO="$(cd "$(dirname "$0")" && pwd)"
ED="$REPO/editor"
B="$HOME/.local/bin"
KITDIR="$HOME/vibe-editing"
VENV="$KITDIR/.venv"
PY="$VENV/bin/python"
mkdir -p "$B" "$KITDIR"
say() { echo "  $1"; }
fail() { echo "STOPPED: $1"; exit 1; }

# 1. Python 3.12 and the video packages (the versions the editor was tested with)
command -v uv >/dev/null 2>&1 || [ -x "$B/uv" ] || pip install -q --user uv==0.12.21 || fail "could not get uv"
UV="$(command -v uv || echo "$B/uv")"
if ! "$PY" -c "import cv2, numpy, PIL, requests, fontTools, faster_whisper, onnxruntime, rapidocr_onnxruntime, imageio_ffmpeg" >/dev/null 2>&1; then
  say "Setting up the video tools (about 2 minutes)..."
  [ -x "$PY" ] || "$UV" venv -q --python 3.12 "$VENV" || fail "could not set up Python"
  "$UV" pip install -q --python "$PY" \
    numpy==2.5.4 opencv-python-headless==5.1.0.95 pillow==13.0.0 requests==2.34.2 fonttools==4.67.0 \
    faster-whisper==1.2.1 av==15.1.0 ctranslate2==4.8.3 onnxruntime==1.31.0 tokenizers==0.23.3 huggingface-hub==2.2.0 \
    imageio-ffmpeg==0.8.1 rapidocr-onnxruntime==1.4.4 yt-dlp==2026.10.26 || fail "could not install the video packages"
fi

# 2. ffmpeg 9 (the editor uses its newer options; the machine's own ffmpeg is too old) and yt-dlp, on the PATH
ln -sf "$("$PY" -c 'import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())')" "$B/ffmpeg"
ln -sf "$VENV/bin/yt-dlp" "$B/yt-dlp"
command -v ffprobe >/dev/null 2>&1 || { apt-get install -y -q ffmpeg >/dev/null 2>&1 || fail "could not get ffprobe"; }
"$B/ffmpeg" -version | head -1

# 3. The sound cleaner (DeepFilterNet 0.5.6). Videos still work without it.
if ! "$B/deep-filter" --version >/dev/null 2>&1; then
  say "Getting the sound cleaner..."
  curl -fsSL --retry 3 -m 300 -o "$B/deep-filter" \
    "https://github.com/Rikorose/DeepFilterNet/releases/download/v0.5.6/deep-filter-0.5.6-x86_64-unknown-linux-musl" \
    && chmod +x "$B/deep-filter" || { rm -f "$B/deep-filter"; say "Sound cleaner skipped (videos still work)."; }
fi

# 4. The editing kit (fonts, caption styles, face finder), kept in this repo's kit folder, then the editor's fixes on top
if [ ! -f "$KITDIR/plugins/vibe-editing/skills/caption-clips/presets/spice.json" ]; then
  [ -d "$REPO/kit/plugins" ] || fail "the editing kit isn't in this repo yet (the kit folder)"
  cp -R --update=none "$REPO/kit/." "$KITDIR/" || fail "could not copy the editing kit"
fi
cp -R "$ED/kit-fixes/." "$KITDIR/" || fail "could not add the kit fixes"

# 5. The speech model that writes down your words (466 MB, from Hugging Face)
if ! find "$HOME/.cache/huggingface/hub/models--Systran--faster-whisper-small.en/snapshots" -name model.bin 2>/dev/null | grep -q .; then
  say "Getting the word writer, 466 MB..."
  HF_HUB_DISABLE_XET=1 "$PY" -c "from faster_whisper import WhisperModel; WhisperModel('small.en', device='cpu', compute_type='int8')" \
    || say "Word writer skipped for now (it downloads with the first video)."
fi

# 6. Your brand and the edits you copied live in this repo, so every new session remembers them
link() {   # link NAME TARGET: NAME becomes a link to TARGET, keeping anything already saved in NAME
  if [ -d "$1" ] && [ ! -L "$1" ]; then cp -R --update=none "$1/." "$2/" 2>/dev/null; rm -rf "$1"; fi
  ln -sfn "$2" "$1"
}
mkdir -p "$REPO/brand" "$REPO/my-copied-edits" "$ED/jobs"
link "$HOME/Content Made Easy Brand" "$REPO/brand"
link "$ED/jobs/_styles" "$REPO/my-copied-edits"
echo "$ED" > "$HOME/.contentmadeeasy-folder"
echo "SET UP"
