// The Nail Bawse paid onboarding scheduler (Zoom), served by the thenailbawse-official Worker. No outside tools.
// Built by onboarding/build.py. Pages live in the repo at a pinned commit (onboarding/dist/), checked by SHA-256 and
// kept in the NB_WEBINAR KV namespace. Private values (page codes, Zoom links) are read from D1 table `links`:
//   onb_shop_token, onb_club_token, onb_admin_token, shop_onboarding_zoom, club_onboarding_zoom.  Never put them in this file.
// Routes: /onboarding/<code>  (booking page for shop or club buyers, or the manager page for Anisia)
//         /api/onboarding/slots | book | ics | admin/list | admin/add | admin/remove
// Slots: D1 table onboarding_slots (one row per room per time). A time offered to both rooms can only be booked once.
const MANIFEST = __MANIFEST__;
const COMMIT = "__COMMIT__";
const SOURCES = ["https://cdn.jsdelivr.net/gh/thenailbawse-boop/nail-enhancement-questionnaire@" + COMMIT + "/operations/site-worker/onboarding/dist/",
                 "https://raw.githubusercontent.com/thenailbawse-boop/nail-enhancement-questionnaire/" + COMMIT + "/operations/site-worker/onboarding/dist/"];
const DUR = 45 * 60000, TZ = "America/Los_Angeles";
const LABEL = { shop: "Never Start Over", club: "Beauty Bawse Club" };

