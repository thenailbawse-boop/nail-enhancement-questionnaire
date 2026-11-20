// The Nail Bawse "Build Your AI Agent" class page for thenailbawse.com (served by the thenailbawse-official Worker).
// Built by build.py from funnel-site/public. Routes: /webinar, /webinar/thanks, /registration (redirect),
// /webinar-assets/*, /api/events, /api/register, /api/ics. Sign-ups go to the same D1 "signups" table.
const ASSETS = __ASSETS__;
const TITLE = "Build Your AI Agent";
const TZ = "America/Los_Angeles";

function bytes(b64) { const s = atob(b64); const u = new Uint8Array(s.length); for (let i = 0; i < s.length; i++) u[i] = s.charCodeAt(i); return u; }
function asset(name, status) {
  const a = ASSETS[name];
  const html = a.t.startsWith("text/html");
  return new Response(a.e === "b64" ? bytes(a.b) : a.b, { status: status || 200, headers: {
    "content-type": a.t, "cache-control": html ? "no-store" : "public, max-age=3600",
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
  if ((key === "/webinar" || key === "/webinar/thanks") && (method === "GET" || method === "HEAD")) return asset(key === "/webinar" ? "index" : "thanks");
  if (h.path.startsWith("/webinar-assets/") && method === "GET") { const n = h.path.slice(16); return ASSETS[n] ? asset(n) : null; }
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
