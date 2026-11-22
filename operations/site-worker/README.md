# thenailbawse.com Worker

Your domain is served by the Cloudflare Worker **thenailbawse-official** (D1 database binding `DB`).

- `worker.original.js`: the live code as of Nov 20, 2026, before the class page. **Backup for rollback.**
- `funnel.template.js` + `build.py` → `funnel.js` (the Build Your AI Agent page, packed from `funnel-site/public`)
  and `worker.new.js` (the live code with 6 small edits from `patch.json`).
- Routes added: `/webinar` (new page), `/webinar/thanks`, `/registration` → `/webinar`, `/webinar-assets/*`,
  `/api/events`, `/api/register`, `/api/ics`. Sign-ups still go to the D1 `signups` table (source `webinar`).
- Class schedule comes from the Worker: **Mondays 5:00 PM PT** from Nov 23, 2026 through Mar 8, 2027 (`SESS_START`…`SESS_END`),
  skipping Dec 21 and Dec 28 (`SESS_SKIP`). Zoom link `ZOOM` (Zoom series updated to match). Changed Nov 20, 2026 (was Thursdays 8 PM PT).
- Emails: a separate Worker, `tnb-email-automation`, reads the D1 `signups` table every minute and sends Brevo templates 1–4
  (confirmation, day-before, hour-before, opted-in follow-up). It needs the Worker secret `BREVO_API_KEY`. Don't add email sending to this Worker.

Rebuild after changing the page: `python3 build.py`, then redeploy both modules (worker.js + funnel.js).

## Nov 21, 2026: moved to Tuesdays on Google Meet
- Class: **Tuesdays 5:00–6:00 PM PT** (45 min class + 15 min live Q&A) from Nov 24, 2026 through Mar 9, 2027; skips Dec 22 and Dec 29.
- Room: **Google Meet https://meet.google.com/nsq-ppfu-iqz** (recurring event on thenailbawse@gmail.com's Google Calendar). The `ZOOM` constant
  in both Workers now holds this Meet link (name kept to keep edits small). `DUR` = 60 min.
- Updated live: `thenailbawse-official` (worker.js schedule/text, funnel.js pinned to commit 86205f9) and `tnb-email-automation`
  (link, 60-min calendar slot). The one sign-up (id 3) was moved to the Tuesday Nov 24 session; no emails had gone out.
- Note: `tnb-email-automation` has no `BREVO_API_KEY` secret yet, so it sends nothing until that's added.
- The old Zoom series (Mondays) still exists in Zoom; not used by the site.

## ⚠️ Nov 21, 2026: NO repeating schedule (Anisia's rule)
Classes are weekly, but **on a different day each week, chosen by Anisia**. Never set a recurring day/time.
- The Worker reads a plain list: `const SESS_LIST = [...]` (UTC ms) in worker.js. Add each new date when she gives it
  (patch that one line on Cloudflare, keep all other modules/bindings). With no upcoming date, the page shows "next date drops soon".
- Google Calendar: one single event per class (no recurrence), Meet link https://meet.google.com/nsq-ppfu-iqz.
- Current list: Tue Nov 24, 2026 5:00–6:00 PM PT (1795568400000).

## ⚠️ Nov 21, 2026: Zoom is for PAID buyers only (Anisia's rule)
- Free class = **Google Meet** (meet.google.com/nsq-ppfu-iqz). Never put a Zoom link on a public page, email or the free-class flow.
- Paid onboarding = **45-min live Q&A on Zoom**, two separate rooms (no fixed day; waiting room on):
  - **Beauty Bawse Club members:** Zoom 870 8458 9404 (the old class link, renamed). Delivered only inside Skool (pinned post) and the club welcome email.
    This link was public on the site Nov 20–21, so the waiting room is the gate.
  - **/shop customers (Never Start Over):** Zoom 841 1824 1303. Shown only on the private hub page (NSO_KV `hub.html`, card id="onboarding", heading "Schedule your live onboarding with Anisia").
    Backup of the page before this edit: NSO_KV `hub.backup-2026-11-21.html`. If hub.html is rebuilt from its source, keep that card.

## Onboarding booking pages (live Nov 21, 2026)
- Module `onboarding.js` (built by `onboarding/build.py`, pages pinned at commit 5ca5dde). Routes `/onboarding/<code>` and `/api/onboarding/*`.
- D1 table `onboarding_slots`. Codes live ONLY in D1 `links` (`onb_shop_token`, `onb_club_token`, `onb_admin_token`).
- Anisia adds open times on her manager page (admin code). A time offered to both groups can only be booked once.
- Shop hub card now has "Pick my onboarding time →". Backup before that edit: NSO_KV `hub.backup-2026-11-21b.html`.

## Free resources + digital business card (live Nov 22, 2026)
- Ported from her Wix headless pages. Files: `pages/site/` (resources/*, card/*), module `pages.js` built by `pages/build.py <commit>`.
- Routes come before worker.js's old /resources placeholder. Pinned commit 7b972b7. Headshot: card/anisia.jpg (from funnel-site/public/assets/anisia.jpg).
- To change a page: edit pages/site/..., commit + push, run build.py with that commit, redeploy pages.js (same method as onboarding.js).
