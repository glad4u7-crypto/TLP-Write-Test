# APAA Personal Edition — P73 Runtime, Persistence and Acceptance

**Checkpoint:** APAA-PERSONAL-P73  
**Date:** 2026-11-17  
**Branch:** `apaa-personal-edition-foundation`  
**Status:** P73 repository implementation has prior exact-head automated PASS evidence; the latest Owner-security/action-approval changes are awaiting their own exact-head CI. Physical/external acceptance gates remain.  
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
- Memory, knowledge, conversation, preference and checkpoint mutations use a fail-closed metadata-only audit wrapper. Each call now requires an explicit approval argument: save forms bind to the corresponding consent checkbox and delete actions bind to the named Owner delete button.
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

**Exact verified PR head:** `5962d0a94fe26ab3eb9db4c56e3c6702039e9611`  
**GitHub Actions run:** [P73 Verification #43990846404](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43990846404) — **PASS**.

- Python compile: PASS.
- Dependency audit: `pip-audit -r requirements.txt` — no known vulnerabilities found.
- Complete Python suite: **1,381 passed, 9 skipped**.
- Android/desktop Chromium smoke: **9 passed**.
- Both workflow jobs completed successfully on the exact PR head.

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

**Current disposition:** P73 repository implementation and exact-head automated verification are PASS. S09 C01 remains OPEN / NOT COMPLETE because physical Android, live private HTTPS/OIDC, owner-operated recovery drill, independent key/anti-rollback and real-host review gates remain. C02 remains NOT STARTED.


## 6. P74 preparation completed

The following repository documents were added on the Personal Edition branch:
- [P74 Browser Security Gate Design](APAA_PERSONAL_EDITION_P74_BROWSER_SECURITY_GATE_DESIGN.md) — specifies exact-origin, redirect, DNS rebinding, SSRF, TLS, session isolation, egress, cancellation, upload/download, approval and audit gates. This is a design contract only; Browser execution remains DISABLED.
- [P74 Android Owner Acceptance Runbook](APAA_PERSONAL_EDITION_P74_ANDROID_ACCEPTANCE_RUNBOOK.md) — defines physical A01–A12 procedures, expected outcomes, evidence requirements and stop conditions. No physical Android tests are claimed as run.
- [P74 Final Verification Matrix](APAA_PERSONAL_EDITION_P74_FINAL_VERIFICATION_MATRIX.md) — consolidates repository, Android, identity, key custody, anti-rollback and real-host evidence requirements.

These additions complete the preparation/documentation work possible without a physical device, private HTTPS/OIDC environment, independent security reviewer or qualified network host. They do not implement a browser engine, create a native APK, or close C01.

**Updated disposition:** Browser Security design contract = DOCUMENTED; secure Browser implementation = NOT IMPLEMENTED / DISABLED. Android A01–A12 = PROCEDURE READY / NOT RUN. Final verification matrix = DOCUMENTED; final acceptance = OPEN. C01 remains OPEN; C02 remains NOT STARTED.


## 7. P74 Browser Security implementation work started

The existing offline browser policy module was hardened with:
- Additional rejection for local-use and reserved DNS suffixes (`localhost`, `local`, `internal`, `test`, `invalid`, `example`, `onion`).
- `PinnedDestination` and `validate_live_destination`: live DNS-name navigation requires an injected trusted resolver, validates the complete answer set, and returns the exact public addresses that a future connector must pin. Public IP literals are validated directly.
- `validate_redirect_chain`: every hop is revalidated, every hostname's DNS set is independently checked, redirects are bounded and loops rejected.
- New regression tests for reserved suffixes, missing resolver, DNS pinning, mixed public/private answers, IP literals, per-hop redirect resolution, DNS failure, redirect loops and hop limits.

**Exact implementation commit:** `eceae46d0c4fb2b70ee92fa298025e0548a799cd`.

**Verification:** GitHub Actions run [#43993237426](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43993237426) was started for this exact head. Its Python test and browser-smoke jobs were still running at the time of this update; do not mark the implementation verified until both jobs finish successfully.

**Not implemented / deliberately disabled:** no browser process, socket connector, TLS pinning/hostname-verification adapter, container sandbox, network egress firewall, browser session manager, download/upload path, or Browser/Worker ExecutionGateway handler was added. The returned pinned addresses are a contract for a future connector, not proof that network connections are currently pinned. Browser execution remains DISABLED.

P74 therefore has real policy code and regression coverage added, but Browser Security is not complete. Android A01–A12 remain procedure-ready/not run, and final acceptance remains open. C01 remains OPEN; C02 remains NOT STARTED.


### P74 latest-head correction
- Reserved suffix hardening intentionally rejects `.example`; an inherited IDN normalization test had used `bücher.example` as an accepted fixture. CI exposed the mismatch (1 failed, 1,393 passed, 9 skipped on the earlier snapshot); the fixture was corrected to `bücher.com`.
- Latest branch head after the fixture correction and verification notes: `7cf35d218a32edc4bb194633539653619548790e`.
- Exact-head workflow [#43993446488](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43993446488) is running on this latest head. Do not claim PASS until both Python tests and browser smoke complete successfully.


## 8. S09-C01 Owner, Permission & Approval Security — implementation started

- Added `core/personal_auth.py`: first-run single-Owner passphrase setup, salted scrypt verifier, constant-time comparison, persistent five-attempt/five-minute lockout, and authenticated passphrase rotation primitive.
- Wired the local Owner gate into `app.py` before local Principal, approval authority, execution gateway, project registry, memory or task UI initialization.
- Added explicit Unlock and Logout flows. Logout and 15-minute idle / 12-hour absolute expiry clear pending drafts, approval authority, gateway and identity-bound runtime state.
- Added `owner-auth.sqlite3` to canonical PersonalRuntime paths and included it in private backup/restore. Restore preserves the Owner verifier while still generating a fresh approval signing key, invalidating outstanding approval receipts.
- Added unit and Streamlit AppTest coverage for first-run setup, passphrase storage, wrong password, persistent lockout, passphrase rotation, login, logout, idle/absolute expiry and failed-login isolation.
- Updated existing local AppTest fixtures to authenticate through the new gate.

**Current code head:** `da83d1e0998948902524f3b1d8ae5590550e930f`.  
**Earlier CI feedback:** workflow run `44006192350` on the prior PR validation snapshot found seven test failures (lockout-boundary expectation, identity cleanup coverage, reusable test auth setup, and planner UI fixtures). The underlying issues were corrected in follow-up commits. That failed run is not evidence for the current head. Exact-head CI for `da83d1e0998948902524f3b1d8ae5590550e930f` remains PENDING / NOT OBSERVED. Do not mark this workstream PASS until the full P73 workflow completes successfully on the exact head.

**Owner passphrase-change UI and payload-free security-event history:** implemented on the current branch. The local auth event table is not independently tamper-proof.

**Action audit follow-up:** a code review found the common UI mutation wrapper self-supplied its approval value. The wrapper now requires an explicit boolean approval argument; all nine app mutation call sites pass the relevant Owner consent checkbox or the named delete-button event. Tests verify missing/non-boolean approval fails before audit intent or dispatch.

**Current latest source head:** to be recorded after the full exact-head CI for these changes. Previous exact-head CI results do not apply to the new approval-hardening commits.


## 9. Source-level action audit and browser-smoke fixture correction

A further source audit identified two verification weaknesses and corrected them on this branch:

1. The shared UI mutation wrapper previously supplied the action name as its own approval. It now requires an explicit boolean approval argument. All nine app call sites supply the matching Owner consent checkbox or the explicit named delete-button event. Missing approval and non-boolean approval fail before the intent audit and operation callback. Regression tests cover these paths and the existing fail-closed audit behavior.
2. Android and desktop Playwright smoke fixtures did not configure a test Owner or complete the mandatory Owner login before expecting the task UI. Both fixtures now create a test-only local Owner in an isolated temporary data directory and authenticate through the actual Unlock APAA screen before testing responsive UI and plan preparation. This is CI test data only; no real Owner credential is used.

The earlier run #90 had Python tests PASS while the browser-smoke job remained in progress. That run predates these fixture corrections and cannot verify the latest source. A fresh exact-head workflow is required.

The source review also reconfirmed that the local auth-event SQLite table is payload-free but not independently tamper-proof; this limitation remains documented. The execution audit hash chain remains a separate tamper-evident control.
