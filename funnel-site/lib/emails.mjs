// Every email the funnel sends. Topic-agnostic: the session title fills in. Plain text + light HTML.
import { formatWhen, googleCalendarUrl } from "./core.mjs";

const esc = (s) => String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

function wrapHtml(paragraphs, footer) {
  const body = paragraphs.map((p) => `<p style="margin:0 0 14px">${p}</p>`).join("");
  return `<div style="font-family:Helvetica,Arial,sans-serif;font-size:16px;line-height:1.55;color:#2A1A2E;max-width:560px">${body}` +
    (footer ? `<p style="margin:24px 0 0;font-size:12px;color:#6E5A70">${footer}</p>` : "") + "</div>";
}
const button = (url, label) =>
  `<a href="${esc(url)}" style="display:inline-block;background:#A3184F;color:#fff;text-decoration:none;padding:12px 22px;border-radius:999px;font-weight:bold">${esc(label)}</a>`;

function footerParts(ctx, { marketing }) {
  const lines = [];
  if (ctx.unsubUrl) lines.push(`Don't want emails about future free sessions? <a href="${esc(ctx.unsubUrl)}" style="color:#6E5A70">Unsubscribe</a>.`);
  if (marketing && ctx.mailingAddress) lines.push(esc(ctx.mailingAddress));
  return lines.join("<br>");
}
const footerText = (ctx, { marketing }) =>
  [ctx.unsubUrl ? `Unsubscribe from future session emails: ${ctx.unsubUrl}` : "", marketing && ctx.mailingAddress ? ctx.mailingAddress : ""]
    .filter(Boolean).join("\n");

const sign = "Anisia\nThe Nail Bawse";
const signHtml = "Anisia<br>The Nail Bawse";
const joinLine = (ev) => ev.zoomUrl || "(Your Zoom link is coming in a separate email.)";

export function confirmationEmail(ev, reg, ctx) {
  const when = formatWhen(ev.startUtc, ev.tz);
  const cal = googleCalendarUrl(ev, { includeJoinLink: true });
  const subject = `You're in 💅🏽 ${ev.title}`;
  const text = [
    `Hey ${reg.firstName},`,
    `Your seat is saved for my free live session:\n${ev.title}\n${when} · Live on Zoom`,
    `Join here: ${joinLine(ev)}`,
    `The calendar invite is attached. Add it now so you don't miss it. I'll also send a reminder the day before and an hour before.`,
    `Bring a notebook and one real question from your business. That's where the good stuff happens.`,
    `See you there,\n${sign}`,
    footerText(ctx, { marketing: false }),
  ].filter(Boolean).join("\n\n");
  const html = wrapHtml([
    `Hey ${esc(reg.firstName)},`,
    `Your seat is saved for my free live session:<br><strong>${esc(ev.title)}</strong><br>${esc(when)} · Live on Zoom`,
    ev.zoomUrl ? button(ev.zoomUrl, "Join on Zoom") + `<br><span style="font-size:13px;color:#6E5A70">${esc(ev.zoomUrl)}</span>` : esc(joinLine(ev)),
    `The calendar invite is attached. <a href="${esc(cal)}">Add it to Google Calendar</a> so you don't miss it. I'll also send a reminder the day before and an hour before.`,
    `Bring a notebook and one real question from your business. That's where the good stuff happens.`,
    `See you there,<br>${signHtml}`,
  ], footerParts(ctx, { marketing: false }));
  return { subject, text, html };
}

export function waitlistEmail(reg, ctx) {
  const subject = "You're on the list 💅🏽";
  const text = [
    `Hey ${reg.firstName},`,
    `Thanks for signing up! The next free live session isn't on the calendar yet. As soon as it is, you'll get the date, the topic and a link to save your seat.`,
    `Talk soon,\n${sign}`,
    footerText(ctx, { marketing: false }),
  ].filter(Boolean).join("\n\n");
  const html = wrapHtml([
    `Hey ${esc(reg.firstName)},`,
    `Thanks for signing up! The next free live session isn't on the calendar yet. As soon as it is, you'll get the date, the topic and a link to save your seat.`,
    `Talk soon,<br>${signHtml}`,
  ], footerParts(ctx, { marketing: false }));
  return { subject, text, html };
}

