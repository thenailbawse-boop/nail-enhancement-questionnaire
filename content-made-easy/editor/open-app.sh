#!/bin/zsh
# Opens Content Made Easy in its own window, and turns the editor on first if it is off (after a restart, say).
# Run by the "Content Made Easy" icon in the Dock. With CME_NOOPEN=1 it only turns the editor on (the at-login starter).
# It never posts, sends or deletes anything.
#   CME_PORT     port to use (default 8790)
#   CME_PROFILE  Chrome profile folder to open it in, like "Profile 1" (optional)
#   CME_DRYRUN=1 do everything except open the window, and say what it would open
cd "$(dirname "$0")" || exit 1
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
PORT="${CME_PORT:-8790}"
URL="http://127.0.0.1:$PORT"
up() { curl -s -m 2 -o /dev/null "$URL/api/setup"; }

if ! up; then
  PY="$HOME/vibe-editing/.venv/bin/python"
  if [ ! -x "$PY" ]; then echo "NOT SET UP: open Claude and type /contentmadeeasy"; exit 2; fi
  if lsof -nP -iTCP:"$PORT" -sTCP:LISTEN -t >/dev/null 2>&1; then echo "PORT BUSY: another app is using $PORT"; exit 3; fi
  PORT="$PORT" nohup "$PY" server.py < /dev/null >> server.log 2>&1 &
  for i in {1..40}; do up && break; /bin/sleep 1; done
  if ! up; then echo "DID NOT START. Last lines of server.log:"; tail -5 server.log; exit 4; fi
  echo "STARTED $URL"
fi

[ -n "$CME_NOOPEN" ] && { echo "ON $URL"; exit 0; }
PAGE="$URL/?app=1"
[ -n "$CME_DRYRUN" ] && { echo "WOULD OPEN $PAGE${CME_PROFILE:+ in $CME_PROFILE}"; exit 0; }
if [ -d "/Applications/Google Chrome.app" ]; then
  # its own window: no tabs, no address bar, so it can't get lost among other tabs
  if [ -n "$CME_PROFILE" ]; then open -na "Google Chrome" --args --profile-directory="$CME_PROFILE" --app="$PAGE"
  else open -na "Google Chrome" --args --app="$PAGE"; fi
else
  open "$PAGE"
fi
echo "OPENED $PAGE"
