// Request handlers. Storage, mail and clock are passed in, so tests run without Netlify or Gmail.
// deps = { store: {get,set,list,del}, mailer: {send}, env, now: () => ms }
import {
  upcoming, publicEvent, validateRegistration, validateEventInput, emailKey, newEventId, safeEqual,
  unsubToken, dueReminder, buildIcs, toCsv, eventEnd,
} from "./core.mjs";
import { confirmationEmail, waitlistEmail, reminderEmail, announcementEmail, ownerNotice } from "./emails.mjs";

const json = (status, body, headers = {}) =>
  new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json", "cache-control": "no-store", ...headers } });
const html = (status, body) =>
  new Response(`<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>The Nail Bawse</title><body style="font-family:Helvetica,Arial,sans-serif;max-width:520px;margin:48px auto;padding:0 16px;color:#2A1A2E;line-height:1.55">${body}</body>`,
    { status, headers: { "content-type": "text/html; charset=utf-8" } });

const ANNOUNCE_LIMIT = 450; // stays under Gmail's ~500 recipients/day

function ctxFor(deps, email) {
  const site = (deps.env.SITE_URL || "").replace(/\/$/, "");
  const secret = deps.env.UNSUB_SECRET || deps.env.ADMIN_KEY || "";
  return {
    siteUrl: site ? `${site}/` : "",
    mailingAddress: deps.env.MAILING_ADDRESS || "",
    unsubUrl: site && secret && email ? `${site}/api/unsubscribe?e=${encodeURIComponent(email)}&t=${unsubToken(email, secret)}` : "",
  };
}
const isAdmin = (req, deps) => safeEqual(req.headers.get("x-admin-key"), deps.env.ADMIN_KEY);
const loadEvents = async (deps) => (await deps.store.get("events")) || [];
const saveEvents = (deps, events) => deps.store.set("events", events);

async function readBody(req) {
  const type = req.headers.get("content-type") || "";
  if (type.includes("application/json")) return { body: await req.json(), isForm: false };
  const fd = await req.formData();
  return { body: Object.fromEntries(fd.entries()), isForm: true };
}

// ---------- /api/events ----------
export async function eventsHandler(req, deps) {
  const url = new URL(req.url);
  const events = await loadEvents(deps);
  const now = deps.now();

  if (req.method === "GET") {
    if (url.searchParams.get("admin") === "1") {
      if (!isAdmin(req, deps)) return json(401, { error: "Wrong admin key." });
      const withCounts = [];
      for (const ev of [...events].sort((a, b) => new Date(b.startUtc) - new Date(a.startUtc))) {
        const keys = await deps.store.list(`reg/${ev.id}/`);
        withCounts.push({ ...ev, registrations: keys.length, past: eventEnd(ev).getTime() <= now });
      }
      const subs = await deps.store.list("sub/");
      return json(200, { events: withCounts, subscribers: subs.length });
    }
    const id = url.searchParams.get("id");
    if (id) {
      const ev = events.find((e) => e.id === id);
      return ev ? json(200, { event: publicEvent(ev) }) : json(404, { error: "Session not found." });
    }
    return json(200, { events: upcoming(events, now).map(publicEvent) });
  }

  if (!isAdmin(req, deps)) return json(401, { error: "Wrong admin key." });
  const input = await req.json();

  if (req.method === "DELETE") {
    const next = events.filter((e) => e.id !== input.id);
    if (next.length === events.length) return json(404, { error: "Session not found." });
    await saveEvents(deps, next);
    return json(200, { ok: true });
  }

  const v = validateEventInput(input);
  if (!v.ok) return json(400, { error: "Please fix the highlighted fields.", fields: v.errors });

  if (req.method === "POST") {
    const ev = { id: newEventId(v.value.startUtc), ...v.value, createdAt: new Date(now).toISOString(), announcedAt: null };
    await saveEvents(deps, [...events, ev]);
    return json(201, { event: ev });
  }
  if (req.method === "PUT") {
    const i = events.findIndex((e) => e.id === input.id);
    if (i < 0) return json(404, { error: "Session not found." });
    events[i] = { ...events[i], ...v.value, updatedAt: new Date(now).toISOString() };
    await saveEvents(deps, events);
    return json(200, { event: events[i] });
  }
  return json(405, { error: "Method not allowed." });
}

