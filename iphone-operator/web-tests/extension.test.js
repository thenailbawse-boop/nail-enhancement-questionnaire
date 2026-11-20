// Tests the Safari extension's page script and plan checker in a fake browser (jsdom).
// Real Safari on iPhone is still required for a full test; this checks the safety logic.
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { JSDOM } = require("jsdom");

const RES = path.join(__dirname, "..", "SafariExtension", "Resources");
const validatorSrc = fs.readFileSync(path.join(RES, "plan-validator.js"), "utf8");
const contentSrc = fs.readFileSync(path.join(RES, "content.js"), "utf8");
const V = require(path.join(RES, "plan-validator.js"));

const PAGE = `
<h1>Nail art ideas</h1>
<form action="/search"><input id="q" type="search" placeholder="Search"><button>Go</button></form>
<a href="/gallery">Gallery</a>
<a href="https://other.example/">Partner site</a>
<button type="button">Delete account</button>
<button type="button" id="more">Show more</button>
<input type="hidden" name="token" value="secret">
<input type="checkbox" aria-label="Remember me">
`;

function makePage(html = PAGE) {
  const dom = new JSDOM(`<!doctype html><body>${html}</body>`, { url: "https://nails.example/ideas", runScripts: "outside-only" });
  const { window } = dom;
  // jsdom has no layout: make everything "visible" and give innerText a value.
  window.HTMLElement.prototype.getBoundingClientRect = () => ({ width: 10, height: 10, top: 0, left: 0, right: 10, bottom: 10 });
  Object.defineProperty(window.HTMLElement.prototype, "innerText", { get() { return this.textContent; }, configurable: true });
  window.scrollBy = () => {};
  let listener = null;
  window.browser = { runtime: { onMessage: { addListener: (fn) => { listener = fn; } } } };
  window.eval(validatorSrc);
  window.eval(contentSrc);
  const send = (msg) => listener(msg);
  return { window, send };
}

const idOf = (snapshot, label) => snapshot.controls.find((c) => c.label === label)?.id;

test("inspect lists visible controls but never hidden/password fields or typed values", async () => {
  const { send } = makePage(PAGE + '<input type="password" aria-label="Password">');
  const { result } = await send({ type: "inspect" });
  const labels = result.controls.map((c) => c.label);
  assert.ok(labels.includes("Search"));
  assert.ok(labels.includes("Gallery"));
  assert.ok(!labels.includes("Password"));
  assert.ok(!JSON.stringify(result).includes("secret"));
  assert.equal(result.sensitive, true, "a page with a password box is flagged");
});

test("run is refused before inspect and on sign-in pages", async () => {
  let page = makePage();
  let res = await page.send({ type: "run", plan: { steps: [{ action: "scroll", direction: "down" }] } });
  assert.equal(res.ok, false);
  page = makePage(PAGE + '<input type="password" aria-label="Password">');
  await page.send({ type: "inspect" });
  res = await page.send({ type: "run", plan: { steps: [{ action: "scroll", direction: "down" }] } });
  assert.equal(res.ok, false);
});

test("typing fills the box and verifies it by reading it back", async () => {
  const { window, send } = makePage();
  const snap = (await send({ type: "inspect" })).result;
  const res = await send({ type: "run", plan: { steps: [{ action: "type", target: idOf(snap, "Search"), text: "chrome nails" }] } });
  assert.equal(res.ok, true);
  assert.equal(window.document.getElementById("q").value, "chrome nails");
  assert.match(res.results[0].verified, /Text is in the box/);
});

test("risky, submit and cross-site clicks are refused", async () => {
  for (const label of ["Delete account", "Go", "Partner site"]) {
    const { send } = makePage();
    const snap = (await send({ type: "inspect" })).result;
    const res = await send({ type: "run", plan: { steps: [{ action: "click", target: idOf(snap, label) }] } });
    assert.equal(res.ok, false, label);
  }
});

test("stale targets fail closed when the page changed after inspect", async () => {
  const { window, send } = makePage();
  const snap = (await send({ type: "inspect" })).result;
  window.document.getElementById("more").textContent = "Delete everything";
  const res = await send({ type: "run", plan: { steps: [{ action: "click", target: idOf(snap, "Show more") }] } });
  assert.equal(res.ok, false);
  assert.match(res.results[0].reason, /page changed/);
});

test("it stops after a tap so the page can be checked again", async () => {
  const { window, send } = makePage();
  let clicked = 0;
  window.document.getElementById("more").addEventListener("click", () => clicked++);
  const snap = (await send({ type: "inspect" })).result;
  const res = await send({ type: "run", plan: { steps: [
    { action: "click", target: idOf(snap, "Show more") },
    { action: "type", target: idOf(snap, "Search"), text: "should not happen" }
  ] } });
  assert.equal(clicked, 1);
  assert.equal(window.document.getElementById("q").value, "");
  assert.ok(res.results.some((r) => r.paused));
  const again = await send({ type: "run", plan: { steps: [{ action: "scroll" }] } });
  assert.equal(again.ok, false, "old numbers are not trusted after a run");
});

test("validator: allowlist, limits, unexpected fields, risky words", () => {
  const snap = { controls: [{ id: "0", tag: "input", type: "search", label: "Search" }, { id: "1", tag: "a", type: "", label: "Gallery" }] };
  assert.equal(V.validatePlan({ steps: [{ action: "type", target: "0", text: "x" }, { action: "click", target: "1" }] }, snap).ok, true);
  assert.equal(V.validatePlan({ steps: [{ action: "eval", text: "alert(1)" }] }, snap).ok, false);
  assert.equal(V.validatePlan({ steps: [{ action: "click", target: "1", script: "x" }] }, snap).ok, false);
  assert.equal(V.validatePlan({ steps: Array(21).fill({ action: "scroll" }) }, snap).ok, false);
  assert.equal(V.validatePlan({ steps: [{ action: "type", target: "0", text: "a".repeat(513) }] }, snap).ok, false);
  assert.equal(V.validatePlan({ steps: [{ action: "click", target: "7" }] }, snap).ok, false);
  assert.equal(V.validatePlan({ steps: [] }, snap).ok, false);
  assert.equal(V.riskyWord("Publish my post"), "publish");
  assert.equal(V.riskyWord("show nail ideas"), null);
});

test("manifest asks only for the tab you tap (no all-sites access)", () => {
  const manifest = JSON.parse(fs.readFileSync(path.join(RES, "manifest.json"), "utf8"));
  assert.deepEqual(manifest.permissions.sort(), ["activeTab", "nativeMessaging", "scripting"]);
  assert.equal(manifest.host_permissions, undefined);
  assert.equal(manifest.content_scripts, undefined);
});