export function reminderEmail(kind, ev, reg, ctx) {
  const when = formatWhen(ev.startUtc, ev.tz);
  if (kind === "r24") {
    const subject = `Tomorrow: ${ev.title}`;
    const text = [`Hey ${reg.firstName},`, `Quick reminder: ${ev.title} is ${when}.`, `Join here: ${joinLine(ev)}`,
      `Come with one question you want answered. I'll make room for it.`, sign, footerText(ctx, { marketing: false })].filter(Boolean).join("\n\n");
    const html = wrapHtml([`Hey ${esc(reg.firstName)},`, `Quick reminder: <strong>${esc(ev.title)}</strong> is ${esc(when)}.`,
      ev.zoomUrl ? button(ev.zoomUrl, "Join on Zoom") : esc(joinLine(ev)), `Come with one question you want answered. I'll make room for it.`, signHtml],
      footerParts(ctx, { marketing: false }));
    return { subject, text, html };
  }
  if (kind === "r1") {
    const subject = `Starting in about an hour 🩷 ${ev.title}`;
    const text = [`Hey ${reg.firstName},`, `We go live in about an hour (${when}).`, `Join here: ${joinLine(ev)}`, `See you soon,\n${sign}`,
      footerText(ctx, { marketing: false })].filter(Boolean).join("\n\n");
    const html = wrapHtml([`Hey ${esc(reg.firstName)},`, `We go live in about an hour (${esc(when)}).`,
      ev.zoomUrl ? button(ev.zoomUrl, "Join on Zoom") : esc(joinLine(ev)), `See you soon,<br>${signHtml}`], footerParts(ctx, { marketing: false }));
    return { subject, text, html };
  }
  // followup
  const subject = ev.replayUrl ? `The replay is up: ${ev.title}` : `Thank you for registering: ${ev.title}`;
  const next = ctx.siteUrl ? `See the next free session and save your seat: ${ctx.siteUrl}` : "";
  const text = [`Hey ${reg.firstName},`,
    ev.replayUrl ? `Whether you made it live or not, here's the replay: ${ev.replayUrl}` : `Thank you for registering for ${ev.title}. Whether you made it live or not, I appreciate you making time for your business.`,
    `Hit reply and tell me one thing you're going to try this week. I'd love to hear it.`, next, sign, footerText(ctx, { marketing: true })]
    .filter(Boolean).join("\n\n");
  const html = wrapHtml([`Hey ${esc(reg.firstName)},`,
    ev.replayUrl ? `Whether you made it live or not, here's the replay:<br>${button(ev.replayUrl, "Watch the replay")}` : `Thank you for registering for <strong>${esc(ev.title)}</strong>. Whether you made it live or not, I appreciate you making time for your business.`,
    `Hit reply and tell me one thing you're going to try this week. I'd love to hear it.`,
    ctx.siteUrl ? `<a href="${esc(ctx.siteUrl)}">See the next free session and save your seat</a>` : "", signHtml].filter(Boolean),
    footerParts(ctx, { marketing: true }));
  return { subject, text, html };
}

export function announcementEmail(ev, sub, ctx) {
  const when = formatWhen(ev.startUtc, ev.tz);
  const subject = `New free live session: ${ev.title}`;
  const link = ctx.siteUrl || "";
  const text = [`Hey ${sub.firstName || "friend"},`, `I'm going live for free:\n${ev.title}\n${when} on Zoom`, ev.description,
    `Save your seat: ${link}`, sign, footerText(ctx, { marketing: true })].filter(Boolean).join("\n\n");
  const html = wrapHtml([`Hey ${esc(sub.firstName || "friend")},`, `I'm going live for free:<br><strong>${esc(ev.title)}</strong><br>${esc(when)} on Zoom`,
    ev.description ? esc(ev.description).replace(/\n/g, "<br>") : "", link ? button(link, "Save my seat") : "", signHtml].filter(Boolean),
    footerParts(ctx, { marketing: true }));
  return { subject, text, html };
}

export function ownerNotice(ev, reg) {
  const subject = `New registration: ${reg.firstName} ${reg.lastName} · ${ev ? ev.title : "waitlist"}`.trim();
  const text = [
    `Session: ${ev ? `${ev.title} (${formatWhen(ev.startUtc, ev.tz)})` : "Waitlist (no session scheduled)"}`,
    `Name: ${reg.firstName} ${reg.lastName}`, `Email: ${reg.email}`, `Phone: ${reg.phone || "-"}`, `Role: ${reg.role || "-"}`,
    `Heard about it: ${reg.source || "-"}${reg.ref ? ` (link: ${reg.ref})` : ""}`, `Wants help with: ${reg.goal || "-"}`,
    `Future sessions emails: ${reg.optIn ? "yes" : "no"}`,
  ].join("\n");
  return { subject, text };
}
