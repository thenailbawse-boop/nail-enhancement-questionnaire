# iPhone Operator — Safe Agentic Prototype v0.1

**Status: SOURCE-CODE PROTOTYPE, not an installed or compiled iPhone app.**

This repository establishes two legitimate execution surfaces for an iPhone-first operator inspired by Claude in Chrome:

1. **iOS Native Operator** (SwiftUI + PhotoKit + Vision + App Intents): inspect recent authorized Apple Photos items; assign local metadata/Vision labels; safely add items to review albums; make sorting available to Apple Shortcuts for schedules. Includes an *optional* Apple Foundation Models-based read-only planning layer for eligible iOS 26+ devices.
2. **Safari Web Operator** (WebExtension MV3): inspect the active webpage's visible interactive controls, then run a deliberately reviewed JSON plan to scroll, type, or click safe same-site elements. Attempts to submit forms or click destructive or consequential controls are blocked.

## What it does NOT do

- Does not allow tapping arbitrary iPhone apps or viewing all native app screens.
- Does not run forever in the iOS background. App Intents can be launched by Shortcuts but iOS enforces runtime policies.
- Does not directly connect one ChatGPT agent to a Muse agent or use their internal accounts without explicit integrations.
- Does not have a model-generated browser planning loop **yet**. The Safari proof of concept accepts a reviewed JSON plan; a supported on-device or API planner must be integrated in a later build.
- Does not manage Instagram app UI or automatically archive posts; Muse's Instagram connector capabilities need owner-account verification.
- Does not remove storage by organizing albums; it performs **non-destructive categorization** only.
- Does not upload or delete photos.

## First launch: native iOS app

Needs a Mac with Xcode and an iPhone. Not installable directly from this ZIP.

1. Open Xcode and create an **iOS App** project named `iPhoneOperator` (Swift, SwiftUI). Target iOS 26 if using the optional Foundation Models planner. To target iOS 18+, remove `OnDevicePlanner.swift` and the planning-button references, or conditionally compile that file for an iOS 26 SDK.
2. Replace template app source with `ios-app/iPhoneOperatorApp.swift`; add `ios-app/OnDevicePlanner.swift` if building with the iOS 26 SDK.
3. Add `NSPhotoLibraryUsageDescription` to your app Info settings with the explanatory string in `ios-app/Info-Plist-Configuration.txt`.
4. Sign the app with your Apple development team and run it on an owned/test iPhone. For personal testing, free Apple ID provisioning may be sufficient, subject to Xcode restrictions. Wider App Store distribution requires Apple Developer Program participation.
5. Tap **Request Photos access**; then **Inspect recent media**. Check result count and local Vision labels.
6. Tap **Safely sort into review albums**. Check Apple Photos for `Operator - Screenshots Review`, `Operator - Video Review`, and `Operator - Photo Review`. Run twice to confirm no duplicate album membership is created.
7. In Apple Shortcuts, find **Organize Recent Media** from the app's App Intents, and run it. Once successfully tested, create a daily Personal Automation pointing to that action. Confirm it completes on the real device without unlock prompts before calling it unattended.

### iPhone photo permission behavior

The user can choose limited or full access. The operator processes only assets it can see. The code does not request access to other apps and cannot access the whole phone filesystem. Do not give this to a friend without consent and documented data boundaries.

## Safari web-extension test

Needs a Mac with Xcode to package the WebExtension into an iOS Safari Extension host app.

1. Create a new **Safari Web Extension App** target for iOS in Xcode, or use Apple's Safari web extension converter to generate an Xcode wrapper for `web-extension/`.
2. Copy the files `manifest.json`, `popup.html`, `popup.js`, and `content.js` into the extension's Resources folder (replace the template demo files).
3. Build and install the host app on iPhone. In Safari Settings > Extensions, enable the extension and grant site-specific permission.
4. Navigate to a benign test page such as https://example.com. Tap the extension in Safari's page menu. Select **Inspect this page**. Review visible elements in JSON; this requires permission from Safari.
5. Enter `{"steps":[{"action":"scroll","direction":"down"}]}` and choose **Run reviewed plan**. For a click, take the element ID from the inspection result and use a JSON step like `{"action":"click","target":"0"}`; cross-site navigation and risky actions are rejected.
6. Do not test against banking, medical, email, or other sensitive pages. Do not run this extension on client accounts until privacy and security review is complete.

### Sample reviewed plan

```json
{
  "steps": [
    {"action":"type","target":"0","text":"Example query"},
    {"action":"scroll","direction":"down"}
  ]
}
```

