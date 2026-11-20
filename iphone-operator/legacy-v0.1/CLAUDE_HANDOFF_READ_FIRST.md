# CLAUDE HANDOFF — iPhone Operator / Creator Reset OS
**Date:** November 20, 2026
**Project owner:** Founder of The Nail Bawse (do not call her CEO; she uses the title Founder)
**Your role:** Lead iOS engineer, agent architect, implementation and QA owner. Pick up the existing source code and advance the build. Do not merely write another strategy brief.

## 1) The mission, in plain English
Build a **plug-and-play AI operator for iPhone**, inspired by the experience of Claude in Chrome on a desktop. The long-term vision is an AI agent that can observe permitted apps/pages, decide what to do, execute actions, verify results, and continue maintenance without a person repeatedly prompting it.

The **first client is the founder's friend**, who wants to clean up her iPhone storage and restart/refresh her Instagram presence. The user wants to do the technical setup for her friend so the friend only has to **install, connect, authorize, delegate** and approve sensitive decisions. This first deployment may become a reusable premium done-for-you service, but **do not imply a $5K–$10K fee is validated merely because the idea exists**; prove the delivered work and reliability.

The user **does not want to research or debug integrations herself**. You own the technical investigation, code updates, build/package preparation, and easy instructions. Speak plainly, as though explaining to a fifth grader. Avoid jargon or explain it in a sentence.

## 2) Product principles / constraints
- **Use platforms the owner already knows:** ChatGPT, Claude, Muse, optionally Base44. Do not add Activepieces, Make, Zapier, or a new paid platform without demonstrating necessity. Begin with Apple-native free capabilities.
- **Free first**: Apple Shortcuts, PhotoKit, Vision, App Intents, Safari Web Extensions, and optional Apple Foundation Models (hardware/iOS permitting). A Mac with Xcode may be required to compile a native app; make that dependency explicit. Apple's paid developer membership may be needed for wider distribution, but should not be presumed necessary for a personal prototype.
- **Build the hands, not just the brain:** Avoid an output that merely generates advice, prompts, or dashboards. The prototype must perform real allowed actions (e.g., inspect owner-approved Photos and add assets to albums) and verify results.
- **Privacy and consent:** The friend's device/photos/Instagram belong to the friend. Require her own authorization and accounts. Do not share passwords, grant remote access without informed approval, or upload private photos to external models by default.
- **Never pretend an iPhone is an unrestricted desktop:** iOS does **not** offer a public third-party API to view/tap across every installed native app, and ordinary apps cannot execute forever in the background. Do not propose jailbreaks, private APIs, covert accessibility controls, or unsupported “always-on” access. Design supported equivalents.
- **Keep human approvals for consequential acts:** No automatic permanent deletions, Instagram archiving/publishing, purchases, messages, or account-settings changes until supported capabilities are verified and specific consent is obtained. Organizing Photos into albums **does not itself free storage**.
- **No fabricated integrations:** Do not assume ChatGPT or Muse remotely controls third-party iPhone apps or that Muse can archive Instagram posts. Verify exact scopes and features, noting anything untestable without owner credentials. Do not confuse ChatGPT subscriptions with free API usage.

## 3) Existing files — read before writing code
The accompanying folder `iPhone_Operator_Prototype/` is the **existing v0.1 source prototype**. It is NOT a compiled, signed, or real-device-tested app.

- `README.md` — architecture, set-up notes, known limits, current validation status.
- `ios-app/iPhoneOperatorApp.swift` — SwiftUI, PhotoKit, local Vision categorization, review albums, an App Intent.
- `ios-app/OnDevicePlanner.swift` — experimental Apple Foundation Models read-only planner; requires appropriate SDK/device.
- `ios-app/Info-Plist-Configuration.txt` — Photos permission notes.
- `web-extension/{manifest.json,content.js,popup.html,popup.js,test-dom.js}` — Safari extension prototype; has reviewed JSON plans, not an autonomous agent reasoning loop.
- `docs/AGENT-CONTRACT.md` — observe → plan → authorize → execute → verify → log → retry policy.
- `docs/CHATGPT-AND-MUSE-PROMPTS.md` — role prompts for the external agents.
- `docs/QA-CHECKLIST.md` — real-device test checklist.

Prior work reports that JS syntax, extension manifest JSON, and Swift *parsing* were checked. **Xcode compilation, iOS integration, and real-device permissions have NOT been verified.** Recheck everything independently. Do not report source parsing as a passing iOS build.

## 4) Engineering architecture to implement

### A — Native iPhone execution layer (highest priority)
Build a valid, reproducible Xcode app that uses:
1. **PhotoKit:** after explicit authorization, list only permitted assets; create review albums; add existing photos/videos to albums without creating duplicate originals or deleting anything.
2. **Vision / local rules:** on-device preliminary classification of photos and metadata. If image labels are uncertain, place in `Needs Review`. Do NOT claim to visually understand video contents without actually processing frames/video.
3. **App Intents + Shortcuts:** expose a safe `Organize Recent Media` action that can be run from Shortcuts; test whether scheduled operation works in background under real device conditions. Provide a supported fallback for jobs that require foreground interaction.
4. **Action ledger and verification:** record asset identifier, proposed action, before state, after state, result, error, timestamp, permissions. Repeat runs must be idempotent.
5. **Simple UI:** one-tap setup, permission status, `Test with 5 photos`, `Run Organizer`, `View Results`, `Review Needed`, `Turn On Schedule` instructions. No giant dashboard.
6. **Optional local AI:** Foundation Models tool calling on compatible iOS devices. Provide deterministic Vision/metadata fallback for unsupported devices. Never describe unsupported hardware as compatible.

