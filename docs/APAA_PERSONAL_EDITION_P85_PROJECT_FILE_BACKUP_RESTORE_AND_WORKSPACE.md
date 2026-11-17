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
- Added durable per-step progress records keyed by tenant, project, plan and step. Progress totals render as a progress bar and remain separate from execution status. Every step-status write now requires a separate Owner consent checkbox plus submit, and is routed through the existing payload-bound approval and audit path.
- Added tests for progress persistence after database reopen, consent, tenant isolation and step-ID validation, plus AppTests proving Web/Page/YouTube providers are not called until the Owner submits and that provider errors are handled safely.
- Corrected the Project Files UI notice: project files are included in Personal Backup v3; users are told to keep archives private and perform a restore drill.
- Existing saved task plans remain available for review and reloading. Checkpoint status is shown as active, blocked, completed or cancelled.
- Android-first responsive CSS already enforces 44px minimum touch targets and 16px form text; this P85 pass preserves the browser-based product direction rather than creating a mandatory APK/Home Screen app.

## Existing capabilities carried forward

- Owner-only Personal Backup & Restore UI already exists from P82 and now uses the extended archive implementation.
- Project file creation remains explicit-consent and fresh approval/audit gated; overwrite remains disabled.
- The action history panel remains separate from task lifecycle/checkpoint history.

## Remaining P85 work

1. Run the exact-head Python suite, compilation, dependency audit and responsive Android/desktop browser tests; fix any regressions and record the exact tested SHA.
2. Add further UI-level tests for public page and YouTube forms, including provider errors and no-call-before-submit behavior. The shared network provider's DNS/redirect/SSRF regression suite is already present.
4. Finish Android-first browser layout and deployment/package documentation. The product direction remains a browser-based web platform; do not turn it into a mandatory Home Screen/native APK install.
5. Complete integration/security regression review and document external gates separately.

## Verification status

- Implementation is committed to `apaa-personal-edition-foundation`.
- P73 Verification run #337 tested earlier P85 code head `16f43924bed2d027829137150e6a63a4bd83e9cb`: compilation PASS, dependency audit PASS, responsive browser smoke PASS, Python suite **1,519 passed / 9 skipped / 1 failed**. The failure identified a restore-created parent directory with overly broad permissions.
- Corrected restore directory creation to explicitly create and chmod both `project-files` and project directories to 0700.
- CI #363 on commit `597f2933b6eac56eb0627c620b648f243fcb31cd`: **1,522 passed / 9 skipped / 0 failed**; Python compile, dependency audit and responsive browser smoke all PASS.
- CI #369 on commit `d2b534f2e706ae7d3ab936e1247bca168bfd01ae`: **1,526 passed / 9 skipped / 0 failed**; Python compile, dependency audit and responsive browser smoke all PASS.
- After #369 completed, additional AppTest coverage was added for explicit-submit Web/Page/YouTube UI behavior and provider-error display, plus a database-reopen persistence assertion for task step progress. These newest tests are not covered by #369; a fresh exact-head CI run is required before P85 can be called verified.
- Physical Android acceptance, owner-operated restore drill and independent security review remain separate external gates.
- PR #13 remains Draft / Open / Unmerged. No merge or deployment is authorized by this checkpoint.
- Browser/Worker dispatch remains disabled; Auto-Run OFF. No paid provider/API key/charge, payment, purchase, trading or money movement is enabled.


## P85 closeout decision

Implementation work for the scoped P85 code changes is complete on the feature branch. The latest observed PR head when this report was updated is `07a252ce24d2d425ece419d40b732dc93b617845`.

**Do not label P85 fully verified or release-ready yet.** The latest visible successful full CI run is #369 on the earlier commit `d2b534f2e706ae7d3ab936e1247bca168bfd01ae`. The workflow also triggers on branch pushes, but the available workflow-run lookup exposes only pull-request-triggered runs; no exact-head result for the latest branch push could be independently read through the current integration.

Remaining external acceptance gates:
- Confirm the latest exact-head push run in GitHub Actions and resolve any failures.
- Run the app on a physical Android device and complete the device acceptance checklist; emulator/desktop browser smoke is not equivalent.
- Perform an Owner-operated backup → clean restore → project-file hash/content verification drill on a separate private destination.
- Obtain independent security review before any remote exposure or production deployment.

The Android path delivered in this checkpoint is a Termux-launched loopback browser app, not a signed APK, Play Store release or native Android package. PR #13 remains Draft/Open/Unmerged. No production deployment, remote worker activation, paid provider, payment or execution dispatch is authorized.
