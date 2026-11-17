# APAA Personal Edition — P73 Runtime, Persistence and Acceptance

**Checkpoint:** APAA-PERSONAL-P73  
**Date:** 2026-11-17  
**Branch:** `apaa-personal-edition-foundation`  
**Status:** Repository implementation substantially complete; exact-head verification and external acceptance gates remain.  
**PR:** #13 — Draft / Open / Unmerged.

## 1. Implemented repository work

### Runtime and owner boundary
- Local Personal Edition uses a fixed server-side owner tenant and owner-private `~/.apaa_personal` storage (or server-side `APAA_PERSONAL_DATA_DIR`).
- Local unauthenticated mode rejects non-loopback Streamlit server binding.
- Task/browser text cannot choose or override the owner identity.
- This fixed local identity is not authentication for a network-exposed deployment.

### Persistent storage
- Owner-scoped SQLite projects, security/approval nonces, durable audit events and consent-gated memory/checkpoints are wired into the local runtime.
- Projects, memory, knowledge, conversation turns, preferences and task checkpoints survive application restarts.
- Local databases and signing key are protected with owner-only filesystem permissions and symlink checks.
- Cross-session local owner views use separate session objects but share the same owner's persistent data; approval capabilities remain session-bound.

### Approval and action audit
- Stable local 32-byte signing key and durable one-time approval nonce storage.
- Approval receipts bind exact action, payload digest, tenant, session and bounded expiry.
- Project creation is review-first and only executes on the explicit Confirm action.
- Intent audit is persisted before project mutation; audit failure blocks dispatch.
- Memory, knowledge, conversation, preference and checkpoint mutations use a fail-closed metadata-only audit wrapper. Explicit consent remains required for content writes.
- Audit records exclude task/content payloads and persist in the SQLite security database.
- Auto-Run remains OFF with no configured Auto-Run allowlist.

### Browser and Worker safety
- No Browser or Worker action handler is registered in the Personal Edition application.
- Unknown actions fail closed; financial, purchase, paid-provider and money-movement actions remain prohibited.
- Browser execution remains DISABLED pending the full origin/redirect/SSRF/DNS-rebinding/session/download-upload/cancellation/egress qualification. It is not safe to enable based only on UI tests.

### Backup and restore
- `core/personal_backup.py` creates owner-private SQLite snapshots for projects, security/audit/nonces and memory/checkpoints.
- Backup verifies SQLite integrity and the audit hash chain, enforces exact archive inventory and size bounds, and verifies SHA-256 digests.
- Restore rejects unsafe archive entries and never overwrites an existing data directory; it stages and atomically renames into a new directory.
- The signing key is deliberately excluded from backup; restore generates a fresh key and invalidates outstanding approvals.
- CLI entry points: `scripts/backup_personal_data.py` and `scripts/restore_personal_data.py`.
- Detailed operator instructions and limitations: `docs/APAA_PERSONAL_EDITION_P73_BACKUP_RESTORE.md`.

## 2. Automated verification

The dedicated P73 GitHub Actions workflow runs:
1. Python compile check;
2. `pip-audit -r requirements.txt`;
3. complete Python test suite, including owner isolation, approval/replay, durable audit, memory/checkpoint persistence, backup/restore and UI action-audit tests;
4. Android/desktop Chromium responsive browser smoke tests.

The exact latest-head result must be read from GitHub Actions. A pass on an earlier commit does not certify a later commit. The latest known completed baseline before the UI action-audit integration was:
- Python suite: 1,373 passed, 9 skipped;
- dependency audit: no known vulnerabilities found;
- Chromium smoke: 9 passed.

The final P73 head after the subsequent UI action-audit integration and documentation updates still requires its own completed CI run before a final PASS statement is made.

## 3. Android acceptance boundary

The current client is a responsive Streamlit web application. It is not a native APK and is not yet an installable PWA.

Automated viewport and Chromium tests are supplemental only. Physical Android A01–A12 checks remain BLOCKED until the owner has a private HTTPS/authenticated test environment and performs the checks on the actual Android phone. Live OIDC login/logout/session expiry, two-account grant/revoke and independent evidence review also remain external acceptance gates.

## 4. Safety and product scope

- One owner; Android-primary.
- Free-only; no paid API/provider, paid hosting or billable service.
- Ask First; Auto-Run OFF.
- No payment, purchase, checkout, trading, investment orders or money movement.
- No public signup, anonymous access, LAN/public exposure, deployment or merge.
- No secret, PIN, recovery code, token, cookie or private key committed.
- PR #13 remains Draft/Open/Unmerged and stacked on PR #12.
- C02 must not start until C01 is complete and the owner explicitly approves C01.

## 5. Remaining before C01 closure

1. Review exact final-head CI and fix any failures.
2. Run an owner-operated backup/restore drill on the intended Android/host environment.
3. Complete physical Android A01–A12 and live private HTTPS/OIDC owner session checks.
4. Complete independent review of the redacted evidence and exact tested SHA.
5. Close remaining external protected-key, anti-rollback-anchor, real-host network and operational recovery gates required by the C01 closure checklist.

**Current disposition:** Repository implementation is substantially complete, but C01 remains OPEN / NOT COMPLETE while external acceptance and exact-head final verification remain. C02 remains NOT STARTED.
