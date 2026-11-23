# Operating dashboard: The Nail Bawse
_Updated Mon Nov 23, 2026 by Claude. The daily run (8:41 AM PT) refreshes this file. Full detail: AUDIT-2026-11-19.md_

## ✅ Completed (verified)
- Nov 21: removed 5 personal email addresses from public repo files (opportunities.json, dashboard); older git history still has them
- Nov 21: Brevo account validated (free plan)
- Nov 21: Zoom = paid onboarding only (45-min live Q&A): club room 870 8458 9404 (pin in Skool), shop room 841 1824 1303 (on buyers' private page). Free class stays on Google Meet
- Nov 21: next class **Tue Nov 24, 5 PM PT on Google Meet, 60 min**. Rule: a different day each week, set by Anisia (no repeating schedule)
- Nov 20: **Elevate RTP talk submitted** by Anisia (results by Dec 21)
- Nov 20: funnel rebuilt (v2) to match the 2 examples' craft, themed as her salon front desk; 16 tests pass, browser-checked
- Rule: every webinar is called **Build Your AI Agent** (no branded phrase)
- Nov 20: **class page LIVE at thenailbawse.com/webinar** (/registration redirects there). Sign-ups save to the site's Cloudflare database; tested end to end, test row removed. How it's built: `site-worker/README.md`
- Public website set: **thenailbawse.com** (all docs and the Elevate proposal updated)
- Nov 19: MUSE Hair Fest replied with fee $350 (sent) · A Place Called Home follow-up (sent)
- New funnel built and tested end to end in a browser (`funnel-site/`, 16 automated tests pass); not deployed yet
- Skool manager live: Gmail connected, daily + Sunday scheduled tasks bound to the Gmail session, first live digest done
- Systems audit of Klaviyo / Zoom / Wix / Skool / outreach from Gmail evidence (17 findings)
- Reusable webinar workflow with a test protocol (`WEBINAR_WORKFLOW.md`), now evergreen
- Simple funnel designed: 1 link, 1 list, 1 recurring Zoom, 3 evergreen emails, all copy written (`funnel/`)
- Relationship tracker rebuilt from sent mail: 32 contacts, replies and bounces (`opportunities.json`)
- Social Club "No self-promotion" rule recorded so drafts never repeat the Oct 29 removal

## 👑 Pending your approval / decision (top first)
1. ~~Funnel setup on Netlify~~ not needed: the page runs on your existing Cloudflare site
2. **Klaviyo (you're leaving it):** export your contacts, turn off Auto-upgrade, downgrade to free before the next bill (~Nov 27)
3. **Class page is live** at thenailbawse.com/webinar. Sign-ups are saved but no confirmation email goes out yet (the page shows the Zoom link + calendar instead). Say "send my sign-ups" anytime to get the list
4. **Postal address or PO box** for the funnel's announcement emails (US law requires one)
6. Skool D-001…D-005 reply drafts (in the Skool digest)

## 🔌 Connections (re-checked Nov 19 late, read-only)
| Connector | Status |
|---|---|
| Gmail | ✅ Working |
| Google Calendar | ✅ Working (thenailbawse@gmail.com) |
| Google Drive | ✅ Working, but signed in as a second personal Google account (sees files shared from thenailbawse) |
| Zoom | ✅ Working (weekly meeting renamed "Build Your AI Agent \| The Nail Bawse™" on Nov 20; same join link) |
| Wix | ✅ Working (4 sites, incl. "The Nail Bawse") |

All connected. Manage them at claude.ai/customize/connectors.

## ⚠️ Unresolved issues
- Zoom: Dec 21 and Dec 28 class dates were deleted today (11:29 AM PT); weekly series otherwise runs Mondays 5 PM PT through January. Confirm that was intended and that the class page doesn't list those dates
- Weekly class is booked 5:00–5:45 PM on a us05 (free-style) Zoom link: free meetings stop at 40 min
- Funnel not deployed yet (needs the Gmail app password, Netlify site and domain, all things only you can create)
- Klaviyo paid plan + Auto-upgrade still on until you change them; next charge is likely around Nov 27
- Old Klaviyo contacts: export them before downgrading, then send me the CSV and I'll add an import to the funnel
- Zoom: confirm your plan (free meetings stop at 40 min; the funnel defaults to 40)
- 7 bounced pitch addresses need correct contacts before any resend (new Nov 23: Santiago Canyon College, Chaffey WTI)