// ---------- /api/register ----------
export async function registerHandler(req, deps) {
  if (req.method !== "POST") return json(405, { error: "Method not allowed." });
  const { body, isForm } = await readBody(req);
  const back = (eventId) => new Response(null, { status: 303, headers: { location: `/thanks.html?e=${encodeURIComponent(eventId || "waitlist")}` } });

  // Honeypot: real people never fill the hidden "company" field. Pretend success.
  if (body.company) return isForm ? back(body.eventId) : json(200, { ok: true });

  const v = validateRegistration(body);
  if (!v.ok) return json(400, { error: "Please fix the highlighted fields.", fields: v.errors });
  const r = v.value;
  const now = deps.now();
  const nowIso = new Date(now).toISOString();
  const ekey = emailKey(r.email);

  let ev = null;
  if (r.eventId !== "waitlist") {
    ev = upcoming(await loadEvents(deps), now).find((e) => e.id === r.eventId);
    if (!ev) return json(400, { error: "That session has already happened or was removed. Please pick another." });
  }

  // Subscriber record = your email list (replaces Klaviyo)
  const subKey = `sub/${ekey}`;
  const sub = (await deps.store.get(subKey)) || { email: r.email, createdAt: nowIso, unsubscribed: false, optIn: false };
  sub.firstName = r.firstName; sub.lastName = r.lastName; sub.phone = r.phone || sub.phone || "";
  sub.role = r.role || sub.role || ""; sub.updatedAt = nowIso;
  if (r.optIn) { sub.optIn = true; sub.unsubscribed = false; }
  sub.source = sub.source || r.source || ""; sub.ref = sub.ref || r.ref || "";
  await deps.store.set(subKey, sub);

  let emailed = false;
  const ctx = ctxFor(deps, r.email);
  if (!ev) {
    await deps.store.set(`wait/${ekey}`, { ...r, registeredAt: nowIso });
    try { await deps.mailer.send({ to: r.email, ...waitlistEmail(r, ctx) }); emailed = true; } catch (e) { console.error("waitlist mail failed", e.message); }
  } else {
    const regKey = `reg/${ev.id}/${ekey}`;
    const existing = await deps.store.get(regKey);
    const reg = existing
      ? { ...existing, ...r, updatedAt: nowIso }
      : { ...r, registeredAt: nowIso, sent: {} };
    const lastConfirm = reg.sent?.confirm ? new Date(reg.sent.confirm).getTime() : 0;
    if (now - lastConfirm > 10 * 60 * 1000) {
      try {
        const msg = confirmationEmail(ev, reg, ctx);
        await deps.mailer.send({
          to: r.email, ...msg,
          attachments: [{ filename: "invite.ics", content: buildIcs(ev, { siteUrl: ctx.siteUrl }), contentType: "text/calendar; charset=utf-8; method=PUBLISH" }],
        });
        reg.sent = { ...(reg.sent || {}), confirm: nowIso };
        emailed = true;
      } catch (e) { console.error("confirmation mail failed", e.message); }
    } else emailed = true; // confirmation already sent in the last 10 minutes
    await deps.store.set(regKey, reg);
  }

  const owner = deps.env.OWNER_EMAIL || deps.env.GMAIL_USER;
  if (owner) {
    try { await deps.mailer.send({ to: owner, ...ownerNotice(ev, r), replyTo: r.email }); } catch (e) { console.error("owner notice failed", e.message); }
  }
  return isForm ? back(ev?.id) : json(200, { ok: true, eventId: ev?.id || "waitlist", emailed });
}

// ---------- scheduled reminders ----------
export async function runReminders(deps) {
  const now = deps.now();
  const events = await loadEvents(deps);
  const log = [];
  for (const ev of events) {
    const end = eventEnd(ev).getTime();
    if (now < new Date(ev.startUtc).getTime() - 26 * 3600e3 || now > end + 73 * 3600e3) continue;
    for (const key of await deps.store.list(`reg/${ev.id}/`)) {
      const reg = await deps.store.get(key);
      if (!reg) continue;
      const kind = dueReminder(ev, reg, now);
      if (!kind) continue;
      if (kind === "followup") {
        const sub = await deps.store.get(`sub/${emailKey(reg.email)}`);
        if (sub?.unsubscribed) { reg.sent = { ...reg.sent, followup: "skipped-unsubscribed" }; await deps.store.set(key, reg); continue; }
      }
      try {
        await deps.mailer.send({ to: reg.email, ...reminderEmail(kind, ev, reg, ctxFor(deps, reg.email)) });
        reg.sent = { ...reg.sent, [kind]: new Date(now).toISOString() };
        await deps.store.set(key, reg);
        log.push(`${kind} → ${ev.id}`);
      } catch (e) { console.error(`${kind} mail failed`, e.message); }
    }
  }
  return log;
}

