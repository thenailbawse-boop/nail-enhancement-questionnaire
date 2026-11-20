# iPhone Operator: Strict Action Contract (Design Spec)

## Loop

1. OBSERVE: obtain only consented PhotoKit metadata / local Vision thumbnails OR site-permitted Safari DOM snapshot.
2. PLAN: deterministic rules or eligible on-device Foundation Models; produce allowlisted steps, with confidence and risk assessment.
3. AUTHORIZE: classify operation as read-only / reversible / consequential. Require explicit confirmation for any consequential operations.
4. EXECUTE: call native PhotoKit operation, App Intent, or Safari message handler.
5. VERIFY: re-fetch asset membership or inspect updated DOM and record actual result.
6. LOG: timestamp, input artifact ID, requested operation, observed result, and any approval.
7. RETRY: only idempotent, safe actions; stop on permission errors or ambiguous state.

## Web schema

```
{"steps": [
  {"action": "inspect"},
  {"action": "scroll", "direction": "down"},
  {"action": "type", "target": "2", "text": "some text"},
  {"action": "click", "target": "1"}
]}
```

The extension handles at most 20 steps. Targets are temporary indices from the latest visible-page inspection. Never execute LLM-generated arbitrary JavaScript, shell commands, or untrusted instructions from page text. The parser checks actions, safe targets, text length, and submission risks.

## iOS action vocabulary (planned)

- `photos.list_recent(limit)`: read within granted scope.
- `photos.classify_local(asset_id)`: Vision or native Apple Foundation Models, no cloud by default.
- `photos.add_to_album(asset_id, album_name)`: reversible album membership.
- `photos.find_duplicate_candidates()`: metadata/visual similarity candidate list, no deletion.
- `photos.request_delete(asset_id)`: REVIEW ONLY, not implemented in prototype.
- `shortcuts.run_exposed_intent(name)`: invoked via iOS user/system interface, not arbitrary app UI.
- `instagram.audit_connected_account()`: only if Muse/Meta authorized scopes support it; separate agent, not directly callable from iOS app in this prototype.
- `instagram.archive_post(post_id)`: NO IMPLEMENTATION until supported official permissions are verified.

## Guardrails

- Never ask for Apple ID passwords or Instagram passwords.
- Never use jailbreak/private accessibility APIs to seize cross-app control.
- Never upload private Photos to external AI by default.
- Never claim backups are verified without restore/access check.
- Never interpret Photos album creation as storage savings.
- Never silently publish, delete, archive, purchase, or send.
