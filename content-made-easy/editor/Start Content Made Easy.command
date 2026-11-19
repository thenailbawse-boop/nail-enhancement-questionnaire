#!/bin/zsh
# Double-click to open Content Made Easy. Close this window to turn it off.
cd "$(dirname "$0")"
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
export PORT=8790
zsh ./install-skill.sh
if curl -s -o /dev/null "http://127.0.0.1:$PORT/api/setup"; then
  open "http://127.0.0.1:$PORT"; exit 0
fi
echo ""
echo "Getting Content Made Easy ready. The first time takes about 5 minutes."
echo "Leave this window open."
echo ""
zsh ./first-run.sh
PY="$HOME/vibe-editing/.venv/bin/python"
if [ ! -x "$PY" ]; then
  echo "  Something didn't install. Send Tiff a screenshot of this window."
  exit 1
fi
"$PY" server.py &
sleep 2
open "http://127.0.0.1:$PORT"
echo ""
echo "Content Made Easy is open in your browser."
echo "Leave this window open while you use it. Close it to turn it off."
wait
