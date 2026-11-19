# Funnel design references (from Anisia, Nov 19, 2026)

**Her instruction: do not build or redesign anything before looking at every link below.**
Take from both "in my own branding": the structure and what makes each page work, never their branding, text or images.

| # | Link (tracking codes removed) | What it is |
|---|---|---|
| 1 | https://aiwithtiff.com | Tiffany Pellot's site (mentor). Webinar/registration page style |
| 2 | https://aiwithtiff.com/confirmation | Tiff's post-registration confirmation page |
| 3 | https://thelacelocker.store/ | The Lace Locker store home page |
| 4 | https://thelacelocker.store/webinar/confirmed | The Lace Locker webinar confirmation page |

Status: **not yet viewed.** This session's network blocks both sites. Open them in a session on the
"nail-enhancement-questionnaire" environment (open internet), or from screenshots Anisia sends.

## Steps for the session that views them
1. Open all 4 pages (desktop + phone width). Note for each: platform, section order, what the form asks,
   what the confirmation page asks people to do next (calendar, community, video, share), and countdown/date display.
2. Write a short comparison for Anisia (what to borrow from each, in her brand) and get her OK.
3. Only then update `funnel-site/public/` (index.html, thanks.html, style.css). Keep the 16 tests passing and
   re-run the browser check (`node test/dev-server.mjs`).

## Her brand (saved earlier in content-made-easy/brand/)
- Name: "Anisia the Nail Bawse"; accent pink **#F4A6C4**; font style **Bold Caps**
- Her own button words: "Save my seat", "Come build with me", "Learn the system", "Let's get to work"
- Sign-offs: "You are the asset. Build accordingly." · "Beyond the service. Beyond the title." · "Build from what you know."
- Current funnel pages use a placeholder plum/pink palette: swap to her brand when redesigning.
