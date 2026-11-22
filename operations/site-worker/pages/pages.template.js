// The Nail Bawse: free resources pages (/resources...) and digital business card (/card...), served by thenailbawse-official.
// Built by pages/build.py. Files live in the repo at a pinned commit (operations/site-worker/pages/site/), are checked by
// SHA-256 and kept in the NB_WEBINAR KV namespace.
const MANIFEST = __MANIFEST__;
const COMMIT = "__COMMIT__";
const SOURCES = ["https://cdn.jsdelivr.net/gh/thenailbawse-boop/nail-enhancement-questionnaire@" + COMMIT + "/operations/site-worker/pages/site/",
                 "https://raw.githubusercontent.com/thenailbawse-boop/nail-enhancement-questionnaire/" + COMMIT + "/operations/site-worker/pages/site/"];
async function sha256(buf) { return Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256", buf))).map(b => b.toString(16).padStart(2, "0")).join(""); }
export async function pages(request, env, h) {
  const m = MANIFEST[h.key];
  if (!m || (request.method !== "GET" && request.method !== "HEAD")) return null;
  const kvKey = "pg:" + m.f + ":" + m.s;
  let body = await env.NB_WEBINAR.get(kvKey, "arrayBuffer");
  if (body === null) {
    for (const base of SOURCES) {
      try { const r = await fetch(base + m.f); if (!r.ok) continue; const b = await r.arrayBuffer(); if (await sha256(b) !== m.s) continue; await env.NB_WEBINAR.put(kvKey, b); body = b; break; } catch (e) {}
    }
  }
  if (body === null) return new Response("This page is updating. Please refresh in a minute.", { status: 503, headers: { "content-type": "text/plain; charset=utf-8" } });
  const isHtml = m.t.indexOf("text/html") === 0;
  return new Response(request.method === "HEAD" ? null : body, { headers: { "content-type": m.t, "cache-control": isHtml ? "public, max-age=300" : "public, max-age=86400", "x-content-type-options": "nosniff" } });
}
