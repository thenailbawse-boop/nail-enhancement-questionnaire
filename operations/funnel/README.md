# The simple funnel: one link, one room, one sequence

**Why it felt overwhelming:** every workshop needed a new list, a new confirmation flow, new dates typed into emails,
and old flows switched off. That's 4+ things to remember per event, and the reason confirmations ended up hand-sent.

**The fix:** make the workshop *evergreen*. Same day, same time, same Zoom link, every time. Then nothing in the
funnel ever needs editing, and you just show up.

```
Instagram (comment/DM "BAWSE") ─┐
Link in bio ────────────────────┤
Wix site button ────────────────┼──►  ONE signup page  ──►  ONE Klaviyo list  ──►  ONE flow (3 emails)  ──►  Workshop
Your own Skool community ───────┤     (Klaviyo-hosted,      "Workshop              confirm → day-of →        (recurring
Email signature ────────────────┘      free, no wiring)     Registrants"          follow-up                  Zoom link)
```

## The 5 pieces (that's the whole system)
| # | Piece | What it is | Changes per workshop? |
|---|---|---|---|
| 1 | **One signup link** | Klaviyo's hosted signup page for the list (you already used one in October) | Never |
| 2 | **One list** | "Workshop Registrants" (reuse the November list WhYD4m, just rename it) | Never |
| 3 | **One recurring Zoom** | A recurring meeting, Thursdays 8:00 PM PT, 40 min (stays inside free Zoom's limit) | Never |
| 4 | **One flow, 3 emails** | Confirmation → "Tonight" reminder → Friday follow-up (`emails.md`) | Never |
| 5 | **One DM reply** | What "BAWSE" sends back: the signup link (`social.md`) | Never |

**Turn off:** the old confirmation flow RqqwPF and every older event flow. Old lists stay as records; nobody new joins them.
The Wix "Next Free Webinar Notification" form gets replaced by a button to the signup link (no Wix→Klaviyo wiring to maintain).

## Your weekly job after setup
Show up Thursday at 8. That's it. The daily run watches for problems and drafts anything that needs your voice.

## How the flow times itself (Klaviyo settings)
- Trigger: **added to list** "Workshop Registrants"
- Email 1: immediately
- Time delay: **until the next Thursday, 3:00 PM PT** (Klaviyo time delays can be limited to chosen days of the week). Email 2.
- Time delay: **until Friday, 10:00 AM PT**. Email 3.
- Someone who signs up on Thursday after 3 PM still has the link from Email 1, and gets the reminder the next week.
- Flow filter: "has not been in this flow in the last 30 days", so repeat sign-ups don't get the series twice in a month.
_I'll double-check these settings against your actual Klaviyo account once it's connected._

## One-time setup (≈30 min, or I do it once Klaviyo is connected)
1. Zoom: schedule a **recurring** meeting, Thursdays 8:00 PM PT, no fixed end date. Copy the link.
2. Klaviyo → Lists: rename WhYD4m to "Workshop Registrants". Open its **signup page** and paste the copy from `page.md`. Copy the page link.
3. Klaviyo → Flows: create a list-triggered flow with the 3 emails in `emails.md` (paste in the Zoom link).
4. Send yourself a test: sign up with `thenailbawse+test@gmail.com`. I'll check Gmail and confirm all 3 emails look right.
5. Switch the flow to **Live**. Set RqqwPF and older event flows to **Manual/Off**.
6. Put the signup link in: IG bio, the BAWSE reply, the Wix button, your email signature.
