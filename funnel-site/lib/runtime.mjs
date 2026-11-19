// Real dependencies on Netlify: Blobs for storage, Gmail (app password) for email.
import { getStore } from "@netlify/blobs";
import nodemailer from "nodemailer";

export function makeDeps() {
  const env = process.env;
  const blobs = getStore({ name: "funnel", consistency: "strong" });
  const store = {
    get: (key) => blobs.get(key, { type: "json" }),
    set: (key, value) => blobs.setJSON(key, value),
    del: (key) => blobs.delete(key),
    list: async (prefix) => (await blobs.list({ prefix })).blobs.map((b) => b.key),
  };
  let transport = null;
  const mailer = {
    async send({ to, subject, text, html, attachments, replyTo }) {
      if (!env.GMAIL_USER || !env.GMAIL_APP_PASSWORD) throw new Error("GMAIL_USER / GMAIL_APP_PASSWORD not set");
      transport ||= nodemailer.createTransport({ service: "gmail", auth: { user: env.GMAIL_USER, pass: env.GMAIL_APP_PASSWORD } });
      return transport.sendMail({
        from: `"${env.FROM_NAME || "Anisia | The Nail Bawse"}" <${env.GMAIL_USER}>`,
        to, subject, text, html, attachments, replyTo: replyTo || env.OWNER_EMAIL || env.GMAIL_USER,
      });
    },
  };
  return { store, mailer, env, now: () => Date.now() };
}
