# Never Start Over: The AI Business Starter System

Sales page and delivery for The Nail Bawse's Black Friday product. Live on thenailbawse.com (Worker `thenailbawse-official`).

**This repository is public.** The paid product, the private access link, the promo code and the setup steps for Stripe, Zapier and Brevo are **not** in this repo. They live in `private/` (git-ignored) and in Anisia's Google Drive.

## What's here

| File | What it is |
|---|---|
| `shop/shop.body.html` | Sales page copy and layout for `/shop` |
| `shop/shop.css` | Sales page styles (Candy Blush, Lemon Cream, Sky Blue, White, Espresso; Playfair Display + Inter) |
| `shop/shop.template.js` | Worker module source: `/shop`, `/shop/buy`, and the private product route |
| `build_shop.py` | Builds `../site-worker/shop.js` and checks that no forbidden words reach the public page |

## How it works

- `/shop` shows the price for today's **Pacific** date: before Nov 27 it says the sale opens Friday, Nov 27–30 shows $97, and from Dec 1 it shows $197. No promo code is ever printed on the page.
- `/shop/buy` sends the buyer to the Stripe Payment Link for today's date. The links are Worker variables (`NSO_LINK_BF`, `NSO_LINK_FULL`), so changing them needs no code change. Until they are set, the button returns to `/shop#price`.
- After payment, Stripe redirects to the private product page. The product HTML is in the KV namespace `nailbawse-never-start-over` (binding `NSO_KV`, key `hub.html`); the path segment is the Worker variable `NSO_TOKEN`.
- Preview another date's price on the sales page: `/shop?asof=2026-11-28`. This only changes what the page shows; checkout always uses the real date.

## Rebuild and deploy

1. `python3 operations/never-start-over/build_shop.py` (writes `operations/site-worker/shop.js`).
2. `python3 operations/site-worker/build.py <funnel commit>` (keeps `worker.new.js` in sync; patch includes the `shop` import and dispatch).
3. Upload `worker.js` + `funnel.js` + `shop.js` with bindings `DB`, `NB_WEBINAR`, `NSO_KV`, and the plain-text variables `NSO_TOKEN`, `NSO_LINK_BF`, `NSO_LINK_FULL`.
