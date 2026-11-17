# APAA Personal Edition P85 — Project File Backup & Restore Integration

Date: 2026-11-17

## Scope

P85 starts the next Personal Edition integration pass. The first code slice closes the known P84 data-loss gap: owner-approved project text files now travel with the existing verified Personal Backup & Restore archive.

## Implemented in this slice

- Backup format version 3 adds a `project_files` inventory to the existing manifest.
- Files are included from the private `project-files/<project-id>/` workspace only after the existing safe project-file listing checks.
- Backup reads use directory-relative, no-follow file opens and re-check regular-file type, size and SHA-256 to detect changes during collection.
- Limits: 500 project files and 32 MiB aggregate project-file content; each file remains bounded by the existing 64 KiB project-file limit.
- Each archived project file has a manifest size and SHA-256. Restore validates archive paths, entry types, per-file and aggregate sizes, exact archive inventory, hashes, UTF-8 and NUL-byte exclusion.
- Restore creates private project directories/files (0700/0600) inside the new restore staging directory. It still refuses an existing destination and never overwrites or switches the live runtime.
- Existing v1 and v2 backups remain supported. The local approval signing key remains excluded and is freshly generated after restore, invalidating old approval receipts.
- Added regression coverage for project-file backup/restore and archive-payload tampering.

## Additional P85 integration added

- Added an explicit-submit **Read-only Web & YouTube Research** panel. It supports public web search, reading one public HTTPS page, and public YouTube video discovery.
- Network requests occur only after the Owner submits a form. The UI uses the existing bounded HTTPS providers: no cookies, browser session, JavaScript, playlist mutation, write action or execution-gateway registration.
- Project file inspection remains local and read-only.
- Added tenant/project-scoped, newest-first checkpoint history with a bounded listing API.
- The Task Workspace can prefill the planner from an Owner-selected active/blocked checkpoint's next action. This is a draft-only resume: it does not execute a task or grant approval.
- Existing saved task plans remain available for review and reloading. Checkpoint status is shown as active, blocked, completed or cancelled.
- Android-first responsive CSS already enforces 44px minimum touch targets and 16px form text; this P85 pass preserves the browser-based product direction rather than creating a mandatory APK/Home Screen app.

## Existing capabilities carried forward

- Owner-only Personal Backup & Restore UI already exists from P82 and now uses the extended archive implementation.
- Project file creation remains explicit-consent and fresh approval/audit gated; overwrite remains disabled.
- The action history panel remains separate from task lifecycle/checkpoint history.

## Remaining P85 work

1. Run the exact-head Python suite, compilation, dependency audit and responsive Android/desktop browser tests; fix any regressions and record the exact tested SHA.
2. Complete progress visualization across individual plan steps and reconcile it with the durable task-state/event store; current checkpoint status/history and planner-prefill resume are implemented, but they are not yet a full step-by-step execution progress engine.
3. Add UI-level tests for the explicit-submit web/page/YouTube forms, including provider errors, redirect/SSRF rejection and no-call-before-submit behavior.
4. Finish Android-first browser layout and deployment/package documentation. The product direction remains a browser-based web platform; do not turn it into a mandatory Home Screen/native APK install.
5. Complete integration/security regression review and document external gates separately.

## Verification status

- Implementation is committed to `apaa-personal-edition-foundation`.
- P73 Verification run #337 tested earlier P85 code head `16f43924bed2d027829137150e6a63a4bd83e9cb`: compilation PASS, dependency audit PASS, responsive browser smoke PASS, Python suite **1,519 passed / 9 skipped / 1 failed**. The failure identified a restore-created parent directory with overly broad permissions.
- Corrected restore directory creation to explicitly create and chmod both `project-files` and project directories to 0700. This correction is in later branch commits; **no exact-head CI result has yet been observed for the correction or subsequent P85 UI/launcher additions**.
- Therefore P85 remains implementation-pending-verification; do not infer a full PASS from the earlier partial run.
- Physical Android acceptance, owner-operated restore drill and independent security review remain separate external gates.
- PR #13 remains Draft / Open / Unmerged. No merge or deployment is authorized by this checkpoint.
- Browser/Worker dispatch remains disabled; Auto-Run OFF. No paid provider/API key/charge, payment, purchase, trading or money movement is enabled.
