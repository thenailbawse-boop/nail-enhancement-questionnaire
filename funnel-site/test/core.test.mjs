import test from "node:test";
import assert from "node:assert/strict";
import { zonedToUtc, formatWhen, dueReminder, buildIcs, validateRegistration, validateEventInput, toCsv, unsubToken } from "../lib/core.mjs";
import { eventsHandler, registerHandler, runReminders, announceHandler, unsubscribeHandler, registrantsHandler, icsHandler } from "../lib/handlers.mjs";

// ---------- fakes ----------
function fakeDeps(nowIso, env = {}) {
  const data = new Map();
  const outbox = [];
  let now = new Date(nowIso).getTime();
  return {
    data, outbox,
    setNow: (iso) => { now = new Date(iso).getTime(); },
    deps: {
      store: {
        get: async (k) => (data.has(k) ? structuredClone(data.get(k)) : null),
        set: async (k, v) => { data.set(k, structuredClone(v)); },
        del: async (k) => { data.delete(k); },
        list: async (p) => [...data.keys()].filter((k) => k.startsWith(p)),
      },
      mailer: { send: async (m) => { outbox.push(m); } },
      env: { ADMIN_KEY: "secret-key-123", SITE_URL: "https://example.com", OWNER_EMAIL: "owner@example.com", ...env },
      now: () => now,
    },
  };
}
const req = (method, path, body, headers = {}) => new Request(`https://example.com${path}`, {
  method, headers: { "content-type": "application/json", ...headers }, body: body ? JSON.stringify(body) : undefined,
});
const admin = { "x-admin-key": "secret-key-123" };

async function addEvent(f, over = {}) {
  const res = await eventsHandler(req("POST", "/api/events", {
    title: "Price your services with confidence", description: "Bring one service.", date: "2026-12-03", time: "19:00",
    tz: "America/Los_Angeles", durationMin: 40, zoomUrl: "https://us06web.zoom.us/j/123", ...over,
  }, admin), f.deps);
  assert.equal(res.status, 201);
  return (await res.json()).event;
}

// ---------- core ----------
test("time zones: PST and PDT convert correctly", () => {
  assert.equal(zonedToUtc("2026-12-03", "19:00", "America/Los_Angeles"), "2026-12-04T03:00:00.000Z"); // PST -8
  assert.equal(zonedToUtc("2026-07-09", "19:00", "America/Los_Angeles"), "2026-07-10T02:00:00.000Z"); // PDT -7
  assert.equal(zonedToUtc("2026-12-03", "19:00", "America/New_York"), "2026-12-04T00:00:00.000Z");
  assert.match(formatWhen("2026-12-04T03:00:00.000Z", "America/Los_Angeles"), /Thursday, December 3 at 7:00 PM PST/);
});

test("validation: requires name and email, phone optional but sane", () => {
  assert.equal(validateRegistration({ eventId: "x", firstName: "A", email: "a@b.co" }).ok, true);
  const bad = validateRegistration({ eventId: "x", firstName: "", email: "nope", phone: "12" });
  assert.deepEqual(Object.keys(bad.errors).sort(), ["email", "firstName", "phone"]);
  assert.equal(validateRegistration({ eventId: "x", firstName: "A", email: "a@b.co", role: "Hacker" }).value.role, "Other");
  assert.equal(validateEventInput({ title: "", date: "bad", time: "7pm" }).ok, false);
});

test("reminder timing", () => {
  const ev = { startUtc: "2026-12-04T03:00:00.000Z", durationMin: 40 };
  const reg = { registeredAt: "2026-11-20T00:00:00.000Z", sent: {} };
  assert.equal(dueReminder(ev, reg, Date.parse("2026-12-03T03:00:00Z")), "r24");
  assert.equal(dueReminder(ev, { ...reg, sent: { r24: "x" } }, Date.parse("2026-12-04T02:00:00Z")), "r1");
  assert.equal(dueReminder(ev, { ...reg, sent: { r24: "x", r1: "x" } }, Date.parse("2026-12-04T16:00:00Z")), "followup");
  assert.equal(dueReminder(ev, reg, Date.parse("2026-11-25T00:00:00Z")), null);
  // signed up 2h before: no 24h reminder, still gets the 1h one
  const late = { registeredAt: "2026-12-04T01:00:00.000Z", sent: {} };
  assert.equal(dueReminder(ev, late, Date.parse("2026-12-04T01:30:00Z")), "r1");
});

test("calendar file is valid-looking and hides the join link when asked", () => {
  const ev = { id: "e1", title: "Pricing, burnout; and you", description: "Line1\nLine2", startUtc: "2026-12-04T03:00:00.000Z", durationMin: 40, zoomUrl: "https://zoom.us/j/1" };
  const full = buildIcs(ev);
  assert.match(full, /DTSTART:20261204T030000Z\r\nDTEND:20261204T034000Z/);
  assert.match(full, /SUMMARY:Pricing\\, burnout\\; and you/);
  assert.match(full, /zoom\.us\/j\/1/);
  assert.doesNotMatch(buildIcs(ev, { includeJoinLink: false }), /zoom\.us\/j\/1/);
});

