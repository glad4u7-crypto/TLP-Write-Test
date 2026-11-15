# APAA-S04-C01-P08-P08-J — CI Verification & Final Security Review

Review date: 2026-11-15
Repository: `glad4u7-crypto/TLP-Write-Test`
Review branch: `feature/approval-ui-e2e-p06`
Reviewed application code snapshot: `84214318fe255d47df5638fbf27bb5f656c8a771`; latest dependency-audit workflow commit: `7d0b0ba2958db3b33bdaa6d028fa3df8a6c458d`
Pull request: #5 (open, draft; base `feature/agent-v0.3-zero-cost-core`)

## 1. CI verification

The reviewed code snapshot passed all three GitHub Actions runs:

| Workflow | Run | Event | Result |
|---|---:|---|---|
| Python Demo CI | #362 / 43675754475 | pull_request | PASS |
| Python Demo CI | #361 / 43675750878 | push | PASS |
| Agent Foundation CI | #271 / 43675750882 | push | PASS |

Verified job steps:
- Python Demo CI: dependency installation, pytest suite, and `demo.py` smoke test.
- Agent Foundation CI: dependency installation, `compileall` for `app.py`, `core`, and `tests`, and foundation pytest suite.

The application-code snapshot `84214318fe255d47df5638fbf27bb5f656c8a771` passed all three runs above. During this review, a first workflow-permission edit was malformed because `workflow_dispatch` was placed under `permissions`; GitHub Actions correctly reported workflow validation failures on commits `db18de13...` and `ebdb886c...`. This was identified from the failed runs and corrected in commit `81a07587437e145ebcc683e6e80ba1e42a452a75`, which restores `workflow_dispatch` under `on` and scopes `permissions: contents: read`. The corrected workflow was subsequently verified on commit `7d0b0ba...`; all four current-head push/PR workflow runs passed. The `pip-audit` step passed on both Foundation CI events and reported `No known vulnerabilities found`. Do not conceal the transient earlier workflow-validation failures.

## 2. Security controls verified in code/tests

- Project mutations use a two-step review/explicit-confirm UI flow.
- Approval receipts are short-lived, HMAC-signed, action- and payload-bound, and single-use.
- Durable approval nonce consumption is tenant-scoped by issuer + subject and uses SQLite transactions.
- Project persistence uses issuer + subject ownership checks.
- OIDC claim adapter rejects missing, malformed, expired, and future-issued identity claims.
- Session identity changes clear pending project data, selected project, approval authority, execution gateway, task drafts, tenant-bound registry, and approval session scope.
- Logout clears identity-bound session state before invoking Streamlit logout.
- Execution gateway dispatches only registered handlers and persists audit intent before invoking a handler when durable audit is configured.
- Local JSONL audit uses a hash chain and safe file-open checks; SQLite audit uses transactional writes and chain verification.
- Current registered execution scope is limited to the project workflow. No real-world file, email, browser, shell, arbitrary network, or device handlers are enabled.
- Payment, purchase, checkout, trading, money movement, paid-provider activation, and API charges remain prohibited/disabled. Auto-Run remains disabled by default.

## 3. Final findings and release gates

### BLOCKER — Live OIDC/browser verification not completed
No configured live OIDC provider, deployment URL, or two controlled test identities were available. Automated claim-adapter tests do not prove real login redirects, cookie/session handling, logout invalidation, CSRF resistance, or cross-browser isolation.

Required: execute the P08-P06 live-auth matrix with two separate identities and isolated browser profiles; record redacted evidence for login, owner isolation, logout/account switch, and approval replay denial.

### BLOCKER — Deployment authentication must be explicitly enforced
The app supports local prototype mode when `[apaa].require_auth` is false or absent. That mode is intentionally unauthenticated and must never be exposed publicly. A deployment must set `require_auth = true`, configure OIDC, and provide a protected stable approval signing secret of at least 32 bytes.

