// Creator Reset — web plan safety checker.
// Shared by popup.js and content.js (and tested in Node by web-tests/).
// Must stay in sync with Core/Sources/OperatorCore/WebPlan.swift (a Swift test checks the word list).
(function (root) {
  "use strict";

  const MAX_STEPS = 20;
  const MAX_TEXT = 512;
  const ALLOWED_ACTIONS = ["scroll", "type", "click"];
  const RISKY_WORDS = [
    "delete", "remove", "archive", "publish", "post now", "submit", "send", "buy", "pay",
    "checkout", "purchase", "transfer", "withdraw", "confirm", "sign out", "log out",
    "unsubscribe", "permanently", "erase", "discard", "save changes", "place order",
    "password", "credit card", "bank"
  ];
  const NOT_TYPABLE = ["checkbox", "radio", "submit", "button", "password", "hidden", "file", "image", "reset"];

  function riskyWord(text) {
    const lower = String(text || "").toLowerCase();
    return RISKY_WORDS.find((w) => lower.includes(w)) || null;
  }

  function describeStep(step, controlsById) {
    const control = controlsById && step.target != null ? controlsById[String(step.target)] : null;
    const name = control ? `“${control.label || control.tag}”` : `item ${step.target}`;
    if (step.action === "scroll") return `Scroll ${step.direction === "up" ? "up" : "down"}`;
    if (step.action === "type") return `Type “${step.text}” into ${name}`;
    if (step.action === "click") return `Tap ${name}`;
    return `Unknown step (${step.action})`;
  }

  /**
   * Checks a plan against the allowlist and the latest page inspection.
   * Returns { ok, errors[], steps[] } where steps are normalized copies with expectLabel filled in.
   */
  function validatePlan(plan, snapshot) {
    const errors = [];
    if (!plan || typeof plan !== "object" || !Array.isArray(plan.steps)) {
      return { ok: false, errors: ["The plan needs a \"steps\" list."], steps: [] };
    }
    if (plan.steps.length === 0) errors.push("The plan has no steps.");
    if (plan.steps.length > MAX_STEPS) errors.push(`Too many steps (max ${MAX_STEPS}).`);
    if (snapshot && snapshot.sensitive) errors.push("This page has a password box. The operator does not work on sign-in or payment pages.");

    const controls = (snapshot && Array.isArray(snapshot.controls)) ? snapshot.controls : [];
    const byId = {};
    for (const c of controls) byId[String(c.id)] = c;

    const steps = [];
    plan.steps.slice(0, MAX_STEPS).forEach((raw, index) => {
      const n = index + 1;
      if (!raw || typeof raw !== "object") { errors.push(`Step ${n}: not a step.`); return; }
      const extraKeys = Object.keys(raw).filter((k) => !["action", "target", "text", "direction", "expectLabel"].includes(k));
      if (extraKeys.length) { errors.push(`Step ${n}: unexpected fields (${extraKeys.join(", ")}).`); return; }
      const action = raw.action;
      if (!ALLOWED_ACTIONS.includes(action)) { errors.push(`Step ${n}: "${action}" is not an allowed action.`); return; }

      if (action === "scroll") {
        if (raw.direction !== undefined && raw.direction !== "up" && raw.direction !== "down") {
          errors.push(`Step ${n}: scroll direction must be up or down.`); return;
        }
        steps.push({ action, direction: raw.direction === "up" ? "up" : "down" });
        return;
      }

      const target = String(raw.target ?? "");
      if (!/^\d{1,3}$/.test(target)) { errors.push(`Step ${n}: needs a target number from the latest Inspect.`); return; }
      const control = byId[target];
      if (!control) { errors.push(`Step ${n}: item ${target} is not on the page right now. Inspect again.`); return; }

      if (action === "type") {
        if (typeof raw.text !== "string" || raw.text.length === 0) { errors.push(`Step ${n}: type needs text.`); return; }
        if (raw.text.length > MAX_TEXT) { errors.push(`Step ${n}: text is longer than ${MAX_TEXT} characters.`); return; }
        const type = String(control.type || "").toLowerCase();
        const typable = (control.tag === "input" && !NOT_TYPABLE.includes(type)) || control.tag === "textarea";
        if (!typable) { errors.push(`Step ${n}: item ${target} is not a text box.`); return; }
        steps.push({ action, target, text: raw.text, expectLabel: control.label });
        return;
      }

      // click
      const word = riskyWord(control.label);
      if (word) { errors.push(`Step ${n}: “${control.label}” looks risky (${word}). Do that one yourself.`); return; }
      if (String(control.type || "").toLowerCase() === "submit") { errors.push(`Step ${n}: submitting forms is not allowed.`); return; }
      steps.push({ action, target, expectLabel: control.label });
    });

    return { ok: errors.length === 0, errors, steps, readable: steps.map((s) => describeStep(s, byId)) };
  }

  const api = { MAX_STEPS, MAX_TEXT, ALLOWED_ACTIONS, RISKY_WORDS, riskyWord, validatePlan, describeStep };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  root.CreatorResetPlan = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
