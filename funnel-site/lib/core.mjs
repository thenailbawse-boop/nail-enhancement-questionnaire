// Pure helpers: no network, no storage. Everything here is unit-tested in test/core.test.mjs.
import { createHash, createHmac, timingSafeEqual, randomBytes } from "node:crypto";

export const DEFAULT_TZ = "America/Los_Angeles";
export const ROLES = ["Nail tech", "Hairstylist", "Esthetician", "Lash or brow artist", "Makeup artist",
  "Salon or suite owner", "Beauty educator", "Barber", "Other"];
export const SOURCES = ["Instagram", "Skool", "A friend", "Email", "Event or class", "Other"];

const MIN = 60 * 1000;
const HOUR = 60 * MIN;

// ---------- time ----------
function tzOffsetMs(utcMs, tz) {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: tz, hourCycle: "h23", year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", second: "2-digit",
  }).formatToParts(new Date(utcMs));
  const p = Object.fromEntries(parts.map((x) => [x.type, x.value]));
  const asUtc = Date.UTC(+p.year, +p.month - 1, +p.day, +p.hour, +p.minute, +p.second);
  return asUtc - utcMs;
}

/** "2026-12-04" + "20:00" in tz -> ISO UTC string. Handles DST. */
export function zonedToUtc(date, time, tz = DEFAULT_TZ) {
  const dm = /^(\d{4})-(\d{2})-(\d{2})$/.exec(date || "");
  const tm = /^(\d{1,2}):(\d{2})$/.exec(time || "");
  if (!dm || !tm) throw new Error("Use date YYYY-MM-DD and time HH:MM");
  const wall = Date.UTC(+dm[1], +dm[2] - 1, +dm[3], +tm[1], +tm[2]);
  let guess = wall - tzOffsetMs(wall, tz);
  guess = wall - tzOffsetMs(guess, tz);
  return new Date(guess).toISOString();
}

export function formatWhen(iso, tz = DEFAULT_TZ) {
  const d = new Date(iso);
  const day = new Intl.DateTimeFormat("en-US", { timeZone: tz, weekday: "long", month: "long", day: "numeric" }).format(d);
  const time = new Intl.DateTimeFormat("en-US", { timeZone: tz, hour: "numeric", minute: "2-digit", timeZoneName: "short" }).format(d);
  return `${day} at ${time}`;
}

export function eventEnd(ev) {
  return new Date(new Date(ev.startUtc).getTime() + (ev.durationMin || 45) * MIN);
}

export function upcoming(events, now = Date.now()) {
  return (events || [])
    .filter((e) => eventEnd(e).getTime() > now)
    .sort((a, b) => new Date(a.startUtc) - new Date(b.startUtc));
}

export function publicEvent(ev) {
  const { zoomUrl, replayUrl, ...rest } = ev;
  return { ...rest, hasReplay: Boolean(replayUrl) };
}

// ---------- ids, keys, tokens ----------
export function emailKey(email) {
  return createHash("sha256").update(String(email).trim().toLowerCase()).digest("hex").slice(0, 32);
}

export function newEventId(startUtc) {
  return `${startUtc.slice(0, 10)}-${randomBytes(3).toString("hex")}`;
}

export function safeEqual(a, b) {
  const x = Buffer.from(String(a ?? ""));
  const y = Buffer.from(String(b ?? ""));
  return x.length === y.length && x.length > 0 && timingSafeEqual(x, y);
}

export function unsubToken(email, secret) {
  return createHmac("sha256", secret).update(String(email).trim().toLowerCase()).digest("hex").slice(0, 32);
}

// ---------- validation ----------
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;
const clean = (v, max) => String(v ?? "").replace(/[\u0000-\u001f\u007f]/g, " ").trim().slice(0, max);

export function validateRegistration(input) {
  const errors = {};
  const out = {
    eventId: clean(input.eventId, 64),
    firstName: clean(input.firstName, 60),
    lastName: clean(input.lastName, 60),
    email: clean(input.email, 254).toLowerCase(),
    phone: clean(input.phone, 30),
    role: clean(input.role, 40),
    source: clean(input.source, 40),
    goal: clean(input.goal, 500),
    optIn: input.optIn === true || input.optIn === "on" || input.optIn === "true",
    tz: clean(input.tz, 60),
    ref: clean(input.ref, 60),
  };
  if (!out.firstName) errors.firstName = "Please add your first name.";
  if (!EMAIL_RE.test(out.email)) errors.email = "Please check your email address.";
  if (out.phone) {
    const digits = out.phone.replace(/\D/g, "");
    if (digits.length < 7 || digits.length > 15) errors.phone = "Please check your phone number, or leave it blank.";
  }
  if (out.role && !ROLES.includes(out.role)) out.role = "Other";
  if (out.source && !SOURCES.includes(out.source)) out.source = "Other";
  if (!out.eventId) errors.eventId = "Please pick a session.";
  return { ok: Object.keys(errors).length === 0, value: out, errors };
}

