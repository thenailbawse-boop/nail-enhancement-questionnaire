(() => {
  if (globalThis.__iphoneOperatorSafePrototypeInstalled) return;
  globalThis.__iphoneOperatorSafePrototypeInstalled = true;

  const BLOCKED_TEXT = /(?:delete|remove|archive|publish|post now|submit|send|buy|pay|checkout|purchase|transfer|withdraw|confirm|sign out|log out|unsubscribe|permanently|erase|discard|save changes|place order)/i;
  const ALLOWED_ACTIONS = new Set(["inspect", "click", "type", "scroll"]);
  const MAX_STEPS = 20;
  const MAX_TEXT = 512;
  const MAX_ELEMENTS = 70;

  function isVisible(element) {
    if (!(element instanceof HTMLElement)) return false;
    const s = getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    return s.display !== "none" && s.visibility !== "hidden" && rect.width > 0 && rect.height > 0;
  }

  function eligibleElements() {
    const elements = Array.from(document.querySelectorAll('a[href], button, input, textarea, select, [role="button"]'));
    return elements.filter(el => {
      if (!isVisible(el)) return false;
      if (el.matches('input[type="password"],input[type="hidden"],input[type="file"], [aria-hidden="true"]')) return false;
      return true;
    }).slice(0, MAX_ELEMENTS);
  }

  function snapshot() {
    const elements = eligibleElements();
    elements.forEach((element, index) => { element.dataset.iphoneOperatorId = String(index); });
    const bodyText = (document.body?.innerText || "").slice(0, 2600);
    return {
      url: location.origin + location.pathname,
      title: document.title.slice(0, 150),
      textExcerpt: bodyText,
      controls: elements.map((el, index) => ({
        id: String(index),
        tag: el.tagName.toLowerCase(),
        type: (el.getAttribute("type") || "").slice(0, 32),
        label: (el.getAttribute("aria-label") || el.innerText || el.getAttribute("placeholder") || "").trim().slice(0, 100)
      }))
    };
  }

  function targetFromId(target) {
    if (!/^\d{1,3}$/.test(String(target ?? ""))) return null;
    return document.querySelector(`[data-iphone-operator-id="${String(target)}"]`);
  }

  function safetyCheck(action, element) {
    if (!element || !isVisible(element)) return "Target unavailable or not visible; inspect again";
    if (element.matches('input[type="password"],input[type="hidden"],input[type="file"]')) return "Sensitive field prohibited";
    if (action === "type" && !element.matches('input:not([type="checkbox"]):not([type="radio"]),textarea')) return "Typing only supported in text inputs";
    if (action === "click") {
      const label = [element.innerText, element.getAttribute("aria-label"), element.getAttribute("title"), element.getAttribute("value")].filter(Boolean).join(" ");
      if (BLOCKED_TEXT.test(label)) return "Potentially consequential click requires manual user action";
      if (element.matches('button[type="submit"], input[type="submit"]') || element.closest('form') && element.matches('button:not([type="button"])')) return "Form submission blocked";
      if (element.matches('a[href]')) {
        try {
          const destination = new URL(element.href, location.href);
          if (destination.origin !== location.origin) return "Cross-site navigation requires manual user action";
        } catch { return "Unrecognized link target"; }
      }
    }
    return null;
  }

  function setText(element, value) {
    const proto = element instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
    const descriptor = Object.getOwnPropertyDescriptor(proto, "value");
    if (!descriptor?.set) return false;
    descriptor.set.call(element, value);
    element.dispatchEvent(new Event("input", { bubbles: true }));
    element.dispatchEvent(new Event("change", { bubbles: true }));
    return true;
  }

  function executeStep(step) {
    if (!step || !ALLOWED_ACTIONS.has(step.action)) return { ok: false, reason: "Unknown action" };
    if (step.action === "inspect") return { ok: true, result: snapshot() };
    if (step.action === "scroll") {
      const amount = step.direction === "up" ? -0.65 : 0.65;
      window.scrollBy({ top: window.innerHeight * amount, behavior: "instant" });
      return { ok: true, action: "scroll" };
    }
    const element = targetFromId(step.target);
    const issue = safetyCheck(step.action, element);
    if (issue) return { ok: false, paused: true, reason: issue };
    if (step.action === "type") {
      if (typeof step.text !== "string" || step.text.length > MAX_TEXT) return { ok: false, reason: "Text must be <=512 characters" };
      if (!setText(element, step.text)) return { ok: false, reason: "Cannot write target" };
      return { ok: true, action: "type", target: String(step.target) };
    }
    if (step.action === "click") {
      element.click();
      return { ok: true, action: "click", target: String(step.target) };
    }
    return { ok: false, reason: "Unsupported action" };
  }

  browser.runtime.onMessage.addListener((message) => {
    if (message?.type === "inspect") return Promise.resolve({ ok: true, result: snapshot() });
    if (message?.type !== "run") return Promise.resolve({ ok: false, reason: "Unknown request" });
    const plan = message.plan;
    if (!Array.isArray(plan?.steps) || plan.steps.length > MAX_STEPS) return Promise.resolve({ ok: false, reason: "Maximum 20 steps" });
    snapshot(); // Assign ids in visible page DOM before processing.
    const results = [];
    for (const [index, step] of plan.steps.entries()) {
      const outcome = executeStep(step);
      results.push({ step: index + 1, ...outcome });
      if (!outcome.ok) break; // Fail closed on ambiguous, unsafe, or inaccessible actions.
    }
    return Promise.resolve({ ok: results.every(r => r.ok), results });
  });
})();