### B — Safari execution layer (second priority)
Package the existing WebExtension into a Safari extension host app for iPhone (or carefully integrated target). Grant only scoped website permissions. Build an explicit `inspect → plan → approve → act → verify` loop for ordinary webpages: inspect visible DOM, type into safe fields, scroll, click allowed elements, re-inspect. Plan must use an allowlisted schema; no arbitrary model-supplied JavaScript. Reject passwords, purchases, publishing, delete, send, form submission, sensitive screens, cross-site surprises and ambiguous targets. Clearly label actions that require the user's active Safari session; do not claim background Safari execution.

### C — Specialized AI agents (third priority)
- **ChatGPT agent / planner:** reasoning and classifications *only via supported integrations/Shortcuts or APIs*, never magic remote control of iPhone apps. Use local AI where feasible to avoid service fees.
- **Muse Instagram assistant:** review connected Instagram information and return an audit / priority queue if supported. Audit Muse's exact account authorization and permitted actions before promising posting, archiving, deleting, editing, or background behavior. If credentials aren't available, provide an explicit permission-test script and leave the capability `UNVERIFIED`.
- **Claude:** your engineering/execution workspace in this handoff. You may also investigate Claude's verified iPhone Shortcuts actions as an alternative to ChatGPT, but prioritize owner familiarity and lowest cost.
- **Base44:** hold unless the native experience genuinely needs a web dashboard. The goal is to operate *on iPhone*, not merely host a dashboard.

### D — Storage outcomes (separate from organization)
For real reclaimed space, inspect native iPhone Storage reporting and Apple Photos duplicate detection/optimization options. Never delete assets to “prove” an AI feature. If iCloud sync is enabled, emphasize that deletion can propagate across synced devices. Track *before and after available storage* and distinguish actual bytes reclaimed from album organization.

## 5) First client scenario / acceptance criteria
**Owner statement:** “Organize my camera roll, keep personal memories safe, identify possible duplicates and reusable creator content, and help refresh my Instagram. Keep it organized going forward.”

The first device test should demonstrate:
1. User installs/test-launches app or Shortcut, understands permissions, and can revoke them.
2. System safely scans 5 then 20 authorized assets.
3. Agent categorizes in local review categories (screenshots, creator content, videos, needs review); unknown content is never silently deleted.
4. Existing assets are added to albums; no duplicate photo files are created.
5. Running twice causes **zero duplicate operations** and produces clear action logs.
6. Scheduled Shortcuts invocation is tested on the target iPhone; document any unlock, permission, or background limitation.
7. Safari extension can inspect and complete benign tasks only on explicitly authorized websites and confirms result after interaction.
8. Muse / Instagram integration is audited separately with confirmed vs unsupported read/write actions.
9. Friend receives a one-page “Install → Allow → Test → Activate → Review” guide.
10. No recurring paid service is necessary for baseline native functionality; if an optional expense is unavoidable, provide an exact reason and free alternative.

## 6) What I need you, Claude, to do FIRST
**Do not restart discovery or deliver a sales deck. Inspect the supplied source files and continue implementation immediately.**

1. Inventory the repository, explain which pieces are working source, incomplete, or not compilable.
2. Build a **real Xcode project/workspace** with correct iOS targets, entitlements, Info.plist privacy strings, signing instructions, and resources; repair Swift/API/manifest issues rather than assuming the old code compiles. Aim for a runnable local native Photos MVP first.
3. Add practical unit/smoke tests where possible and a test-data workflow that avoids real client photos.
4. Preserve the privacy/risk policy; all destructive features remain disabled by default.
5. Package the finished project source as a downloadable ZIP. If your environment cannot actually compile, say so explicitly and give the exact first compilation steps for a Mac.
6. Produce **two final artifacts**:
   - `CREATOR_RESET_BUILD.zip` — complete updated project source and relevant resources.
   - `START_HERE.md` — 5th-grade-level numbered instructions: what app to open, what to tap, what success looks like, what must be approved, how to stop/revoke, and what remains untested.
7. After that, work through Safari operator and agent orchestration; report a small status table with `Built`, `Tested on simulator`, `Tested on physical device`, or `Blocked` (avoid vague “done”).

If you need a missing fact to actually compile or test (device model, iOS version, Mac/Xcode access, account scopes), make the most conservative assumption you can and continue on independent tasks. Ask at most one targeted question once it truly blocks the next physical-device step. Do not send the founder off to research integration documentation.

## 7) Definition of done
**Not done:** a conceptual diagram, prompts, a dashboard mockup, syntax checks, or a claim that a human could complete the actions manually.

**Done for first engineering milestone:** reproducible iPhone app project that actually builds (or explicitly untested compilation if no Xcode), uses authorized Apple Photos access, safely organizes test assets, exposes a Shortcut action, records verified outcomes, and includes instructions simple enough for a non-technical client.

**Done for client pilot:** demonstrated on the friend's compatible iPhone with her permission, measured outcomes, clearly documented remaining manual approvals, and repeatable onboarding.

**Long-term goal:** one native iPhone operator with multiple specialized task agents, giving a Claude-in-Chrome-like experience within Apple's supported execution surfaces.

## 8) Exact kickoff instruction
**START BY READING THE WHOLE INCLUDED `README.md`, `docs/AGENT-CONTRACT.md`, `ios-app/*.swift`, and extension files. THEN IMPLEMENT THE FIRST COMPILE-READY XCODE PROJECT. Don't ask me to research, buy new tools, or manually assemble the system if you can produce the files yourself. Tell me precisely which actions are independently executable, which require permissions, which are impossible with public iOS APIs, and what you actually tested.**
