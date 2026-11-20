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