async function sha256(s) { return Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s)))).map(b => b.toString(16).padStart(2, "0")).join(""); }
async function page(name, env) {
  const m = MANIFEST[name], key = "onb:" + name + ":" + m.s;
  let body = await env.NB_WEBINAR.get(key);
  if (body === null) {
    for (const base of SOURCES) {
      try { const r = await fetch(base + m.f); if (!r.ok) continue; const t = await r.text(); if (await sha256(t) !== m.s) continue; await env.NB_WEBINAR.put(key, t); body = t; break; } catch (e) {}
    }
  }
  if (body === null) return new Response("This page is updating. Please refresh in a minute.", { status: 503, headers: { "content-type": "text/plain; charset=utf-8" } });
  return new Response(body, { headers: { "content-type": "text/html; charset=utf-8", "cache-control": "no-store", "x-robots-tag": "noindex, nofollow", "referrer-policy": "no-referrer", "x-content-type-options": "nosniff" } });
}
function json(o, s) { return new Response(JSON.stringify(o), { status: s || 200, headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" } }); }
async function cfg(env) {
  const r = await env.DB.prepare("SELECT key, url FROM links WHERE key IN ('onb_shop_token','onb_club_token','onb_admin_token','shop_onboarding_zoom','club_onboarding_zoom')").all();
  const c = {}; for (const row of (r.results || [])) c[row.key] = row.url; return c;
}
function who(c, k) {
  if (!k) return null;
  if (k === c.onb_shop_token) return "shop";
  if (k === c.onb_club_token) return "club";
  if (k === c.onb_admin_token) return "admin";
  return null;
}
// Pacific wall-clock date + time -> UTC ms (handles PST/PDT)
function ptToUtc(date, time) {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(date || ""), n = /^(\d{1,2}):(\d{2})$/.exec(time || "");
  if (!m || !n) return null;
  const want = Date.UTC(+m[1], +m[2] - 1, +m[3], +n[1], +n[2]);
  let t = want;
  for (let i = 0; i < 3; i++) {
    const p = Object.fromEntries(new Intl.DateTimeFormat("en-US", { timeZone: TZ, hourCycle: "h23", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" }).formatToParts(new Date(t)).map(x => [x.type, x.value]));
    const seen = Date.UTC(+p.year, +p.month - 1, +p.day, +p.hour, +p.minute);
    t += want - seen;
  }
  return t;
}
function ics(start, zoom, label) {
  const d = x => new Date(x).toISOString().replace(/[-:]/g, "").replace(/\.\d{3}/, "");
  return ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//The Nail Bawse//Onboarding//EN", "BEGIN:VEVENT", "UID:" + start + "-onboarding@thenailbawse.com", "DTSTAMP:" + d(Date.now()),
    "DTSTART:" + d(start), "DTEND:" + d(start + DUR), "SUMMARY:Live onboarding with Anisia (" + label + ")", "LOCATION:" + zoom, "DESCRIPTION:Join on Zoom: " + zoom + "\\nWait in the waiting room until Anisia lets you in.", "URL:" + zoom, "END:VEVENT", "END:VCALENDAR"].join("\r\n");
}

export async function onboarding(request, env, h) {
  const path = h.path, key = h.key, method = request.method, url = new URL(request.url);
  const isPage = path.startsWith("/onboarding/"), isApi = key.startsWith("/api/onboarding/");
  if (!isPage && !isApi) return null;
  const c = await cfg(env);
  if (isPage) {
    const role = who(c, path.slice(12).replace(/\/+$/, ""));
    if (!role || (method !== "GET" && method !== "HEAD")) return null;
    return page(role === "admin" ? "manage" : "onboard", env);
  }
  let body = {};
  if (method === "POST") { try { body = await request.json(); } catch (e) { return json({ error: "Something went wrong. Please try again." }, 400); } }
  const role = who(c, method === "POST" ? body.k : url.searchParams.get("k"));
  if (!role) return json({ error: "This link isn't valid." }, 404);
  const now = new Date().toISOString(), soon = new Date(Date.now() + 2 * 3600000).toISOString();

  if (key === "/api/onboarding/slots" && method === "GET" && role !== "admin") {
    const r = await env.DB.prepare("SELECT id, start_utc FROM onboarding_slots s WHERE room = ? AND booked_email IS NULL AND start_utc > ? AND NOT EXISTS (SELECT 1 FROM onboarding_slots b WHERE b.start_utc = s.start_utc AND b.booked_email IS NOT NULL) ORDER BY start_utc LIMIT 60").bind(role, soon).all();
    return json({ room: role, label: LABEL[role], slots: (r.results || []).map(x => ({ id: x.id, start: x.start_utc })) });
  }
  if (key === "/api/onboarding/book" && method === "POST" && role !== "admin") {
    const name = String(body.name || "").trim().slice(0, 80), email = String(body.email || "").trim().toLowerCase().slice(0, 200), id = Number(body.id);
    if (!name || !/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(email) || !id) return json({ error: "Please add your first name and a valid email." }, 400);
    const u = await env.DB.prepare("UPDATE onboarding_slots SET booked_name = ?, booked_email = ?, booked_at = ? WHERE id = ? AND room = ? AND booked_email IS NULL AND start_utc > ? AND NOT EXISTS (SELECT 1 FROM onboarding_slots b WHERE b.start_utc = onboarding_slots.start_utc AND b.booked_email IS NOT NULL)")
      .bind(name, email, now, id, role, now).run();
    if (!u.meta || u.meta.changes !== 1) return json({ error: "Sorry, that time was just taken. Please pick another." }, 409);
    const s = await env.DB.prepare("SELECT start_utc FROM onboarding_slots WHERE id = ?").bind(id).first();
    return json({ ok: true, id: id, start: s.start_utc, zoom: c[role + "_onboarding_zoom"], label: LABEL[role] });
  }
  if (key === "/api/onboarding/ics" && method === "GET" && role !== "admin") {
    const s = await env.DB.prepare("SELECT start_utc FROM onboarding_slots WHERE id = ? AND room = ? AND booked_email IS NOT NULL").bind(Number(url.searchParams.get("id")), role).first();
    if (!s) return new Response("Not found", { status: 404 });
    return new Response(ics(Date.parse(s.start_utc), c[role + "_onboarding_zoom"], LABEL[role]), { headers: { "content-type": "text/calendar; charset=utf-8", "content-disposition": 'attachment; filename="onboarding-with-anisia.ics"', "cache-control": "no-store" } });
  }
  if (role === "admin") {
    if (key === "/api/onboarding/admin/list" && method === "GET") {
      const r = await env.DB.prepare("SELECT id, room, start_utc, booked_name, booked_email, (booked_email IS NULL AND EXISTS (SELECT 1 FROM onboarding_slots b WHERE b.start_utc = s.start_utc AND b.booked_email IS NOT NULL)) AS taken_elsewhere FROM onboarding_slots s WHERE start_utc > ? ORDER BY start_utc, room LIMIT 200").bind(new Date(Date.now() - 3600000).toISOString()).all();
      return json({ slots: r.results || [] });
    }
    if (key === "/api/onboarding/admin/add" && method === "POST") {
      const t = ptToUtc(body.date, body.time);
      if (!t) return json({ error: "Pick a date and a time." }, 400);
      if (t < Date.now()) return json({ error: "That time has already passed." }, 400);
      const rooms = (Array.isArray(body.rooms) ? body.rooms : []).filter(r => r === "shop" || r === "club");
      if (!rooms.length) return json({ error: "Pick who can book this time." }, 400);
      const iso = new Date(t).toISOString();
      for (const r of rooms) await env.DB.prepare("INSERT OR IGNORE INTO onboarding_slots (room, start_utc, created_at) VALUES (?, ?, ?)").bind(r, iso, now).run();
      return json({ ok: true, start_utc: iso });
    }
    if (key === "/api/onboarding/admin/remove" && method === "POST") {
      const u = await env.DB.prepare("DELETE FROM onboarding_slots WHERE id = ? AND booked_email IS NULL").bind(Number(body.id)).run();
      if (!u.meta || u.meta.changes !== 1) return json({ error: "That time is booked, so it can't be removed here." }, 409);
      return json({ ok: true });
    }
  }
  return json({ error: "Not found." }, 404);
}
