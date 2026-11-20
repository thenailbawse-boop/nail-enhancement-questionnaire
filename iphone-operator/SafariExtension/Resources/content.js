// Creator Reset — page hands. Injected only into the tab the user is looking at, only after
// they tap the extension (activeTab). Looks at visible buttons/links/boxes, does approved
// safe steps, then checks what actually happened. Never reads what is typed in boxes.
(() => {
  "use strict";
  if (globalThis.__creatorResetOperator) return;
  globalThis.__creatorResetOperator = true;

  const V = globalThis.CreatorResetPlan;
  const MAX_ELEMENTS = 80;
  const SENSITIVE_INPUT = [
    'input[type="password"]', 'input[type="hidden"]', 'input[type="file"]',
    'input[autocomplete^="cc-"]', 'input[autocomplete="one-time-code"]',
    'input[autocomplete="current-password"]', 'input[autocomplete="new-password"]'
  ].join(",");
  let lastSnapshot = null;

  function isVisible(el) {
    if (!(el instanceof HTMLElement)) return false;
    const style = getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    return style.display !== "none" && style.visibility !== "hidden" && rect.width > 0 && rect.height > 0;
  }

  function labelOf(el) {
    const isButtonInput = el.tagName === "INPUT" && ["submit", "button", "reset"].includes((el.getAttribute("type") || "").toLowerCase());
    const raw = el.getAttribute("aria-label") || el.innerText || el.getAttribute("placeholder") ||
      (isButtonInput ? el.getAttribute("value") : "") || el.getAttribute("title") || el.getAttribute("name") || "";
    return String(raw).replace(/\s+/g, " ").trim().slice(0, 100);
  }

  function typeOf(el) {
    if (el.tagName === "BUTTON") {
      const t = (el.getAttribute("type") || "").toLowerCase();
      // A <button> inside a <form> with no type submits the form.
      if (t === "submit" || (!t && el.closest("form"))) return "submit";
      return t || "button";
    }
    return (el.getAttribute("type") || (el.tagName === "INPUT" ? "text" : "")).toLowerCase().slice(0, 32);
  }

  function pageIsSensitive() {
    return Array.from(document.querySelectorAll('input[type="password"]')).some(isVisible);
  }

  function snapshot() {
    document.querySelectorAll("[data-creator-reset-id]").forEach((el) => el.removeAttribute("data-creator-reset-id"));
    const elements = Array.from(document.querySelectorAll('a[href], button, input, textarea, select, [role="button"]'))
      .filter((el) => isVisible(el) && !el.matches(SENSITIVE_INPUT) && el.getAttribute("aria-hidden") !== "true")
      .slice(0, MAX_ELEMENTS);
    elements.forEach((el, i) => el.setAttribute("data-creator-reset-id", String(i)));
    lastSnapshot = {
      url: location.origin + location.pathname,
      title: document.title.slice(0, 150),
      sensitive: pageIsSensitive(),
      takenAt: new Date().toISOString(),
      textExcerpt: (document.body?.innerText || "").replace(/\s+/g, " ").slice(0, 2000),
      controls: elements.map((el, i) => ({ id: String(i), tag: el.tagName.toLowerCase(), type: typeOf(el), label: labelOf(el) }))
    };
    return lastSnapshot;
  }

  function findTarget(target) {
    if (!/^\d{1,3}$/.test(String(target ?? ""))) return null;
    return document.querySelector(`[data-creator-reset-id="${String(target)}"]`);
  }

  function checkElement(step, el) {
    if (!el || !isVisible(el)) return "That item is gone or hidden now. Inspect again.";
    if (el.matches(SENSITIVE_INPUT)) return "Private boxes (passwords, cards, codes) are off limits.";
    if (step.expectLabel !== undefined && labelOf(el) !== step.expectLabel) {
      return `The page changed (expected “${step.expectLabel}”, found “${labelOf(el)}”). Inspect again.`;
    }
    if (step.action === "type" && !el.matches('input:not([type="checkbox"]):not([type="radio"]):not([type="submit"]):not([type="button"]), textarea')) {
      return "Typing only works in text boxes.";
    }
    if (step.action === "click") {
      const word = V.riskyWord([labelOf(el), el.getAttribute("title"), el.getAttribute("value")].filter(Boolean).join(" "));
      if (word) return `Looks risky (${word}). Do that one yourself.`;
      if (typeOf(el) === "submit" || el.matches('input[type="submit"]')) return "Submitting forms is not allowed.";
      if (el.matches("a[href]")) {
        try {
          const dest = new URL(el.href, location.href);
          if (dest.origin !== location.origin) return "That link goes to a different website. Tap it yourself if you want.";
          if (dest.protocol === "javascript:") return "Script links are not allowed.";
        } catch { return "Unrecognized link."; }
      }
    }
    return null;
  }

  function setText(el, value) {
    const proto = el instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
    const descriptor = Object.getOwnPropertyDescriptor(proto, "value");
    if (!descriptor?.set) return false;
    el.focus();
    descriptor.set.call(el, value);
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
    return true;
  }

  const wait = (ms) => new Promise((r) => setTimeout(r, ms));

  async function run(plan) {
    if (!lastSnapshot) return { ok: false, results: [], reason: "Inspect the page first." };
    if (pageIsSensitive()) return { ok: false, results: [], reason: "This page has a password box. The operator stays off sign-in pages." };
    const check = V.validatePlan(plan, lastSnapshot);
    if (!check.ok) return { ok: false, results: [], reason: check.errors.join(" ") };

    const before = { url: location.href, title: document.title, scrollY: window.scrollY };
    const results = [];
    for (const [index, step] of check.steps.entries()) {
      const n = index + 1;
      if (step.action === "scroll") {
        window.scrollBy({ top: window.innerHeight * (step.direction === "up" ? -0.65 : 0.65), behavior: "instant" });
        results.push({ step: n, ok: true, did: V.describeStep(step) });
        continue;
      }
      const el = findTarget(step.target);
      const problem = checkElement(step, el);
      if (problem) { results.push({ step: n, ok: false, reason: problem }); break; }
      if (step.action === "type") {
        const ok = setText(el, step.text);
        // VERIFY: read back that the box now holds exactly what we typed.
        const confirmed = ok && el.value === step.text;
        results.push({ step: n, ok: confirmed, did: `Typed into “${step.expectLabel}”`, verified: confirmed ? "Text is in the box." : "Could not confirm the text." });
        if (!confirmed) break;
        continue;
      }
      el.click();
      results.push({ step: n, ok: true, did: `Tapped “${step.expectLabel}”` });
      if (index < check.steps.length - 1) {
        results.push({ step: n + 1, ok: true, paused: true, reason: "Stopped after a tap so the page can be checked again before doing more." });
      }
      break;
    }

    await wait(700);
    const after = { url: location.href, title: document.title, scrollY: window.scrollY };
    lastSnapshot = null; // old numbers are no longer trusted
    return {
      ok: results.every((r) => r.ok),
      results,
      verify: {
        urlChanged: before.url !== after.url,
        titleChanged: before.title !== after.title,
        scrolledBy: Math.round(after.scrollY - before.scrollY),
        nowAt: after.url.split("#")[0].split("?")[0],
        note: "Inspect again before the next step."
      }
    };
  }

  browser.runtime.onMessage.addListener((message) => {
    if (message?.type === "inspect") return Promise.resolve({ ok: true, result: snapshot() });
    if (message?.type === "run") return run(message.plan);
    return Promise.resolve({ ok: false, reason: "Unknown request" });
  });
})();
