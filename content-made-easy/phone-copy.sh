#!/bin/bash
# Makes a phone-size copy of a finished video (1080x1920, the size Instagram, TikTok and YouTube Shorts show),
# so it downloads fast over a hotspot. The 4K original stays where it is.
# Usage: bash phone-copy.sh "IN.mp4" "OUT.mp4"
set -e
FF="$HOME/.local/bin/ffmpeg"; [ -x "$FF" ] || FF=ffmpeg
"$FF" -v error -y -i "$1" -vf "scale=1080:1920:force_original_aspect_ratio=decrease:flags=lanczos,pad=1080:1920:(ow-iw)/2:(oh-ih)/2" \
  -c:v libx264 -preset medium -crf 21 -maxrate 8M -bufsize 16M -pix_fmt yuv420p -c:a aac -b:a 160k -movflags +faststart "$2"
echo "$(du -h "$2" | cut -f1) $2"
