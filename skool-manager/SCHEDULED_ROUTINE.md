# Cloud scheduled tasks (saved Nov 19, 2026)

These run in Anthropic's cloud. They do **not** need your laptop, Chrome or a hotspot. Each run wakes the
cloud session that holds this repo with push access (the setup session), which re-reads state from GitHub,
writes the digest, and pushes. Files, not chat memory, are the source of truth.

| Task | ID | Schedule (Pacific) | Bound to |
|---|---|---|---|
| Skool daily digest | `trig_01BLdrK4D3HLGoYzDunqSY2A` | Every day 8:41 AM (ready by 9) | setup session |
| Skool weekly review | `trig_01Emj5bb4qQWybFTotLiG3kJ` | Sundays 4:42 PM (ready by 5) | setup session |

Times are a few minutes before the hour on purpose: on-the-hour runs queue behind everyone else's.

## Verification history

- 2026-11-19: first version ran as fresh cloud sessions. A manual test run started in the cloud, cloned the repo
  and read state correctly, but its **push was refused (403)**: fresh routine sessions get no repo write access.
  Those two tasks were deleted and replaced by the session-bound tasks above.

## Known limit: Gmail

The setup session started before Gmail was connected, so these runs have **no Gmail** yet; each records the
blocker and stays brief. Fix (one time): connect Gmail at claude.ai/customize/connectors, then open a **new**
Claude Code session on this repo and say **"finish Skool setup"** (steps in CLAUDE.md).

## The saved prompts

The exact prompts are stored on the tasks themselves (readable with `get_trigger`). Summary:
- **Daily**: fetch canonical branch → read CLAUDE.md + state → Gmail `from:skool.com` since last run (24h overlap,
  read-only) → dedupe → ≤5 drafts queued → `digests/YYYY-MM-DD.md` → validate, commit, push, confirm → digest message.
- **Weekly**: same sources plus Calendar times → priorities, stale drafts, verified classes/replays, relationships,
  ≤1 post idea checked against publish history and rules → `digests/weekly-YYYY-MM-DD.md` → one workflow improvement.

## Rate and cost controls

One daily run, one weekly run, no polling. Incremental reads only. ≤5 drafts/day. No paid tools, no credit top-ups,
no settings changes. No Skool write actions ever (Skool Platform Policy).
