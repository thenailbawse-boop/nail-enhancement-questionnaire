# Free Live Session funnel (The Nail Bawse)

One page on your domain that always shows your next free session, whatever the topic, day or time.
No Klaviyo, no monthly fees.

## What it does
- **Public page (`/`)**: shows the next session (or lets people pick if several are posted). Collects first/last name,
  email, mobile (optional), what they do, how they heard, what they want help with, and opt-in for future sessions.
  No session posted yet → "Notify me" list.
- **Emails from your Gmail, automatically:** confirmation with Zoom link + calendar invite → 24-hour reminder →
  "starting in about an hour" → next-day thank-you (with replay link if you add one). A copy of every registration goes to you.
- **Your email list:** everyone who opts in. One button announces a new session to them (with unsubscribe link).
- **Admin page (`/admin.html`)**, works on your phone: post/edit/delete sessions, see registration counts, copy a
  share link, download registrants or your whole list as CSV.
- **Share links:** `thenailbawse.com/?src=instagram` records where people came from. `?s=<session id>` opens a specific date.

## One-time setup (≈20 minutes, free)
1. **Gmail app password** (so the site can send email as you):
   Google Account → Security → turn on **2-Step Verification** → search "App passwords" → create one named "Funnel".
   Copy the 16-letter password. Never paste it into a chat.
2. **Netlify** (free): sign up at netlify.com with GitHub → "Add new site" → "Import from Git" → pick
   `nail-enhancement-questionnaire` → branch `main` (after the funnel is merged there) → **Base directory: `funnel-site`** → Deploy.
3. **Environment variables** (Netlify → Site configuration → Environment variables):
   | Name | Value |
   |---|---|
   | `GMAIL_USER` | thenailbawse@gmail.com |
   | `GMAIL_APP_PASSWORD` | the 16-letter app password |
   | `ADMIN_KEY` | a long passphrase only you know (you type it once on the admin page) |
   | `SITE_URL` | https://thenailbawse.com |
   | `MAILING_ADDRESS` | a postal address or PO box. Required by US law in announcement emails, so the "email my list" button stays off without it |
   | `FROM_NAME` (optional) | how your name shows in inboxes; default "Anisia \| The Nail Bawse" |
   Then **Deploys → Trigger deploy**.
4. **Your domain**: Netlify → Domain management → Add a domain → follow the DNS steps it shows at your registrar.
   HTTPS turns on automatically.
5. **Test**: open `/admin.html`, post a test session with your own Zoom link, register with
   `thenailbawse+test@gmail.com`, and confirm the email + invite arrive. Delete the test session.

## Every week
Tell Claude the topic, date and time (and Zoom link), or post it yourself on `/admin.html`. Share the page link.
Gmail sends up to ~500 emails a day, which covers this comfortably at your current size.

## For developers
`npm test` runs the suite (also runs on every Netlify deploy, so a broken change won't go live).
`node test/dev-server.mjs` previews everything locally at http://localhost:8788 (admin key `dev-key`, emails printed, not sent).
Storage: Netlify Blobs store `funnel` (`events`, `reg/<event>/<email-hash>`, `sub/<email-hash>`, `wait/<email-hash>`).