### HIGH — Production capability isolation is absent
ApprovalAuthority and ExecutionGateway are trusted in-process Python capabilities. This is not a sandbox against arbitrary code running in the same process. Do not register real-world or irreversible handlers until the approval issuer and execution broker are isolated behind a narrow trusted service boundary.

### HIGH — Audit operations and recovery need production controls
SQLite transactional nonce/audit storage improves process-safe local persistence, but it is not a centralized tamper-evident audit service. Production still needs protected storage, access controls, backup/retention, monitoring, recovery, and reconciliation for a side effect whose completion audit write fails.

### HIGH — Deployment topology and storage hardening remain
Local SQLite project/security databases do not by themselves establish a tested multi-host deployment model. Validate filesystem permissions, backup/restore, concurrent workers, database locking, and operational recovery before multi-worker production use.

### RESOLVED — CI workflow least privilege / PR coverage
The Agent Foundation workflow previously relied on repository-default token permissions and only ran PR events targeting `main`, while PR #5 targets `feature/agent-v0.3-zero-cost-core`. The workflow has now been corrected to explicit `contents: read` permission, includes that PR base branch, and retains the `workflow_dispatch` trigger. An initial malformed edit caused two workflow-validation failures; the syntax was corrected in commit `81a07587437e145ebcc683e6e80ba1e42a452a75`. Current-head CI on `7d0b0ba...` passed: Foundation push `43676566026`, Demo push `43676566108`, Foundation PR `43676570288`, and Demo PR `43676570332`. Dependency audit also passed with no known vulnerabilities reported.

## 4. Release decision

**NOT APPROVED for production, public deployment, or real-world execution.**

The code snapshot has passing automated CI and useful prototype security controls. The outstanding live-authentication and production-boundary findings remain release blockers. Keep PR #5 in draft. Do not merge or enable real-world handlers based on CI success alone.

## 5. Next checkpoint

1. Re-run CI after the latest documentation corrections and record any failures.
2. Complete P08-P06 live OIDC/browser matrix with two identities.
3. Review deployment configuration and durable storage operations.
4. Reassess production approval only after the blockers are closed and independently verified.

Safety policy remains unchanged: no payments or purchases; no paid API/provider activation or charges; no automatic execution by default.

## P08-P08-Q — Current-head regression verification addendum

Verification date: 2026-11-15
Current PR head reviewed: `64a5d65fa9481f16b4fcfe90947b9a478ff623e8`
Commit message: `Assert identity switch clears approval session scope`

The current PR head was checked after the P08-P08-Q session-security regression assertion was added.

| Workflow | Run | Event | Result |
|---|---:|---|---|
| Python Demo CI | #396 / 43678014330 | pull_request | PASS |
| Agent Foundation CI | #304 / 43678014322 | pull_request | PASS |

Verified completed job steps:
- Python Demo CI: dependency installation, full pytest suite, and `demo.py` smoke test.
- Agent Foundation CI: dependency installation, `pip-audit`, module compilation, and foundation pytest suite.

The specific P08-P08-Q test change adds `approval_session_scope` to the identity-switch cleanup fixture and asserts that the old identity's approval scope is removed. The implementation's identity-bound key list already includes this scope. No application runtime code was changed by this checkpoint.

The PR remains open and Draft. This CI result does not satisfy the outstanding live OIDC/browser verification or production release gates. No merge, deployment, provider activation, or real-world handler enablement is authorized.

## Next serial work

Proceed with the next offline-verifiable security review item on the existing feature branch. Prioritize tests that can be completed without provider credentials or a deployment. The live P08-P06 browser matrix remains blocked until the operator supplies a configured test OIDC deployment and two controlled test identities. Keep production status **NOT APPROVED**.


## P08-P08-W — SQLite journal and sidecar permission regression verification

Verification date: 2026-11-15
Reviewed code head: `19e043adb9f5fda885aa68e83029e2f58d800380`

This checkpoint adds regression tests to the three existing SQLite store test modules; no new files or runtime code changes were required:

