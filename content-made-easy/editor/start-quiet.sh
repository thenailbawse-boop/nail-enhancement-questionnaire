#!/bin/zsh
# Starts the website without opening anything, for Claude Code. Safe to run when it's already on.
cd "$(dirname "$0")"
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
export PORT=8790
URL="http://127.0.0.1:$PORT"
zsh ./install-skill.sh
if curl -s -m 3 -o /dev/null "$URL/api/setup"; then
  echo "READY $URL"; exit 0
fi
WHO=$(lsof -nP -iTCP:$PORT -sTCP:LISTEN -t 2>/dev/null | head -1)
if [ -n "$WHO" ]; then
  echo "STOPPED: another app is using port $PORT. Quit it, then try again."; exit 1
fi
echo "Getting Content Made Easy ready. The first time takes about 5 minutes."
zsh ./first-run.sh || { echo "STOPPED: setup didn't finish. Read the lines above."; exit 1; }
PY="$HOME/vibe-editing/.venv/bin/python"
if [ ! -x "$PY" ]; then
  echo "STOPPED: something didn't install. Send Tiff a screenshot of this."; exit 1
fi
nohup "$PY" server.py >> server.log 2>&1 &
for i in {1..40}; do
  curl -s -m 2 -o /dev/null "$URL/api/setup" && { echo "READY $URL"; exit 0; }
  /bin/sleep 1
done
echo "STOPPED: it didn't start. The last lines of server.log:"; tail -5 server.log; exit 1
