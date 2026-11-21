// Never Start Over (The AI Business Starter System) for thenailbawse.com, served by the thenailbawse-official Worker.
// Built by operations/never-start-over/build_shop.py from shop.body.html + shop.css. Do not edit shop.js by hand.
// Routes:
//   /shop                      sales page; the price shown follows the Pacific date (no promo code is ever printed)
//   /shop/buy                  sends the buyer to the right Stripe Payment Link for today's Pacific date
//   /never-start-over/<token>  the private product (HTML kept in the NSO_KV namespace, never in this public repo)
// Worker settings this module reads (Cloudflare dashboard > Worker > Settings > Variables and bindings):
//   NSO_TOKEN      the private access path segment          NSO_KV       KV namespace holding "hub.html"
//   NSO_LINK_BF    Stripe Payment Link for the $97 price    NSO_LINK_FULL Stripe Payment Link for $197 (promotion codes on)
const BODY = __BODY__;
const CSS = __CSS__;
const FONTS = '<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&family=Playfair+Display:ital,wght@0,600;0,700;1,600;1,700&display=swap">';
// Pacific time windows (PST is UTC-8 for all of these dates)
const OPEN = Date.UTC(2026, 10, 27, 8, 0, 0);   // Fri Nov 27, 2026 12:00 AM PT: Black Friday opens at $97
const BF_END = Date.UTC(2026, 11, 1, 8, 0, 0);  // Tue Dec 1, 2026 12:00 AM PT: back to $197 on the page
const TITLE = "Never Start Over | The AI Business Starter System | The Nail Bawse™";
const DESC = "Life will pull you out of the chair. Your business shouldn't disappear when it does. AI prompts, a Business Brain dashboard and an AI Front Desk Manager for nail techs and beauty pros.";

function phase(t) { return t < OPEN ? "soon" : (t < BF_END ? "bf" : "full"); }
function asOf(url) {
  const a = url.searchParams.get("asof");
  if (!a || !/^\d{4}-\d{2}-\d{2}$/.test(a)) return null;
  const t = Date.parse(a + "T12:00:00-08:00");
  return isNaN(t) ? null : t;
}
function priceBlock(ph) {
  if (ph === "soon") return '<div class="nso-price"><span class="nso-tag"><span>Black Friday</span> · <span>Opens Fri, Nov 27</span> · <span>12 AM PT</span></span><p class="nso-amt"><s>$197</s>$97</p><span class="nso-btn is-off" aria-disabled="true">Doors open Friday</span><p class="nso-small">4 days only, Nov 27–30.<br>Back to $197 on December&nbsp;1.</p></div>';
  if (ph === "bf") return '<div class="nso-price"><span class="nso-tag"><span>Black Friday</span> · <span>Ends Mon, Nov 30</span> · <span>11:59 PM PT</span></span><p class="nso-amt"><s>$197</s>$97</p><a class="nso-btn" href="/shop/buy">Get Never Start Over · $97</a><p class="nso-small">Instant access on your phone.<br>Back to $197 on December&nbsp;1.</p></div>';
  return '<div class="nso-price"><span class="nso-tag">Instant access</span><p class="nso-amt">$197</p><a class="nso-btn" href="/shop/buy">Get Never Start Over</a><p class="nso-small">Have a promo code? Add it at checkout.</p></div>';
}
function plain(status, text) { return new Response(text, { status: status, headers: { "content-type": "text/plain; charset=utf-8", "cache-control": "no-store" } }); }

export async function shop(request, env, ctx) {
  const key = ctx.key, url = new URL(request.url);
  if (request.method !== "GET" && request.method !== "HEAD") return null;

  if (key === "/shop") {
    const ph = phase(asOf(url) ?? Date.now());
    const body = FONTS + "<style>" + CSS + "</style>" + BODY.split("{{PRICE}}").join(priceBlock(ph)).split("{{SESSION_URL}}").join(ctx.SESSION_URL || "/");
    return ctx.html(ctx.page(TITLE, DESC, "/shop", body), 200, env);
  }

  if (key === "/shop/buy") {
    const ph = phase(Date.now());
    const link = ph === "bf" ? env.NSO_LINK_BF : (ph === "full" ? env.NSO_LINK_FULL : "");
    if (!link || !/^https:\/\/(buy|checkout)\.stripe\.com\//.test(String(link))) return Response.redirect("https://" + url.host + "/shop#price", 302);
    return new Response(null, { status: 302, headers: { "location": String(link), "cache-control": "no-store", "referrer-policy": "strict-origin-when-cross-origin" } });
  }

  if (key === "/never-start-over") return Response.redirect("https://" + url.host + "/shop", 302);
  if (key.indexOf("/never-start-over/") === 0) {
    const seg = ctx.path.split("/")[2] || "";
    const tok = env.NSO_TOKEN ? String(env.NSO_TOKEN) : "";
    if (!tok || seg !== tok || !env.NSO_KV) return ctx.respond("/404.html", 404, env);
    const hub = await env.NSO_KV.get("hub.html");
    if (hub === null) return plain(503, "Your access page is updating. Please refresh in a minute.");
    return new Response(hub, { headers: { "content-type": "text/html; charset=utf-8", "cache-control": "no-store", "x-robots-tag": "noindex, nofollow, noarchive",
      "referrer-policy": "no-referrer", "x-content-type-options": "nosniff", "x-frame-options": "DENY" } });
  }
  return null;
}
