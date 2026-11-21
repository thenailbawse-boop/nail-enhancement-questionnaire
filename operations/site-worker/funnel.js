// The Nail Bawse "Build Your AI Agent" class page for thenailbawse.com (served by the thenailbawse-official Worker).
// Built by build.py from funnel-site/public (pass the commit that holds dist/).
// Routes: /webinar, /webinar/thanks, /registration (redirect), /webinar-assets/*, /api/events, /api/register, /api/ics. Sign-ups go to the same D1 "signups" table.
// Page files live in the repo at a pinned commit (dist/). The first request fetches each one, checks its
// SHA-256 against MANIFEST, and keeps it in the NB_WEBINAR KV namespace; later requests are served from KV.
const MANIFEST = {"index":{"f":"index.html","t":"text/html; charset=utf-8","s":"1b7a3b77cb11173887cc8bb18a48f798133e0e26d7a7c4944edcd839772ec491"},"thanks":{"f":"thanks.html","t":"text/html; charset=utf-8","s":"b05817b037587b1a8585893b5f0b948aaad2ace45dd646342301accffc785479"},"funnel.css":{"f":"funnel.css","t":"text/css; charset=utf-8","s":"76bbd3479a2fcf1fb942321f528076b594d4ea5f290e5c9d3d75aff210399fa2"},"app.js":{"f":"app.js","t":"text/javascript; charset=utf-8","s":"0e1f956c8ab65267560c34d6271f6f563913906b40952c76e5349eef70be8de5"},"card.js":{"f":"card.js","t":"text/javascript; charset=utf-8","s":"381d20f6ffe37b61faccd6995f920c76bfe9f4fdc0ed6ab47c10742e932c2ca9"}};
const COMMIT = "PENDING";
const SOURCES = ["https://cdn.jsdelivr.net/gh/thenailbawse-boop/nail-enhancement-questionnaire@" + COMMIT + "/operations/site-worker/dist/",
                 "https://raw.githubusercontent.com/thenailbawse-boop/nail-enhancement-questionnaire/" + COMMIT + "/operations/site-worker/dist/"];
const TITLE = "Build Your AI Agent";
const TZ = "America/Los_Angeles";

async function sha256(s) { return Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s)))).map(b => b.toString(16).padStart(2, "0")).join(""); }
async function load(name, env) {
  const m = MANIFEST[name], key = name + ":" + m.s;
  let body = await env.NB_WEBINAR.get(key);
  if (body !== null) return body;
  for (const base of SOURCES) {
    try {
      const r = await fetch(base + m.f, { cf: { cacheTtl: 300 } });
      if (!r.ok) continue;
      const t = await r.text();
      if (await sha256(t) !== m.s) continue;
      await env.NB_WEBINAR.put(key, t);
      return t;
    } catch (e) { /* try the next source */ }
  }
  return null;
}
async function asset(name, env) {
  const m = MANIFEST[name], body = await load(name, env);
  if (body === null) return new Response("This page is updating. Please refresh in a minute.", { status: 503, headers: { "content-type": "text/plain; charset=utf-8", "retry-after": "30" } });
  const html = m.t.startsWith("text/html");
  return new Response(body, { headers: { "content-type": m.t, "cache-control": html ? "no-store" : "public, max-age=3600",
    "x-content-type-options": "nosniff", "referrer-policy": "strict-origin-when-cross-origin" } });
}
function json(obj, status) { return new Response(JSON.stringify(obj), { status: status || 200, headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" } }); }
function evFor(t, h) { return { id: "s" + t, title: TITLE, startUtc: new Date(t).toISOString(), tz: TZ, durationMin: Math.round(h.DUR / 60000), description: "", joinUrl: h.ZOOM }; }
function tFromId(id, h) {
  const m = /^s(\d{12,14})$/.exec(String(id || "")); if (!m) return null;
  const t = Number(m[1]); const n = h.nextSession(t - h.DUR + 1); return n === t ? t : null;
}

export async function funnel(request, env, h) {
  const key = h.key, method = request.method;
  if (key === "/registration") { const u = new URL(request.url); return Response.redirect("https://" + h.APEX + "/webinar" + u.search, 301); }
  if ((key === "/webinar" || key === "/webinar/thanks") && (method === "GET" || method === "HEAD")) return asset(key === "/webinar" ? "index" : "thanks", env);
  if (h.path.startsWith("/webinar-assets/") && method === "GET") { const n = h.path.slice(16); return MANIFEST[n] ? asset(n, env) : null; }
  if (key === "/api/events" && method === "GET") {
    const id = new URL(request.url).searchParams.get("id");
    if (id) { const t = tFromId(id, h); return t ? json({ event: evFor(t, h) }) : json({ error: "Session not found." }, 404); }
    const next = h.nextSession(Date.now());
    return json({ events: next ? [evFor(next, h)] : [] });
  }
  if (key === "/api/ics" && method === "GET") {
    const t = tFromId(new URL(request.url).searchParams.get("id"), h);
    if (!t) return new Response("Not found", { status: 404 });
    return new Response(h.icsText(t), { headers: { "content-type": "text/calendar; charset=utf-8", "content-disposition": 'attachment; filename="build-your-ai-agent.ics"', "cache-control": "no-store" } });
  }
  if (key === "/api/register" && method === "POST") {
    let b; try { b = await request.json(); } catch (e) { return json({ error: "Something went wrong. Please try again." }, 400); }
    if (String(b.company || "").trim()) return json({ ok: true, eventId: "waitlist", emailed: false });
    const name = String(b.firstName || "").trim().slice(0, 80);
    const email = String(b.email || "").trim().toLowerCase().slice(0, 200);
    const fields = {};
    if (!name) fields.firstName = "Please add your first name.";
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(email)) fields.email = "Please check your email address.";
    if (Object.keys(fields).length) return json({ error: "Please fix the highlighted fields.", fields: fields }, 400);
    const t = b.eventId && b.eventId !== "waitlist" ? tFromId(b.eventId, h) : h.nextSession(Date.now());
    if (b.eventId && b.eventId !== "waitlist" && !t) return json({ error: "That date has passed. Refresh the page to see the next one." }, 400);
    const optin = b.optIn === false || b.optIn === "false" ? 0 : 1;
    await env.DB.prepare("INSERT INTO signups (created_at, source, first_name, email, marketing_opt_in, session_start_utc, user_agent) VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(source, email, session_start_utc) DO UPDATE SET first_name = excluded.first_name, marketing_opt_in = MAX(marketing_opt_in, excluded.marketing_opt_in)")
      .bind(new Date().toISOString(), "webinar", name, email, optin, t ? new Date(t).toISOString() : "tba", String(request.headers.get("user-agent") || "").slice(0, 300)).run();
    return json({ ok: true, eventId: t ? "s" + t : "waitlist", emailed: false });
  }
  return null;
}
