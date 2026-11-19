# Cloud scheduled tasks (saved Nov 19, 2026)

These run in Anthropic's cloud, in the `nail-enhancement-questionnaire` cloud environment. They do **not** need
your laptop, Chrome, or a hotspot. Each run starts a fresh cloud session, reads this repo, writes the digest,
pushes state, and sends a push notification to the Claude app.

| Task | ID | Schedule (Pacific) | Next run |
|---|---|---|---|
| Skool daily digest | `trig_016VeEqLr3qRb4NtyJgcZkf1` | Every day 8:41 AM (digest ready by 9) | Thu Nov 20, 8:41 AM |
| Skool weekly review | `trig_01U5D5Pm5u69tBSnBxFpmhGL` | Sundays 4:42 PM (ready by 5) | Sun Nov 22, 4:42 PM |

Times are set a few minutes before the hour on purpose: on-the-hour runs queue behind everyone else's.

## Known limit: connectors

Both tasks were created from a session that had no Gmail connection, so they currently run **without** Gmail or
Calendar. Until that changes, each run records "Gmail not connected" once and stays quiet. Fix (one time):
connect Gmail at claude.ai/customize/connectors, then in a **new** session on this repo say
**"finish Skool setup"**. That session (which will hold Gmail) recreates both tasks with Gmail attached,
deletes these two, and updates this table. Alternatively, add Gmail to each task in the claude.ai routines screen.

## The saved prompts

The exact prompts are stored on the tasks themselves (readable with `get_trigger`). Summary:
- **Daily**: fetch canonical branch → read CLAUDE.md + state → Gmail `from:skool.com` since last run (24h overlap,
  read-only) → dedupe → ≤5 drafts queued → `digests/YYYY-MM-DD.md` → validate, commit, push, confirm → digest message.
- **Weekly**: same sources plus Calendar times → priorities, stale drafts, verified classes/replays, relationships,
  ≤1 post idea checked against publish history and rules → `digests/weekly-YYYY-MM-DD.md` → one workflow improvement.

## Rate and cost controls

One daily run, one weekly run, no polling. Incremental reads only. ≤5 drafts/day. No paid tools, no credit top-ups,
no settings changes. No Skool write actions ever (Skool Platform Policy).
