# Funnel design references (from Anisia, Nov 19, 2026)

**Her instruction: do not build or redesign anything before looking at every link below.**
Take from both "in my own branding": the structure and what makes each page work, never their branding, text or images.

| # | Link (tracking codes removed) | What it is |
|---|---|---|
| 1 | https://aiwithtiff.com | Tiffany Pellot's site (mentor). Webinar/registration page style |
| 2 | https://aiwithtiff.com/confirmation | Tiff's post-registration confirmation page |
| 3 | https://thelacelocker.store/ | The Lace Locker store home page |
| 4 | https://thelacelocker.store/webinar/confirmed | The Lace Locker webinar confirmation page |

Status: **all 4 viewed Nov 19, 2026** at desktop (1366px) and phone (390px) width. ✅ 1 ✅ 2 ✅ 3 ✅ 4
Phone screenshots: `screenshots/key-*.png`. **Waiting for Anisia's OK before any change to `funnel-site/`.**

## What each page does
| | Tiff: sign-up (1) | Tiff: confirmation (2) | Lace Locker: sign-up (3) | Lace Locker: confirmation (4) |
|---|---|---|---|---|
| Platform | GoHighLevel (LeadConnector) | GoHighLevel | Custom site, own code | Custom site |
| Order | Headline → date box + form → countdown → problem → 3 things you'll learn → 4-step demo → "is this for you" checklist → host → final date + countdown + button | Date → "You're IN" → Skool button → 3 numbered next steps → paid toolkit offer | Date ticker → countdown → headline → calendar-page date → button → video → DM quotes → 5 lessons → before/after → "for you if" → paid community + Black Friday price → teacher story | Big "locked in" → hall pass with date/time → share to story → Zoom ID → add to calendar → waitlist |
| Form | First name, email, phone (all required) + text consent | none | First name, email, phone (optional) + text consent | none |
| Next steps | n/a | 1 check inbox, save Zoom link · 2 add to calendar · 3 bring one task | n/a | Post on your story and tag her · join Zoom · add to calendar (Google, Apple, Outlook) |
| Date / countdown | Full date + ET time; live countdown twice; 3 time zones at bottom | Date at top only | Countdown pinned at top; "NOV 25" calendar page; "live only, no replay" | ET/CT/MT/PT line + "That's 11 PM where you are" (visitor's own time) |

## What to borrow, in Anisia's brand only
(accent #F4A6C4, Bold Caps, her button words; none of their text, art or images)
1. **Form right under the headline**, with the date shown just above it (from 1). Keep our 2 fields: first name + email. Phone optional, later.
2. **Countdown to the next session** near the top and again by the last button (from 1 and 3).
3. **Date in the visitor's own time zone**, plus PT/ET (from 4). Good for an evergreen weekly class.
4. **"What you'll learn" as 3 numbered points** and a short **"This is for you if…"** list (from 1 and 3).
5. **Same button repeated after each section**, using her words: "Save my seat" (from 1).
6. **Thank-you page as 3 numbered steps**: check your inbox · add to calendar (Google/Apple/Outlook) · join the Skool community (from 2 and 4).
7. **A shareable "seat saved" card** in her pink, made for an IG story, with a "tag @thenailbawse" line (idea from 4's hall pass, our own design).
8. Skip for now: video, DM quotes, paid offers on the thank-you page, fake "Jayla just saved a seat" pop-ups.

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