test("CSV escapes quotes and blocks formula injection", () => {
  const csv = toCsv([{ a: '=HYPERLINK("x")', b: 'say "hi", ok' }], ["a", "b"]);
  assert.equal(csv, 'a,b\n"\'=HYPERLINK(""x"")","say ""hi"", ok"\n');
});

// ---------- handlers ----------
test("admin key is required to create sessions", async () => {
  const f = fakeDeps("2026-11-20T00:00:00Z");
  const res = await eventsHandler(req("POST", "/api/events", { title: "x", date: "2026-12-03", time: "19:00" }, { "x-admin-key": "wrong" }), f.deps);
  assert.equal(res.status, 401);
});

test("public list hides the Zoom link and past sessions", async () => {
  const f = fakeDeps("2026-11-20T00:00:00Z");
  await addEvent(f);
  await addEvent(f, { date: "2026-11-10", title: "Old one" });
  const body = await (await eventsHandler(req("GET", "/api/events"), f.deps)).json();
  assert.equal(body.events.length, 1);
  assert.equal(body.events[0].zoomUrl, undefined);
  assert.equal(JSON.stringify(body).includes("zoom.us"), false);
});

test("registration: stores, emails confirmation with invite + owner notice, dedupes", async () => {
  const f = fakeDeps("2026-11-20T00:00:00Z");
  const ev = await addEvent(f);
  const person = { eventId: ev.id, firstName: "Mia", lastName: "Lee", email: "Mia@Example.com", phone: "(323) 555-0100", role: "Nail tech", optIn: true };
  const res = await registerHandler(req("POST", "/api/register", person), f.deps);
  assert.equal(res.status, 200);
  assert.equal((await res.json()).emailed, true);
  assert.equal(f.outbox.length, 2);
  const [confirm, owner] = f.outbox;
  assert.equal(confirm.to, "mia@example.com");
  assert.match(confirm.subject, /You're in/);
  assert.match(confirm.text, /zoom\.us\/j\/123/);
  assert.equal(confirm.attachments[0].filename, "invite.ics");
  assert.match(confirm.text, /unsubscribe\?e=mia%40example\.com&t=/);
  assert.equal(owner.to, "owner@example.com");
  assert.match(owner.text, /Phone: \(323\) 555-0100/);
  // same person again within 10 minutes: no second confirmation, still one registration
  await registerHandler(req("POST", "/api/register", person), f.deps);
  assert.equal(f.outbox.filter((m) => m.to === "mia@example.com").length, 1);
  assert.equal([...f.data.keys()].filter((k) => k.startsWith(`reg/${ev.id}/`)).length, 1);
  assert.equal([...f.data.keys()].filter((k) => k.startsWith("sub/")).length, 1);
});

test("registration rejects bad input, past sessions, and silently drops bots", async () => {
  const f = fakeDeps("2026-11-20T00:00:00Z");
  const ev = await addEvent(f);
  assert.equal((await registerHandler(req("POST", "/api/register", { eventId: ev.id, firstName: "", email: "x" }), f.deps)).status, 400);
  const bot = await registerHandler(req("POST", "/api/register", { eventId: ev.id, firstName: "B", email: "b@b.co", company: "spam inc" }), f.deps);
  assert.equal(bot.status, 200);
  assert.equal(f.outbox.length, 0);
  f.setNow("2026-12-10T00:00:00Z");
  assert.equal((await registerHandler(req("POST", "/api/register", { eventId: ev.id, firstName: "C", email: "c@c.co" }), f.deps)).status, 400);
});

test("waitlist signup when nothing is scheduled", async () => {
  const f = fakeDeps("2026-11-20T00:00:00Z");
  const res = await registerHandler(req("POST", "/api/register", { eventId: "waitlist", firstName: "W", email: "w@w.co", optIn: true }), f.deps);
  assert.equal(res.status, 200);
  assert.match(f.outbox[0].subject, /on the list/);
  assert.equal((await f.deps.store.get([...f.data.keys()].find((k) => k.startsWith("sub/")))).optIn, true);
});

test("plain HTML form post (no JavaScript) redirects to the thank-you page", async () => {
  const f = fakeDeps("2026-11-20T00:00:00Z");
  const ev = await addEvent(f);
  const fd = new URLSearchParams({ eventId: ev.id, firstName: "N", email: "n@n.co" });
  const res = await registerHandler(new Request("https://example.com/api/register", { method: "POST", headers: { "content-type": "application/x-www-form-urlencoded" }, body: fd }), f.deps);
  assert.equal(res.status, 303);
  assert.equal(res.headers.get("location"), `/thanks.html?e=${ev.id}`);
});

test("scheduled reminders send each email once, at the right time", async () => {
  const f = fakeDeps("2026-11-20T00:00:00Z");
  const ev = await addEvent(f); // Dec 3, 7 PM PT = 2026-12-04T03:00Z
  await registerHandler(req("POST", "/api/register", { eventId: ev.id, firstName: "R", email: "r@r.co" }), f.deps);
  f.outbox.length = 0;
  f.setNow("2026-12-03T04:00:00Z"); assert.deepEqual(await runReminders(f.deps), [`r24 → ${ev.id}`]);
  f.setNow("2026-12-03T04:15:00Z"); assert.deepEqual(await runReminders(f.deps), []);
  f.setNow("2026-12-04T02:00:00Z"); assert.deepEqual(await runReminders(f.deps), [`r1 → ${ev.id}`]);
  f.setNow("2026-12-04T16:00:00Z"); assert.deepEqual(await runReminders(f.deps), [`followup → ${ev.id}`]);
  f.setNow("2026-12-04T16:15:00Z"); assert.deepEqual(await runReminders(f.deps), []);
  assert.deepEqual(f.outbox.map((m) => m.subject.split(":")[0].split(" ")[0]), ["Tomorrow", "Starting", "Thank"]);
});

test("announce: needs a postal address, skips unsubscribed and already-registered, never double-sends", async () => {
  const f = fakeDeps("2026-11-20T00:00:00Z");
  const ev = await addEvent(f);
  for (const [email, optIn] of [["a@a.co", true], ["b@b.co", false], ["c@c.co", true]])
    await registerHandler(req("POST", "/api/register", { eventId: "waitlist", firstName: "X", email, optIn }), f.deps);
  await registerHandler(req("POST", "/api/register", { eventId: ev.id, firstName: "C", email: "c@c.co", optIn: true }), f.deps);
  f.outbox.length = 0;
  assert.equal((await announceHandler(req("POST", "/api/announce", { id: ev.id }, admin), f.deps)).status, 400);
  f.deps.env.MAILING_ADDRESS = "PO Box 1, Los Angeles, CA";
  const body = await (await announceHandler(req("POST", "/api/announce", { id: ev.id }, admin), f.deps)).json();
  assert.equal(body.sent, 1);
  assert.equal(f.outbox[0].to, "a@a.co");
  assert.match(f.outbox[0].text, /PO Box 1/);
  assert.equal((await announceHandler(req("POST", "/api/announce", { id: ev.id }, admin), f.deps)).status, 409);
});

test("unsubscribe link works only with the right token", async () => {
  const f = fakeDeps("2026-11-20T00:00:00Z");
  await registerHandler(req("POST", "/api/register", { eventId: "waitlist", firstName: "U", email: "u@u.co", optIn: true }), f.deps);
  assert.equal((await unsubscribeHandler(req("GET", "/api/unsubscribe?e=u@u.co&t=wrong"), f.deps)).status, 400);
  const t = unsubToken("u@u.co", "secret-key-123");
  assert.equal((await unsubscribeHandler(req("GET", `/api/unsubscribe?e=u%40u.co&t=${t}`), f.deps)).status, 200);
  const sub = await f.deps.store.get([...f.data.keys()].find((k) => k.startsWith("sub/")));
  assert.equal(sub.unsubscribed, true);
});

test("registrant export is admin-only CSV; public calendar file has no join link", async () => {
  const f = fakeDeps("2026-11-20T00:00:00Z");
  const ev = await addEvent(f);
  await registerHandler(req("POST", "/api/register", { eventId: ev.id, firstName: "Z", lastName: "Q", email: "z@z.co", phone: "3235550100" }), f.deps);
  assert.equal((await registrantsHandler(req("GET", `/api/registrants?id=${ev.id}`), f.deps)).status, 401);
  const csv = await (await registrantsHandler(req("GET", `/api/registrants?id=${ev.id}`, null, admin), f.deps)).text();
  assert.match(csv, /^firstName,lastName,email,phone/);
  assert.match(csv, /Z,Q,z@z\.co,3235550100/);
  const ics = await (await icsHandler(req("GET", `/api/ics?id=${ev.id}`), f.deps)).text();
  assert.doesNotMatch(ics, /zoom\.us/);
});

test("admin can edit and delete a session", async () => {
  const f = fakeDeps("2026-11-20T00:00:00Z");
  const ev = await addEvent(f);
  const put = await eventsHandler(req("PUT", "/api/events", { id: ev.id, title: "New topic", date: "2026-12-05", time: "10:00", tz: "America/Los_Angeles", durationMin: 40 }, admin), f.deps);
  assert.equal((await put.json()).event.title, "New topic");
  const list = await (await eventsHandler(req("GET", "/api/events?admin=1", null, admin), f.deps)).json();
  assert.equal(list.events[0].registrations, 0);
  assert.equal((await eventsHandler(req("DELETE", "/api/events", { id: ev.id }, admin), f.deps)).status, 200);
  assert.equal((await (await eventsHandler(req("GET", "/api/events"), f.deps)).json()).events.length, 0);
});
