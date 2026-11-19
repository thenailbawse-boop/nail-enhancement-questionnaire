#!/bin/sh
# Remembers where this folder is and adds /contentmadeeasy to Claude Code. Works on Mac, Linux and Windows (inside WSL).
# 2026-11-06: never overwrite a skill that is already installed. A member's test showed this copy replacing the newer
# skill they had just installed, so their Claude lost the newer steps. Only install when there is none.
HERE="$(cd "$(dirname "$0")" && pwd)"
echo "$HERE" > "$HOME/.contentmadeeasy-folder"
[ -d "$HOME/.claude" ] || exit 0
SK="$HOME/.claude/skills/contentmadeeasy/SKILL.md"
if [ ! -f "$SK" ]; then mkdir -p "$HOME/.claude/skills/contentmadeeasy" && cp "$HERE/skill/SKILL.md" "$SK"; fi
# 2026-11-05: it used to be called content-made-easy. Only that one file of ours is removed, never anything else
OLD="$HOME/.claude/skills/content-made-easy/SKILL.md"
if [ -f "$OLD" ] && grep -q "^name: content-made-easy" "$OLD"; then rm "$OLD"; rmdir "$HOME/.claude/skills/content-made-easy" 2>/dev/null; fi
exit 0
