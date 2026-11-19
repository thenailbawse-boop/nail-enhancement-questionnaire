// Local preview: serves public/ and runs the real handlers with in-memory storage and a fake mailbox.
// node test/dev-server.mjs  → http://localhost:8788  (admin key: dev-key)
import http from "node:http";
import { readFile } from "node:fs/promises";
import { extname, join, normalize } from "node:path";
import * as H from "../lib/handlers.mjs";
import { runReminders } from "../lib/handlers.mjs";

const data = new Map(); export const outbox = [];
const deps = {
  store: { get: async (k) => (data.has(k) ? structuredClone(data.get(k)) : null), set: async (k, v) => { data.set(k, structuredClone(v)); },
    del: async (k) => data.delete(k), list: async (p) => [...data.keys()].filter((k) => k.startsWith(p)) },
  mailer: { send: async (m) => { outbox.push(m); console.log("MAIL →", m.to, "|", m.subject); } },
  env: { ADMIN_KEY: "dev-key", SITE_URL: "http://localhost:8788", OWNER_EMAIL: "owner@example.com", MAILING_ADDRESS: "PO Box 0, Los Angeles, CA" },
  now: () => Date.now(),
};
const routes = { "/api/events": H.eventsHandler, "/api/register": H.registerHandler, "/api/announce": H.announceHandler,
  "/api/registrants": H.registrantsHandler, "/api/unsubscribe": H.unsubscribeHandler, "/api/ics": H.icsHandler };
const types = { ".html": "text/html; charset=utf-8", ".css": "text/css", ".js": "text/javascript" };
const root = new URL("../public/", import.meta.url).pathname;

http.createServer(async (req, res) => {
  const url = new URL(req.url, "http://localhost:8788");
  if (url.pathname === "/__outbox") { res.setHeader("content-type", "application/json"); return res.end(JSON.stringify(outbox)); }
  if (url.pathname === "/__reminders") { res.end(JSON.stringify(await runReminders(deps))); return; }
  const h = routes[url.pathname];
  if (h) {
    const chunks = []; for await (const c of req) chunks.push(c);
    const r = await h(new Request(url, { method: req.method, headers: req.headers, body: ["GET", "HEAD"].includes(req.method) ? undefined : Buffer.concat(chunks) }), deps);
    res.writeHead(r.status, Object.fromEntries(r.headers)); return res.end(Buffer.from(await r.arrayBuffer()));
  }
  const p = normalize(join(root, url.pathname === "/" ? "index.html" : url.pathname));
  if (!p.startsWith(root)) { res.writeHead(403); return res.end(); }
  try { const b = await readFile(p); res.writeHead(200, { "content-type": types[extname(p)] || "application/octet-stream" }); res.end(b); }
  catch { res.writeHead(404); res.end("not found"); }
}).listen(8788, () => console.log("preview on http://localhost:8788"));