- `tests/test_sqlite_project_store.py`: rollback-journal permission test for the tenant-scoped project store.
- `tests/test_sqlite_security_store.py`: rollback-journal permission test for the approval nonce/audit store.
- `tests/test_sqlite_storage.py`: rollback-journal permission test for the legacy project store.

The tests explicitly select SQLite DELETE journal mode, hold a write transaction to force journal creation, and assert POSIX mode `0600` for the journal and main database. The prior P08-P08-V tests cover WAL and SHM sidecars with the same owner-only permission expectation.

Current-head GitHub Actions verification for `19e043adb9f5fda885aa68e83029e2f58d800380`:

| Workflow check | Result |
|---|---|
| Agent Foundation CI — push | PASS |
| Python Demo CI — push | PASS |
| Agent Foundation CI — PR | PASS |
| Python Demo CI — PR | PASS |

All four check-runs completed successfully. The tests are POSIX-only and are skipped on non-POSIX platforms; this does not constitute cross-platform filesystem permission verification.

No runtime implementation was changed in P08-P08-W. These tests provide evidence for the current tested POSIX environment only; they do not eliminate same-user filesystem tampering, TOCTOU races, multi-host SQLite limitations, or the outstanding live OIDC/browser release blocker.

PR #5 remains open and Draft. No merge, deployment, provider activation, or real-world handler enablement is authorized. Production remains **NOT APPROVED**.

## Next serial work after P08-P08-W

Continue the offline-verifiable review in small increments. Reassess SQLite path and connection lifecycle assumptions without weakening the existing permission checks. Live P08-P06 OIDC/browser verification remains blocked until a configured test deployment and two controlled identities are available.


## P08-P08-Y — SQLite path and connection-lifecycle review

Verification date: 2026-11-15
Reviewed branch head before this documentation update: `0c5e15f9e9e9c5f75d8bafefd88da3fa3292e5b0`

Reviewed the existing implementations and regression tests in:

- `core/sqlite_storage.py` (legacy tenant-scoped project store)
- `core/sqlite_project_store.py` (persistent tenant-scoped project store)
- `core/sqlite_security_store.py` (approval nonce and durable audit store)
- Their three existing SQLite test modules.

### Findings

1. All three stores apply the same essential initialization-time filesystem policy for file-backed databases: inspect lexical parent components for symlinks, require a private POSIX parent directory, pre-create a missing database with owner-only mode where supported, reject a symlink/non-regular target, and apply mode `0600`.
2. The existing P08-P08-V/W regression tests cover WAL/SHM sidecars and rollback journals in the tested POSIX environment. This is useful regression evidence, not a universal guarantee across filesystems or operating systems.
3. Each store's `_connect()` opens the configured path directly and does not repeat the filesystem checks. The checks therefore protect initialization and detect an unsafe path at that time; they are not a per-connection defense against a later path replacement.
4. A process running under the same OS account, or an attacker able to modify the private parent directory, may be able to race or replace filesystem objects after validation. The current path-based SQLite API does not establish race-free protection against that threat. Do not describe these stores as safe against hostile same-user code or arbitrary same-account compromise.
5. No safe, portable runtime change was justified by this review alone. Introducing descriptor-based SQLite opening or connection-time path checks without a well-defined supported-platform contract could create false confidence and platform regressions. No runtime code or tests were changed in P08-P08-Y.

### Decision and next action

Retain the existing owner-only directory/file controls and explicitly preserve the same-user/TOCTOU limitation in the threat model. Before attempting stronger hardening, define supported operating systems, filesystem assumptions, and whether hostile same-account processes are in scope; then design and test a platform-specific approach rather than adding a superficial re-check.

The live OIDC/browser matrix remains blocked pending a configured test deployment and two controlled identities. PR #5 remains open and Draft. No merge, deployment, paid-provider activation, or real-world handler enablement is authorized. Production remains **NOT APPROVED**.

## Next serial work after P08-P08-Y

Continue with the next offline-verifiable review item, prioritizing concrete authorization and failure-path tests over speculative filesystem changes. Keep the existing repository files and architecture stable; do not add new files unless a demonstrated requirement needs one.
