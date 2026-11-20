# thenailbawse.com Worker

Your domain is served by the Cloudflare Worker **thenailbawse-official** (D1 database binding `DB`).

- `worker.original.js`: the live code as of Nov 20, 2026, before the class page. **Backup for rollback.**
- `funnel.template.js` + `build.py` → `funnel.js` (the Build Your AI Agent page, packed from `funnel-site/public`)
  and `worker.new.js` (the live code with 6 small edits from `patch.json`).
- Routes added: `/webinar` (new page), `/webinar/thanks`, `/registration` → `/webinar`, `/webinar-assets/*`,
  `/api/events`, `/api/register`, `/api/ics`. Sign-ups still go to the D1 `signups` table (source `webinar`).
- Class schedule comes from the Worker: Thursdays 8:00 PM PT (`SESS_START`…`SESS_END`), Zoom link `ZOOM`.

Rebuild after changing the page: `python3 build.py`, then redeploy both modules (worker.js + funnel.js).