// ---------- /api/announce (admin) ----------
export async function announceHandler(req, deps) {
  if (req.method !== "POST") return json(405, { error: "Method not allowed." });
  if (!isAdmin(req, deps)) return json(401, { error: "Wrong admin key." });
  if (!deps.env.MAILING_ADDRESS) return json(400, { error: "Add MAILING_ADDRESS in Netlify first. US law (CAN-SPAM) requires a postal address (a PO box is fine) in announcement emails." });
  const { id, force } = await req.json();
  const events = await loadEvents(deps);
  const ev = events.find((e) => e.id === id);
  if (!ev) return json(404, { error: "Session not found." });
  if (ev.announcedAt && !force) return json(409, { error: `Already announced on ${ev.announcedAt}. Nothing sent.` });

  let sent = 0, skipped = 0;
  for (const key of await deps.store.list("sub/")) {
    if (sent >= ANNOUNCE_LIMIT) break;
    const sub = await deps.store.get(key);
    if (!sub || !sub.optIn || sub.unsubscribed) { skipped++; continue; }
    if (await deps.store.get(`reg/${ev.id}/${emailKey(sub.email)}`)) { skipped++; continue; } // already registered
    try { await deps.mailer.send({ to: sub.email, ...announcementEmail(ev, sub, ctxFor(deps, sub.email)) }); sent++; }
    catch (e) { console.error("announce mail failed", e.message); }
  }
  ev.announcedAt = new Date(deps.now()).toISOString();
  await saveEvents(deps, events);
  return json(200, { ok: true, sent, skipped, capped: sent >= ANNOUNCE_LIMIT });
}

// ---------- /api/registrants (admin CSV) ----------
export async function registrantsHandler(req, deps) {
  if (!isAdmin(req, deps)) return json(401, { error: "Wrong admin key." });
  const url = new URL(req.url);
  const id = url.searchParams.get("id");
  const cols = ["firstName", "lastName", "email", "phone", "role", "source", "ref", "goal", "optIn", "registeredAt"];
  let rows = [], name = "subscribers";
  if (id) {
    name = `registrants-${id}`;
    for (const k of await deps.store.list(`reg/${id}/`)) { const r = await deps.store.get(k); if (r) rows.push(r); }
  } else {
    for (const k of await deps.store.list("sub/")) {
      const s = await deps.store.get(k);
      if (s) rows.push({ ...s, registeredAt: s.createdAt, optIn: s.optIn && !s.unsubscribed });
    }
  }
  return new Response(toCsv(rows, cols), {
    headers: { "content-type": "text/csv; charset=utf-8", "content-disposition": `attachment; filename="${name}.csv"`, "cache-control": "no-store" },
  });
}

// ---------- /api/unsubscribe ----------
export async function unsubscribeHandler(req, deps) {
  const url = new URL(req.url);
  const email = (url.searchParams.get("e") || "").trim().toLowerCase();
  const t = url.searchParams.get("t") || "";
  const secret = deps.env.UNSUB_SECRET || deps.env.ADMIN_KEY || "";
  if (!email || !secret || !safeEqual(t, unsubToken(email, secret))) return html(400, "<h1>That link didn't work</h1><p>Reply to any of my emails and I'll take you off the list.</p>");
  const key = `sub/${emailKey(email)}`;
  const sub = (await deps.store.get(key)) || { email };
  sub.unsubscribed = true; sub.optIn = false; sub.unsubscribedAt = new Date(deps.now()).toISOString();
  await deps.store.set(key, sub);
  return html(200, "<h1>You're unsubscribed</h1><p>You won't get emails about future free sessions. If you're registered for one that's coming up, you'll still get its reminders.</p>");
}

// ---------- /api/ics (public calendar file, no join link) ----------
export async function icsHandler(req, deps) {
  const id = new URL(req.url).searchParams.get("id");
  const ev = (await loadEvents(deps)).find((e) => e.id === id);
  if (!ev) return json(404, { error: "Session not found." });
  return new Response(buildIcs(ev, { includeJoinLink: false, siteUrl: deps.env.SITE_URL || "" }), {
    headers: { "content-type": "text/calendar; charset=utf-8", "content-disposition": `attachment; filename="session.ics"` },
  });
}
