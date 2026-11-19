# Cloud scheduled tasks

These run in Anthropic's cloud. They do **not** need your laptop, Chrome or a hotspot. Each run wakes the
cloud session that has Gmail and push access to this repo, re-reads state from GitHub, writes the digest, and
pushes. Files, not chat memory, are the source of truth.

| Task | ID | Schedule (Pacific) | Bound to |
|---|---|---|---|
| Skool daily digest | `trig_014tV2sLDsT79g1DEeNoAkmA` | Every day 8:41 AM (ready by 9) | `session_014duir2ozQGSs9NdK6oLi3m` (Gmail connected) |
| Skool weekly review | `trig_01AHfGHdLmKcfzHBEFqVLq8d` | Sundays 4:42 PM (ready by 5) | `session_014duir2ozQGSs9NdK6oLi3m` (Gmail connected) |

State branch for both: `claude/skool-setup-3dza76`.
Times are a few minutes before the hour on purpose: on-the-hour runs queue behind everyone else's.

## Retired tasks

| ID | Why | Status |
|---|---|---|
| `trig_016VeEqLr3qRb4NtyJgcZkf1`, `trig_01U5D5Pm5u69tBSnBxFpmhGL` | fresh-session runs could not push (403) | deleted 2026-11-19 |
| `trig_01BLdrK4D3HLGoYzDunqSY2A` (daily), `trig_01Emj5bb4qQWybFTotLiG3kJ` (weekly) | bound to the old setup session, which had no Gmail | deleted 2026-11-19 with Anisia's permission |

## Verification history

- 2026-11-19: first version ran as fresh cloud sessions. A test run read state correctly, but its **push was
  refused (403)**: fresh routine sessions get no repo write access. Replaced by session-bound tasks.
- 2026-11-19: session-bound daily task fired in the old setup session, read state and pushed (no Gmail there).
- 2026-11-19: "finish Skool setup" in a Gmail-connected session: Gmail read verified (3 Skool emails), new tasks
  created and bound to that session, first live digest pushed.

## The saved prompts

The exact prompts are stored on the tasks themselves (readable with `get_trigger`). Summary:
- **Daily**: fetch state branch → read CLAUDE.md + state → Gmail `from:skool.com` since last run (24h overlap,
  read-only) → dedupe → ≤5 drafts queued → `digests/YYYY-MM-DD.md` → validate, commit, push, confirm → digest message.
- **Weekly**: same sources plus Calendar times → priorities, stale drafts, verified classes/replays, relationships,
  ≤1 post idea checked against publish history and rules → `digests/weekly-YYYY-MM-DD.md` → one workflow improvement.

## Rate and cost controls

One daily run, one weekly run, no polling. Incremental reads only. ≤5 drafts/day. No paid tools, no credit top-ups,
no settings changes. No Skool write actions ever (Skool Platform Policy). Skool tracking links in emails are never opened.
