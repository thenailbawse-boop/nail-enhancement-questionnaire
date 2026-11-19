#!/usr/bin/env python3
"""Claude Code runs this in the background after opening the page. It waits, using almost nothing, for the person to
type something to Claude on the page, prints it and ends. Ending is what wakes the chat. While it waits, the page's dot is green."""
import fcntl, json, os, sys, time

SAVED = os.path.join(os.path.expanduser("~"), "Content Made Easy Brand")
ASKS, SEEN, LOCK = (os.path.join(SAVED, x) for x in ("claude-asks.jsonl", "claude-asks.seen", "claude-asks.lock"))
LISTEN, BUSY = os.path.join(SAVED, "claude-listening.json"), os.path.join(SAVED, "claude-working.json")
os.makedirs(SAVED, exist_ok=True)
me, parent = os.getpid(), os.getppid()


def off():
    try:
        if json.load(open(LISTEN)).get("pid") == me:
            os.remove(LISTEN)
    except (OSError, ValueError):
        pass


def take():
    """Each ask goes to one chat, once, even with two chats open."""
    with open(LOCK, "a") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        try:
            lines = open(ASKS, encoding="utf-8").read().split("\n")[:-1]
        except OSError:
            return []
        try:
            seen = int(open(SEEN).read() or 0)
        except (OSError, ValueError):
            seen = 0
        if seen > len(lines):
            seen = 0
        if seen < len(lines):
            open(SEEN, "w").write(str(len(lines)))
        return lines[seen:]


json.dump({"pid": me, "since": time.time()}, open(LISTEN, "w"))
if os.path.exists(BUSY):
    os.remove(BUSY)
try:
    t0 = time.time()
    while time.time() - t0 < 8 * 3600:
        if os.getppid() != parent:      # the chat that started this is gone, so nobody would hear the answer
            sys.exit(0)
        new = take()
        if new:
            json.dump({"at": time.time()}, open(BUSY, "w"))
            print("The person typed this to you on the Content Made Easy page. It is about their video. Do it, tell them on the page, then run this listener again.\n")
            print("\n".join(new))
            sys.exit(0)
        time.sleep(1)
    print("Nothing came in for 8 hours, so the dot on the page is off now.")
finally:
    off()
