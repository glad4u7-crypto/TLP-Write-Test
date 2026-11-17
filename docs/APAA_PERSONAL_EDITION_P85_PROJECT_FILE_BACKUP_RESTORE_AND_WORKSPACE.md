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

## Existing capabilities carried forward

- Owner-only Personal Backup & Restore UI already exists from P82 and now uses the extended archive implementation.
- Project file creation remains explicit-consent and fresh approval/audit gated; overwrite remains disabled.
- Saved task plans already persist with the memory database and can be loaded again; the action history panel remains separate from task lifecycle history.

## Remaining P85 work

1. Run the exact-head Python suite, compilation, dependency audit and responsive Android/desktop browser tests; fix any regressions and record the exact tested SHA.
2. Integrate the existing tenant-scoped SQLite task-state/event store into the Owner Task Workspace for task history, visible step progress, and explicit resume/review after restart. Loading or resuming a plan must never execute it or grant approval.
3. Improve the existing bounded read-only Web, project File and YouTube research surfaces while preserving no-cookie, no-script, no-write, SSRF/DNS/redirect controls and clear source attribution.
4. Finish Android-first browser layout and deployment/package documentation. The product direction remains a browser-based web platform; do not turn it into a mandatory Home Screen/native APK install.
5. Complete integration/security regression review and document external gates separately.

## Verification status

- Implementation is committed to `apaa-personal-edition-foundation`.
- Exact-head CI for the current P85 commits has not yet been observed. This document does not claim the new backup integration is verified.
- Physical Android acceptance, owner-operated restore drill and independent security review remain separate external gates.
- PR #13 remains Draft / Open / Unmerged. No merge or deployment is authorized by this checkpoint.
- Browser/Worker dispatch remains disabled; Auto-Run OFF. No paid provider/API key/charge, payment, purchase, trading or money movement is enabled.
