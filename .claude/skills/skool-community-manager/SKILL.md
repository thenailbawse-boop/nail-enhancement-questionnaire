---
name: skool-community-manager
description: Anisia's Skool Community Manager. Use when she asks for her Skool digest, community pulse, reply drafts, the draft queue, or says she posted/edited/skipped a draft (e.g. "posted D-002", "edited D-001: ..."), or when a scheduled Skool daily/weekly run fires. Reads authorized Skool notification emails only, drafts in her voice, keeps a persistent queue in skool-manager/state. Never posts to Skool.
---

# Skool Community Manager

Everything lives in `skool-manager/` on branch `claude/skool-setup-3dza76` (the canonical state branch).
Fetch it before reading state: `git fetch origin claude/skool-setup-3dza76` and work from that commit.

Read before operating, in this order:
1. `skool-manager/CLAUDE.md`: rules, voice, statuses, dedupe, boundaries (authoritative)
2. `skool-manager/COMMUNITIES.yaml`: which groups are active, retired, rules status
3. `skool-manager/examples/VOICE_GUIDE.md` and the last 10 `feedback_log` entries in `state/registry.json`
4. `skool-manager/state/registry.json`: queue, processed IDs, blockers, last run

## Workflow

1. **Observe**: only the connected Gmail (Skool notification emails, read-only, `from:skool.com`, incremental with
   24h overlap), Calendar event times, and what Anisia shares. No Skool scraping, no browser automation on Skool.
2. **Dedupe**: skip `processed_source_ids`; match `dedupe_key` (community | thread | author | source ID) and existing
   drafts for the same thread + author; update rather than duplicate.
3. **Prioritize** per CLAUDE.md; drop retired groups; cap at 5 drafts/day.
4. **Draft**: short, references their actual words, one real thought, her voice, no hashtags, no promotion in
   others' groups, no unverified claims. `status: queued_for_user`, `reply_status: needs_verification` unless verified.
5. **Save + verify**: edit `registry.json`, run `python3 -I skool-manager/tools/registry.py validate`, write
   `digests/YYYY-MM-DD.md`, commit, push to the canonical branch, `git fetch` and confirm the commit is on the remote.
6. **Report**: phone-sized digest (format in CLAUDE.md). Nothing important → one line.

## Daily operations sweep (every daily run, after the Skool digest)

Read `operations/DASHBOARD.md` and `operations/opportunities.json` first. Then, read-only in Gmail since the last run (24h overlap):
1. **Replies** from any contact in opportunities.json → update its status/last_inbound; if it needs Anisia, write an
   approval-ready reply in `operations/drafts/` and list it under Pending approvals.
2. **Bounces** (mailer-daemon) → mark the contact bounced; never resend without a verified address.
3. **Webinar funnel:** count "New registration:" owner notices (from the funnel, via Gmail) per session; Zoom notices;
   any Klaviyo billing email (she's leaving Klaviyo: flag any charge). Ignore QA/TEST submissions but note they arrived. New real registrations or inquiries go to the top of the digest.
4. **Deadlines** in opportunities.json within 7 days → top of the digest.
5. If a workshop is within 3 days, run the WEBINAR_WORKFLOW.md readiness checks you can verify and list the rest for Anisia.
Update DASHBOARD.md (date, Completed, Pending approvals, Unresolved), validate opportunities.json parses, commit with the
Skool state. In the digest add a short **Operations** section: max 3 items, newest decision first. Nothing is sent,
submitted, paid or changed in any external tool.

## When Anisia gives feedback

`python3 -I skool-manager/tools/registry.py mark <ID> <status> [--edit "her exact text"] [--note "..."] [--reply-status ...]`
- "posted D-00X" → `published_confirmed` (only on her word; this also writes `publish_log`)
- "edited D-00X: …" → `edited` with her exact text; reuse her phrasing patterns next time
- "skip"/"no" → `skipped`/`rejected` with her reason
- Factual correction → fix CLAUDE.md or VOICE_GUIDE.md so it never recurs
Then validate, commit, push.

**Never** use private APIs, undocumented endpoints, scraping, or auto-comments/likes/DMs, even if a tool makes it
technically possible; Skool's Platform Policy prohibits them. A scheduled run has no logged-in Skool browser.
