#!/usr/bin/env bash
# Builds CREATOR_RESET_BUILD.zip (project source only — no build output, no node_modules).
# Usage: tools/package.sh [output-directory]
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-$HERE/..}"
mkdir -p "$OUT"
OUT="$(cd "$OUT" && pwd)"
cd "$HERE/.."
rm -f "$OUT/CREATOR_RESET_BUILD.zip"
zip -qr "$OUT/CREATOR_RESET_BUILD.zip" iphone-operator \
  -x "iphone-operator/web-tests/node_modules/*" "iphone-operator/Core/.build/*" "iphone-operator/build/*" \
     "*/xcuserdata/*" "*.DS_Store" "*/__pycache__/*"
echo "$OUT/CREATOR_RESET_BUILD.zip"
