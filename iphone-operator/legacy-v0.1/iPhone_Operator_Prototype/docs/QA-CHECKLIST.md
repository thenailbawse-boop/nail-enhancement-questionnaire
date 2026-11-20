# Acceptance Test (run on an actual iPhone)

- [ ] iPhone Photos permission request appears; limited and full access behave as expected.
- [ ] Scanning 20 recent assets shows correct classification by type, date, and safe local Vision labels.
- [ ] Running native organizer creates three review albums without deleting, editing, or creating duplicate original files.
- [ ] Running organizer twice adds zero duplicate album memberships on second run.
- [ ] App Intent is visible in Shortcuts and runs successfully without foreground UI after permissions have already been granted.
- [ ] A real Time of Day automation completes for a small batch; record whether the device needs to be unlocked.
- [ ] Revoke Photos access and verify organizer halts without processing private content.
- [ ] Safari extension can be enabled on iOS and sees only user-authorized tab webpage content.
- [ ] Inspect retrieves visible controls but does not include password or input values.
- [ ] Benign same-page scroll and text fill operate correctly.
- [ ] Submit / delete / purchase / archive / publish clicks are rejected.
- [ ] Cross-site links are blocked pending manual owner action.
- [ ] When site DOM changes, stale targets fail closed rather than guessing.
- [ ] Muse account capabilities are verified on the client's authorized Instagram account; record exact confirmed read/write scopes.
- [ ] Record iOS version, phone model, account type, number of files handled, failures, approval prompts, and actual manual time.
