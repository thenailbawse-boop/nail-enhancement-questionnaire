# Anisia the Nail Bawse: rules every chat must follow

Anisia has ADHD and reads on her phone. Keep replies short, plain and step by step. Never make her repeat herself:
check this file first.

## Her standing rules
0. **Budget: free tools only.** She's on Skool's $9 Hobby plan (no Pro, no Skool Zapier plugin) and can't pay for other tools.
   Check a feature works on a free plan before suggesting it.
   **Payments: use Whop for everything for now** (Stripe sign-in is blocked, Nov 22 2026). The /shop buy button accepts
   whop.com or Stripe links (Worker vars NSO_LINK_BF / NSO_LINK_FULL); none is set yet, so buying is closed.
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

## Where the links live
- **This repo is PUBLIC.** Private links (Zoom onboarding rooms, passcodes) are stored ONLY in the private Cloudflare D1
  database `thenailbawse-official` DB (id 82c09758-…), table **`links`**:
  `club_onboarding_zoom`, `shop_onboarding_zoom`, `free_class_meet`, `skool_club`, `club_sales_page`, `class_signup_page`,
  plus the private booking-page codes `onb_shop_token`, `onb_club_token`, `onb_admin_token` (never write them in this repo).
  Read it with the Cloudflare ("website") connector: `SELECT key, url, who_gets_it, note FROM links`.
- Public links: free class sign-up https://thenailbawse.com/webinar · Skool club https://www.skool.com/legacy-over-likes-2460/about
  · club sales page (pending Stripe links) https://thenailbawse.com/community · free class room https://meet.google.com/nsq-ppfu-iqz
- Zoom meeting IDs (no passcodes here): club onboarding 870 8458 9404 · shop onboarding 841 1824 1303.

## Where the work lives
- Onboarding booking (her own, free): thenailbawse.com/onboarding/<code>. Shop code → /shop buyers (button on their access page),
  club code → pin in Skool, admin code → Anisia's manager page to add open times. Code: `operations/site-worker/onboarding/`.
- Free resources page thenailbawse.com/resources (+ /resources/learn, /free, /sessions) and digital business card
  thenailbawse.com/card: ported from her Wix pages, files in `operations/site-worker/pages/site/`, served by module pages.js
  Restyled Nov 24 to MATCH the main site: /resources pages are body fragments wrapped in worker.js page() (same header/footer/CSS);
  /card is standalone with the NB mark + main-site tokens. Edit `pages/gen.py` (source = `pages/wix-src/`), run it, commit,
  `python3 build.py <commit>`, redeploy pages.js. Worker var CONTACT_EMAIL = hello@thenailbawse.com (fixes site Email links).
- Website: Cloudflare Worker `thenailbawse-official` → `operations/site-worker/README.md`
- Emails: Worker `tnb-email-automation` + Brevo free plan. CONNECTED Nov 22 2026 (secret BREVO_API_KEY set). Sender hello@send.thenailbawse.com
  (domain send.thenailbawse.com authenticated), replies to hello@thenailbawse.com (forwards to her Gmail). Templates 1-3 say Google Meet; club = $37/month.
- Skool Manager: `skool-manager/` (its own chat: 🏫 SKOOL MANAGER)
- Dashboard of open items: `operations/DASHBOARD.md`