export function validateEventInput(input) {
  const errors = {};
  const title = clean(input.title, 120);
  const description = String(input.description ?? "").trim().slice(0, 1500);
  const tz = clean(input.tz, 60) || DEFAULT_TZ;
  const durationMin = Math.round(Number(input.durationMin || 45));
  const zoomUrl = clean(input.zoomUrl, 500);
  const replayUrl = clean(input.replayUrl, 500);
  let startUtc = null;
  if (!title) errors.title = "Add a topic title.";
  try { startUtc = zonedToUtc(input.date, input.time, tz); } catch (e) { errors.date = e.message; }
  if (!(durationMin >= 10 && durationMin <= 240)) errors.durationMin = "Length must be 10–240 minutes.";
  if (zoomUrl && !/^https:\/\//.test(zoomUrl)) errors.zoomUrl = "The Zoom link should start with https://";
  if (replayUrl && !/^https:\/\//.test(replayUrl)) errors.replayUrl = "The replay link should start with https://";
  return { ok: !Object.keys(errors).length, errors, value: { title, description, tz, durationMin, zoomUrl, replayUrl, startUtc } };
}

// ---------- reminders ----------
/** Which reminder (if any) is due for one registration right now. */
export function dueReminder(ev, reg, now = Date.now()) {
  const start = new Date(ev.startUtc).getTime();
  const end = eventEnd(ev).getTime();
  const sent = reg.sent || {};
  const regAt = new Date(reg.registeredAt).getTime();
  if (!sent.r24 && now >= start - 25 * HOUR && now < start - 3 * HOUR && now - regAt > HOUR) return "r24";
  if (!sent.r1 && now >= start - 90 * MIN && now < start - 10 * MIN) return "r1";
  if (!sent.followup && now >= end + 12 * HOUR && now < end + 72 * HOUR) return "followup";
  return null;
}

// ---------- calendar ----------
const icsEsc = (s) => String(s ?? "").replace(/\\/g, "\\\\").replace(/;/g, "\\;").replace(/,/g, "\\,").replace(/\r?\n/g, "\\n");
const icsDate = (d) => d.toISOString().replace(/[-:]/g, "").replace(/\.\d{3}/, "");
function fold(line) {
  const out = [];
  while (line.length > 74) { out.push(line.slice(0, 74)); line = " " + line.slice(74); }
  out.push(line);
  return out.join("\r\n");
}

export function buildIcs(ev, { siteUrl = "", includeJoinLink = true } = {}) {
  const start = new Date(ev.startUtc);
  const join = includeJoinLink && ev.zoomUrl ? ev.zoomUrl : "";
  const desc = [ev.description, join ? `Join on Zoom: ${join}` : "Your Zoom link is in your confirmation email.", siteUrl]
    .filter(Boolean).join("\n\n");
  return [
    "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//The Nail Bawse//Workshop//EN", "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
    "BEGIN:VEVENT",
    `UID:${ev.id}@thenailbawse`,
    `DTSTAMP:${icsDate(new Date())}`,
    `DTSTART:${icsDate(start)}`,
    `DTEND:${icsDate(eventEnd(ev))}`,
    fold(`SUMMARY:${icsEsc(ev.title)}`),
    fold(`DESCRIPTION:${icsEsc(desc)}`),
    fold(`LOCATION:${icsEsc(join || "Online (Zoom)")}`),
    "BEGIN:VALARM", "ACTION:DISPLAY", "DESCRIPTION:Starting soon", "TRIGGER:-PT30M", "END:VALARM",
    "END:VEVENT", "END:VCALENDAR", "",
  ].join("\r\n");
}

export function googleCalendarUrl(ev, { includeJoinLink = false } = {}) {
  const fmt = (d) => icsDate(d);
  const details = [ev.description, includeJoinLink && ev.zoomUrl ? `Join: ${ev.zoomUrl}` : "Your Zoom link is in your confirmation email."]
    .filter(Boolean).join("\n\n");
  const q = new URLSearchParams({
    action: "TEMPLATE", text: ev.title, dates: `${fmt(new Date(ev.startUtc))}/${fmt(eventEnd(ev))}`, details,
    location: includeJoinLink && ev.zoomUrl ? ev.zoomUrl : "Online (Zoom)",
  });
  return `https://calendar.google.com/calendar/render?${q}`;
}

// ---------- CSV ----------
export function toCsv(rows, columns) {
  const esc = (v) => {
    let s = String(v ?? "");
    if (/^[=+\-@]/.test(s)) s = "'" + s; // stop spreadsheet formula injection
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  return [columns.join(","), ...rows.map((r) => columns.map((c) => esc(r[c])).join(","))].join("\n") + "\n";
}
