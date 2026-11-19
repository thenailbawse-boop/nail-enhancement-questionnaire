#!/bin/bash
# Turns the editor on in a cloud session, with no browser window. Safe to run when it's already on.
REPO="$(cd "$(dirname "$0")" && pwd)"
ED="$REPO/editor"
URL="http://127.0.0.1:8790"
export PATH="$HOME/.local/bin:$PATH"
curl -s -m 3 -o /dev/null "$URL/api/setup" && { echo "READY $URL"; exit 0; }
[ -x "$HOME/vibe-editing/.venv/bin/python" ] && [ -L "$HOME/Content Made Easy Brand" ] || bash "$REPO/setup-cloud.sh" || exit 1
cd "$ED" && PORT=8790 nohup "$HOME/vibe-editing/.venv/bin/python" server.py >> server.log 2>&1 &
for i in $(seq 1 40); do
  curl -s -m 2 -o /dev/null "$URL/api/setup" && { echo "READY $URL"; exit 0; }
  sleep 1
done
echo "STOPPED: it didn't start. The last lines of server.log:"; tail -5 "$ED/server.log"; exit 1