The element index is from the fresh **Inspect** output for the current page. A site redesign or navigation invalidates the plan; inspect again. The browser executor cannot submit forms.

## How ChatGPT and Muse fit

**ChatGPT** — Available now for designing/test-driving instructions, generating reviewed browser action JSON from an owner-approved DOM snapshot, and (on compatible devices) as a model in Apple Shortcuts. This does not grant the ChatGPT app arbitrary cross-app permissions and is not a free OpenAI API key.

**Muse** — A separate Instagram-connected agent for supported audit/analysis and any owner-approved connected actions. Meta documents connector access and background activity, but general automated Instagram archive/delete permission is **not verified** for this use case. No direct ChatGPT-to-Muse machine-to-machine integration is established here.

**Apple Foundation Models** — Optional *native* AI reasoning in the iOS app at no separate model subscription on compatible Apple Intelligence-enabled devices. In the prototype it only produces a read-only review plan; Vision classification and album actions are separate. This is the most economical route for a first-party iOS agent brain.

## Action permission policy

| Operation | V0.1 status | Permission rule |
| --- | --- | --- |
| Read selected/authorized PhotoKit assets | Native code implemented | User grants Photos access |
| Label preview images with on-device Vision | Native code implemented | Only locally available image thumbnails |
| Add existing assets to new albums | Native code implemented | After explicit action / scheduled Shortcut |
| Delete assets / free storage | Not implemented | Never silently delete |
| Inspect active Safari page | Web code implemented | User activation and site permission |
| Type in ordinary web text input | Web code implemented | User-reviewed JSON plan; no passwords |
| Click same-site links and benign controls | Web code implemented | Risky/submit clicks blocked |
| Execute across native third-party apps | Not supported by general iOS API | Requires each app's exposed intents/APIs |
| Trigger exact-time always-on jobs | Not guaranteed | Subject to iOS scheduling/runtime |
| Publish/archive Instagram content | Not implemented | Owner review and verified supported Meta integration |

## Verification that was possible here

- Safari extension scripts passed `node --check` syntax validation.
- `manifest.json` passed JSON validation.
- Swift source passed Swift parser validation (`swiftc -frontend -parse`).
- **NOT compiled or run in Xcode.** Apple frameworks aren't available in this Linux authoring environment, and there was no connected iPhone or account to test permissions and real execution.

## Next engineering milestones

1. **Device QA:** Prove real Safari extension injection and PhotoKit sorting on a test iPhone, including app-in-background behavior and shortcut triggers.
2. **Native AI planner with tool-calling:** Evolve Apple Foundation Models from read-only plans to a strict allowlisted tool contract that invokes only PhotoKit, App Intents, and approved actions; require approvals for irreversible operations. Apple supplies model tool-calling primitives on supported devices.
3. **Safari-native model bridge:** Connect a Safari web extension to its containing iOS extension via `browser.runtime.sendNativeMessage`, with the native extension as planner/tool dispatcher. Apple documentation confirms web-to-native messaging on iOS but specifically notes that the containing iOS app cannot initiate messages to JavaScript.
4. **Instagram connector audit:** With the owner's account permission, inventory Muse's actual allowed read/write scopes and any API-based supported actions. Do not use hidden APIs or scrape private content to get around account restrictions.
5. **Reliability:** Add idempotent execution ledger, snapshots, permission revocation handling, retry ceilings, local redaction, risk policy, and automated tests.

## Primary references

- Apple: Safari Web Extensions: https://developer.apple.com/documentation/safariservices/safari-web-extensions
- Apple: Safari permissions: https://developer.apple.com/documentation/safariservices/managing-safari-web-extension-permissions
- Apple: iOS web-to-native extension messaging: https://developer.apple.com/documentation/safariservices/messaging-between-the-app-and-javascript-in-a-safari-web-extension
- Apple: PhotoKit: https://developer.apple.com/documentation/photos/phphotolibrary
- Apple: Vision image classification: https://developer.apple.com/documentation/vision/vnclassifyimagerequest
- Apple: App Intents: https://developer.apple.com/documentation/appintents
- Apple: Background tasks: https://developer.apple.com/documentation/backgroundtasks
- Apple: Foundation Models: https://developer.apple.com/foundation-models-framework/
- Apple: ChatGPT in Shortcuts: https://support.apple.com/guide/shortcuts/use-apple-intelligence-in-shortcuts-tpg3vrvwmclv/ios
- Meta Muse: https://ai.meta.com/muse/
