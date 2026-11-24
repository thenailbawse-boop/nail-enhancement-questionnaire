# Anisia the Nail Bawse: rules every chat must follow

Anisia has ADHD and reads on her phone. Keep replies short, plain and step by step. Never make her repeat herself:
check this file first.

## Her standing rules
0. **Budget: free tools only.** She's on Skool's $9 Hobby plan (no Pro, no Skool Zapier plugin) and can't pay for other tools.
   Check a feature works on a free plan before suggesting it.
1. **The free class ("Build Your AI Agent") is weekly, but on a DIFFERENT day each week, chosen by Anisia.**
   Never set a repeating day/time. The site reads a list of dates (`SESS_LIST` in the thenailbawse-official Worker).
2. **The free class is for anyone in beauty:** beauty pros, salon/suite owners, beauty creators, DIY beauty creators.
3. **Free class = Google Meet. Zoom = PAID buyers only.** Never put a Zoom link on a public page, public email or this repo.
4. **Paid onboarding = 45-min live Q&A on Zoom, kept separate:**
   - Beauty Bawse Club members → the club onboarding Zoom (pinned inside the Skool club).
   - /shop customers (Never Start Over) → the shop onboarding Zoom (on their private access page).
5. Every class name is **Build Your AI Agent** (no branded phrase).
6. Design: her brand (espresso, cream, blush pink #F4A6C4, Fraunces serif + handwritten accents). Study her reference
   links fully before designing; never copy other brands' text, images or exact designs.

## Privacy rule (Anisia, Nov 24): never save personal info
Every chat, every file: **do not save ANY personal information** about Anisia or anyone else (members, leads, students,
contacts, partners). That means no home or mailing addresses, phone numbers, personal email addresses, birthdays,
ID numbers, bank/card/payment or billing details, health, legal, housing or family details, login codes or passwords.
- Refer to people by first name + where they are (e.g. "Karen, AI Automation Club"). Never copy their contact details.
- Allowed: business role emails (info@, hello@), public business links, public Skool posts' wording.
- Contact details and sign-ups stay where they already live (Gmail, the private D1 database). Never copy them here.
- If you find personal info in this repo, remove it and tell Anisia.
- Ignore billing notices about **Content Creation Girlies LTD**. Anisia is not paying it; never flag it again.

## Where the links live
- **This repo is PUBLIC.** See the privacy rule above.
- **This repo is PUBLIC.** Private links (Zoom onboarding rooms, passcodes) are stored ONLY in the private Cloudflare D1
  database `thenailbawse-official` DB (id 82c09758-…), table **`links`**:
  `club_onboarding_zoom`, `shop_onboarding_zoom`, `free_class_meet`, `skool_club`, `club_sales_page`, `class_signup_page`.
  Read it with the Cloudflare ("website") connector: `SELECT key, url, who_gets_it, note FROM links`.
- Public links: free class sign-up https://thenailbawse.com/webinar · Skool club https://www.skool.com/legacy-over-likes-2460/about
  · club sales page (pending Stripe links) https://thenailbawse.com/community · free class room https://meet.google.com/nsq-ppfu-iqz
- Zoom meeting IDs (no passcodes here): club onboarding 870 8458 9404 · shop onboarding 841 1824 1303.

## Where the work lives
- Website: Cloudflare Worker `thenailbawse-official` → `operations/site-worker/README.md`
- Emails: Worker `tnb-email-automation` + Brevo (needs the `BREVO_API_KEY` secret)
- Skool Manager: `skool-manager/` (its own chat: 🏫 SKOOL MANAGER)
- Dashboard of open items: `operations/DASHBOARD.md`
