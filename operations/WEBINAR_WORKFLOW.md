# Reusable webinar workflow: Booked, Burnt Out & Underpaid (any date)

One source of truth per event, one registration path, automatic confirmations, and a test at every step.
**Who does what:** 🤖 = Claude does it (drafts, checks, records) · 👑 = you (publish, send, pay, decide).

## 0. Event record (fill once per event, in `operations/events/YYYY-MM-DD.md`)
Date · start/end (PT) · Zoom link + ID · Klaviyo list ID · confirmation flow ID · slides file · offer/CTA · status.
Every email, post and page copies date/link from this record, never retyped.

## T-14 → T-10 days: set up
| Step | Who | Done when |
|---|---|---|
| Create the event record | 🤖 | File exists with all fields |
| Schedule Zoom (keep live portion ≤40 min unless the plan allows longer) | 👑 | Link + ID in record |
| Klaviyo: new list for this event (or confirm WhYD4m for Nov) | 👑 / 🤖 once connected | List ID in record |
| Point the Wix/Klaviyo signup form at **this** list | 👑 | Test signup lands on the right list |
| Confirmation flow (RqqwPF): trigger = added to this list; date/link updated | 👑 / 🤖 once connected | Test registrant gets the right email |
| **Turn off or archive older event flows** | 👑 | Only one confirmation flow live per event |

## T-10 → T-1: promote
| Step | Who | Done when |
|---|---|---|
| Draft promo copy: IG caption + keyword BAWSE, email, owned-community post | 🤖 | In daily digest for approval |
| Skool: only **your own** community gets the invite. AI Automation Club / The Social Club get value posts, no invite links (Social Club rule 2) | 🤖 drafts / 👑 posts | Logged in publish_log |
| Reminder emails: T-1 day and T-1 hour (Klaviyo flow delays) | 👑 / 🤖 once connected | Test registrant gets both |

## Test protocol (run before announcing, re-run after any edit)
1. Register with a `thenailbawse+test-<date>@gmail.com` address through the public form.
2. 🤖 checks Gmail: confirmation arrived, date/time/link match the event record, Zoom link opens the right meeting ID.
3. Record pass/fail in the event record. **Never call a step "working" without this.**

## Day of
Slides final (Drive) · Zoom opened 10 min early · replay recording on · CTA link tested.

## T+1 → T+7: follow-up
| Step | Who |
|---|---|
| Attendance from Zoom report → tag attendees vs no-shows in Klaviyo | 👑 / 🤖 once both connected |
| Replay + thank-you email (attendees) and "missed it" email (no-shows) | 🤖 drafts / 👑 approves |
| Debrief: registrations, show rate, questions asked, offer responses → event record | 🤖 |
| Move list into general nurture; archive the event flow | 👑 |
