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


## P08-P09-AG — SQLite audit crash-recovery regression

Verification date: 2026-11-15  
Reviewed PR head: `a04d30d959c3eb80c193c8707ac7e1c7d919b077`

### Work completed
- Added `test_sqlite_recovers_uncommitted_audit_event_after_process_crash` to the existing `tests/test_sqlite_security_store.py`; no new file or runtime implementation change was needed.
- The test creates a committed audit event, starts a spawned child process, writes a second event inside an uncommitted SQLite transaction, and terminates the child abruptly with `os._exit(0)`.
- After reopening the store, it verifies the committed event and hash-chain head remain intact, the uncommitted event is absent, and a subsequent committed append succeeds.
- Existing nonce crash-recovery and multi-process nonce/audit concurrency tests remain in the same test module.

### Current-head CI evidence
Both required workflows completed successfully for this exact PR head:

| Workflow | Run | Result |
|---|---:|---|
| Python Demo CI | #476 / 43685211540 | PASS |
| Agent Foundation CI | #386 / 43685211513 | PASS |

Python Demo CI completed dependency installation, the test suite, and the `demo.py` smoke test. Agent Foundation CI completed dependency installation, dependency audit, module compilation, and foundation tests.

### Scope and release status
This verifies the automated crash-recovery regression in the GitHub Actions environment; it does not prove power-loss durability across every filesystem, host, or storage controller. The existing limitations around local SQLite deployment topology, protected audit anchoring, live OIDC/browser verification, and production capability isolation remain open.

PR #5 remains open and Draft. No merge, deployment, paid-provider activation, payment, trading, or real-world handler enablement is authorized. Production remains **NOT APPROVED**.


## P08-P09-AK — Documentation CI and authenticated-runtime regression review

Verification date: 2026-11-15  
Reviewed PR head: `b00272d25a373d96fba6d842eddd2dc9be5f69b6`

### Current-head CI evidence

The two documentation updates in P08-P09-AJ completed all four associated workflow runs successfully:

| Workflow | Run | Commit | Result |
|---|---:|---|---|
| Python Demo CI | #483 / 43685624423 | `7c55186dae9f31637cea65e2d3d04feae1ffb560` | PASS |
| Agent Foundation CI | #393 / 43685624537 | `7c55186dae9f31637cea65e2d3d04feae1ffb560` | PASS |
| Python Demo CI | #484 / 43685627642 | `b00272d25a373d96fba6d842eddd2dc9be5f69b6` | PASS |
| Agent Foundation CI | #394 / 43685627624 | `b00272d25a373d96fba6d842eddd2dc9be5f69b6` | PASS |

Verified job steps include dependency installation, full pytest suite, demo smoke test, dependency audit, module compilation, and foundation tests, as applicable to each workflow.

### Additional read-only code review

Reviewed the existing `app.py`, `core/session_security.py`, `core/streamlit_auth.py`, `core/sqlite_security_store.py`, `core/sqlite_project_store.py`, and their existing session, OIDC, approval, and persistent-project tests.

- Authenticated runtime derives the principal from Streamlit OIDC claims; identity is not accepted from UI input.
- Authenticated mode fails closed when OIDC configuration is absent, the stable approval signing secret is missing/too short, or durable SQLite storage cannot be initialized.
- The authenticated path uses issuer + subject tenant scoping, durable one-time approval nonce storage, SQLite execution audit, and persistent project storage.
- Logout clears identity-bound Streamlit session state before calling Streamlit logout; identity transitions clear prior approval scope, gateway, registry, and user-specific drafts.
- Existing automated tests cover malformed/expired/future OIDC claims, identity-switch cleanup, logout cleanup, stale receipt rejection, cross-session approval replay rejection, cross-tenant project access denial, and persistent gateway audit intent/completion/fail-closed behavior.

No additional runtime change was justified by this read-only review. No new files were created.

### Remaining blockers

Automated CI and claim-adapter tests do not replace a live OIDC deployment test with two controlled identities and isolated browser profiles. The deployment must explicitly enforce `[apaa].require_auth = true`, use protected stable signing material, and validate logout/session invalidation and tenant isolation in a real browser environment.

The local SQLite stores remain single-host-oriented operational components, not a verified multi-host service. Protected backup/retention/monitoring/recovery and independent audit anchoring remain production requirements. In-process Python approval/execution capabilities are not a sandbox against hostile code in the same process. The existing same-account filesystem/TOCTOU limitation remains unchanged.

PR #5 remains open and Draft on `feature/approval-ui-e2e-p06`, targeting `feature/agent-v0.3-zero-cost-core`. No merge, deployment, paid-provider activation, payment, purchase, trading, or real-world handler enablement is authorized. Auto-Run remains disabled. Production remains **NOT APPROVED**.


## P08-P09-AL — Live OIDC verification runbook and current-head CI

Verification date: 2026-11-15  
Reviewed PR head before this documentation-only update: `f340110237674d61f3a769a336379b9e78e62861`

### Current-head CI evidence

Both required workflows completed successfully for the reviewed head:

| Workflow | Run | Result |
|---|---:|---|
| Python Demo CI | #487 / 43685779467 | PASS |
| Agent Foundation CI | #397 / 43685779485 | PASS |

The earlier #486/#396 runs were also successful; #487/#397 are the later runs attached to the same reviewed commit.

### Controlled live OIDC verification procedure

This is a manual release-gate procedure, not a claim that live testing has already occurred. Use only a private test deployment, a test OIDC client, two operator-controlled non-production identities (A and B), and two isolated browser profiles. Never place real access tokens, ID tokens, client secrets, signing secrets, or session cookies in screenshots, logs, or this repository.

Preconditions:
1. Configure the test deployment's Streamlit OIDC provider using the provider's supported secrets format.
2. Set `[apaa].require_auth = true`; verify the unauthenticated app cannot reach project or approval functionality.
3. Configure a high-entropy stable `approval_signing_secret_hex` decoding to at least 32 bytes. Store it only in the deployment secret manager.
4. Configure private writable security/project database paths and verify owner-only filesystem permissions on the supported POSIX test host.
5. Keep Auto-Run disabled and use only the existing project-create test action. Do not register file, shell, browser, network, email, device, payment, trading, or other real-world handlers.

Execution matrix and evidence to record (redacted, with timestamps and pass/fail only):
- **Unauthenticated access:** open a fresh private profile; confirm login is required and no project data/actions are exposed.
- **Identity A login:** sign in as A; create a harmless uniquely named test project after reviewing and explicitly confirming it; verify the project is listed for A.
- **Identity B isolation:** in a separate private profile, sign in as B; verify A's project is not listed, readable, editable, or deletable by B.
- **Approval binding:** issue a test approval in A's session; verify a changed payload, different action, expired receipt, replayed receipt, and receipt presented by B are all rejected.
- **Logout invalidation:** log out A; verify the prior session cannot access authenticated project/approval functions and its pre-logout receipt cannot be reused after a fresh login.
- **Account switch:** where the provider supports it, switch A to B in the same browser profile; verify old drafts, selected project, approval authority, gateway and session scope are cleared before B's state is initialized.
- **Session separation:** keep A and B sessions open simultaneously in isolated profiles; verify actions and project lists remain tenant-scoped.
- **Failure behavior:** in a disposable test deployment only, test missing/invalid OIDC configuration and unavailable/unwritable durable stores; the app must stop rather than fall back to unauthenticated or ephemeral authenticated execution.

Acceptance: every case passes, evidence is redacted, no secrets are committed, and a reviewer independently checks the evidence and deployment configuration. Any failure blocks release and must be fixed and retested. Do not use production customer identities or production data for this matrix.

### Boundaries

This runbook does not prove CSRF/cookie protections, provider configuration correctness, deployment isolation, or multi-host storage behavior until executed against the actual test deployment. Live OIDC/browser verification remains **PENDING** until the operator supplies that deployment and two controlled test identities. PR #5 remains open and Draft; no merge or deployment is authorized. Production remains **NOT APPROVED**.

## P08-P09-AM — Live OIDC runbook documentation CI verification

Verification date: 2026-11-15  
Reviewed PR head: `bf37656745867314563a264aad476f02e53fab1e`

### Current-head CI evidence

The documentation-only follow-up adding the controlled two-identity live OIDC/browser runbook has now completed both required workflows for both push and pull-request events:

| Workflow | Event | Run ID | Result |
|---|---|---:|---|
| Python Demo CI | push | 43687284417 | PASS |
| Agent Foundation CI | push | 43687284390 | PASS |
| Python Demo CI | pull_request | 43687286798 | PASS |
| Agent Foundation CI | pull_request | 43687286774 | PASS |

All four runs report the exact reviewed head `bf37656745867314563a264aad476f02e53fab1e` and completed successfully. The PR-triggered checks confirm the workflow coverage for the PR's actual base branch, `feature/agent-v0.3-zero-cost-core`.

### Review outcome

- No application runtime code was changed in this documentation-only follow-up.
- The existing live OIDC/browser matrix remains a procedure only; it has not been executed.
- No new runtime security claim is inferred from the documentation CI result.
- PR #5 remains open and Draft on `feature/approval-ui-e2e-p06`.
- No merge, deployment, paid-provider activation, payment, purchase, trading, or real-world handler enablement is authorized.
- Auto-Run remains disabled. Production remains **NOT APPROVED**.

### Next serial work

Continue the offline-verifiable review with focused fail-closed authenticated-runtime and durable-storage initialization tests. Do not attempt live OIDC verification until a private test deployment and two controlled non-production identities are available.


## P08-P09-AQ — Auth-required OIDC fail-closed regression and CI verification

Verification date: 2026-11-15  
Reviewed PR head: `95b33e9aacb97c1bf01ba6029287d3fee37e7d60`

### Work completed

- Added an AppTest regression in `tests/test_app_smoke.py` that enables `[apaa].require_auth = true` while omitting the OIDC `[auth]` configuration.
- The test verifies the app stops with an authentication-configuration error before rendering any interactive action buttons.
- The first test attempt used a temporary `.streamlit/secrets.toml`. CI exposed that Streamlit caches file-backed secrets across AppTest runs in the same Python process, contaminating later local-prototype tests. That first attempt failed and was not accepted.
- Corrected the test to monkeypatch the module-level `st.secrets` mapping for the duration of the test. Pytest restores the original mapping afterward, avoiding shared configuration state and preserving test isolation.
- No runtime application code or production configuration was changed.

### Current-head CI evidence

All four GitHub Actions runs completed successfully for the exact reviewed commit:

| Workflow | Event | Run ID | Result |
|---|---|---:|---|
| Python Demo CI | push | 43688903523 | PASS |
| Agent Foundation CI | push | 43688903518 | PASS |
| Python Demo CI | pull_request | 43688907488 | PASS |
| Agent Foundation CI | pull_request | 43688907570 | PASS |

Verified job steps:
- Python Demo CI: dependency installation, full pytest suite, and `demo.py` smoke test.
- Agent Foundation CI: dependency installation, `pip-audit`, module compilation, and foundation tests.

The failed first attempt on `f10d34523fffac8aac0bad84092fc18f7604f07c` was investigated and corrected in `95b33e9aacb97c1bf01ba6029287d3fee37e7d60`; the successful results above are for the corrected commit only.

### Scope and release status

This test proves the local AppTest branch stops when authentication is required but OIDC configuration is absent. It does not prove live OIDC redirects, real-browser cookie/session handling, CSRF resistance, two-identity isolation, or deployment configuration.

PR #5 remains open and Draft on `feature/approval-ui-e2e-p06`, targeting `feature/agent-v0.3-zero-cost-core`. The base branch is not changed by this work. No merge, deployment, paid-provider activation, payment, purchase, trading, or real-world handler enablement is authorized. Auto-Run remains disabled. Production remains **NOT APPROVED**.

### Next serial work

Continue with the next offline-verifiable authenticated-runtime failure-path case, prioritizing stable signing-secret validation and durable project/security-store initialization failures. Keep changes focused, test each failure mode, and verify all four CI runs before advancing. The live two-identity OIDC/browser matrix remains pending a private test deployment and two controlled non-production identities.


## P08-P09-AR — Authenticated runtime signing-secret and SQLite path fail-closed regressions

Verification date: 2026-11-15  
Reviewed PR head: `45c9d4c65a9f302d5144ed097139879b8037123f`

### Work completed

- Extended the existing `tests/test_app_smoke.py` AppTest coverage for authenticated runtime initialization failures; no new files and no runtime implementation changes were required.
- Added a test proving an authenticated session with an approval signing secret shorter than the required 32 decoded bytes stops with a durable-security-configuration error.
- Added a test proving a symlinked security-database parent path is rejected before the application exposes project/task actions; the external sentinel file remains unchanged.
- Both failure tests explicitly permit the Logout control, which is rendered before durable-store initialization. They assert that Logout is the only button remaining after the fail-closed stop.
- The first test assertion incorrectly expected zero buttons and failed because the safe Logout control is intentionally rendered before storage initialization. The failure was reviewed from the CI log and the assertions were corrected to require exactly the Logout button. The corrected code is the only version accepted below.

### Current-head CI evidence

All four required GitHub Actions runs completed successfully for the exact reviewed commit:

| Workflow | Event | Run ID | Result |
|---|---|---:|---|
| Python Demo CI | push | 43690554699 | PASS |
| Agent Foundation CI | push | 43690554702 | PASS |
| Python Demo CI | pull_request | 43690558817 | PASS |
| Agent Foundation CI | pull_request | 43690558826 | PASS |

Verified steps:
- Python Demo CI: dependency installation, full pytest suite, and `demo.py` smoke test.
- Agent Foundation CI: dependency installation, `pip-audit`, module compilation, and foundation test suite.
- The dependency audit reported no known vulnerabilities.

### Scope and release status

These tests verify the local AppTest behavior for a short signing secret and an unsafe SQLite security database path. They do not prove real deployment secret-manager configuration, live OIDC redirects, browser cookie/session controls, CSRF resistance, multi-identity isolation, or protection from same-account filesystem races. Project-database initialization failure remains a separate failure-path case for subsequent review.

PR #5 remains open and Draft on `feature/approval-ui-e2e-p06`, targeting `feature/agent-v0.3-zero-cost-core`. No merge, deployment, paid-provider activation, payment, purchase, trading, or real-world handler enablement is authorized. Auto-Run remains disabled. Production remains **NOT APPROVED**.

### Next serial work

Continue with the authenticated project-database initialization failure path and confirm that no project/task actions are exposed if the security store initializes but the project store cannot. Then reassess the authenticated runtime's partial-initialization and session-state behavior. Live OIDC/browser verification remains pending a private test deployment and two controlled non-production identities.


## P08-P09-AS — Authenticated project-store initialization failure and partial-startup regression

Verification date: 2026-11-15  
Reviewed PR head: `b6d4cd425a3ed842d905e2546a457a942a77eda2`

### Work completed

- Added an AppTest regression in the existing `tests/test_app_smoke.py`; no new files and no runtime application changes were required.
- The test configures a valid authenticated test principal, a valid 32-byte approval signing secret, and a safe private security-database path.
- It deliberately supplies a symlinked parent directory for the project database so `SQLiteProjectStore` initialization fails after `SQLiteSecurityStore` has initialized successfully.
- It verifies the security database was created, the project database was not created through the symlink, the app stops with the durable-storage error, and Logout is the only remaining button. No project or task actions are exposed after the partial initialization.
- This is a regression test for safe startup failure, not proof of a full transactional rollback of the security database file. The security store is initialized before the project store and its file may remain after the app stops; no authenticated execution path is exposed.

### Current-head CI evidence

All four required GitHub Actions runs completed successfully for the exact reviewed commit:

| Workflow | Event | Run ID | Result |
|---|---|---:|---|
| Python Demo CI | push | 43690660413 | PASS |
| Agent Foundation CI | push | 43690660416 | PASS |
| Python Demo CI | pull_request | 43690664045 | PASS |
| Agent Foundation CI | pull_request | 43690664019 | PASS |

Verified steps include dependency installation, full pytest suite, `demo.py` smoke test, `pip-audit`, Python module compilation, and foundation tests. The dependency audit reported no known vulnerabilities.

### Scope and release status

This verifies the AppTest startup behavior when project-store initialization fails after security-store initialization. It does not prove live OIDC redirects, browser cookie/session controls, CSRF resistance, multi-identity browser isolation, secret-manager correctness, or protection from same-account filesystem races. The prior P09-AR signing-secret and security-database path regressions remain covered and the complete four-run CI matrix passes at this head.

PR #5 remains open and Draft on `feature/approval-ui-e2e-p06`, targeting `feature/agent-v0.3-zero-cost-core`. No merge, deployment, paid-provider activation, payment, purchase, trading, or real-world handler enablement is authorized. Auto-Run remains disabled. Production remains **NOT APPROVED**.

### Next serial work

Review authenticated-runtime partial initialization and session-state recovery after a durable-store failure, including a rerun/retry scenario in the same Streamlit session. Preserve the fail-closed behavior and avoid leaving stale approval authority, execution gateway, or tenant-bound project registry state reachable. Live OIDC/browser verification remains pending a private test deployment and two controlled non-production identities.


## P08-P09-AT — Same-session durable-store failure cleanup and safe retry

Verification date: 2026-11-15  
Reviewed code commit: `398875292f99158cf4266645ae3e6326677da2c0`

### Work completed

- Updated the authenticated durable-store initialization failure handler in `app.py` to call `clear_session_identity(st.session_state)` before stopping the app.
- This clears identity-bound state from the failed session, including the approval authority, execution gateway, gateway owner, session approval scope, tenant-bound project registry, pending project draft, selected project, and prepared task state.
- Added an AppTest regression that starts an authenticated session successfully, changes the project database path to a rejected symlink path, and reruns the same Streamlit session.
- The test verifies the app fails closed and clears all identity-bound capabilities/state. It then restores a valid database path and reruns the same session, verifying a fresh approval authority and gateway are initialized and the tenant-bound registry is restored.
- The first test attempt used ordinary directory permissions and correctly failed the SQLite store's private-directory requirements. The fixture was corrected to create private directories with mode `0700`; the first failed run was not accepted as verification.

### Current-head CI evidence

All four required GitHub Actions runs completed successfully for the exact reviewed commit:

| Workflow | Event | Run ID | Result |
|---|---|---:|---|
| Python Demo CI | push | 43690911915 | PASS |
| Agent Foundation CI | push | 43690911926 | PASS |
| Python Demo CI | pull_request | 43690915454 | PASS |
| Agent Foundation CI | pull_request | 43690915411 | PASS |

Verified steps include the full pytest suite, `demo.py` smoke test, dependency audit, Python module compilation, and foundation tests.

### Scope and release status

This verifies the AppTest same-session failure/retry path under controlled configuration changes. It does not prove real-browser OIDC redirects, cookie/session handling, CSRF resistance, two-identity browser isolation, deployment secret-manager behavior, or filesystem protection against same-account races.

PR #5 remains open and Draft on `feature/approval-ui-e2e-p06`, targeting `feature/agent-v0.3-zero-cost-core`. No merge, deployment, paid-provider activation, payment, purchase, trading, or real-world handler enablement is authorized. Auto-Run remains disabled. Production remains **NOT APPROVED**.

### Next serial work

Review cached approval-authority lifecycle when an authenticated deployment rotates its signing secret or changes its durable security database path during a live session. Ensure a changed security configuration cannot silently reuse an authority bound to the previous secret/store. Keep the authority server-side, never log or expose signing material, and add regression tests before claiming the rotation path is safe. Live OIDC/browser verification remains pending a private test deployment and two controlled non-production identities.


## P08-P09-AU — Approval authority configuration rotation and stale receipt invalidation

Verification date: 2026-11-15  
Reviewed code commit: `1ab9d03c9261a99f85b6f5aa21e6fa85ce0340fb`

### Work completed

- Bound the authenticated session's cached approval authority to a keyed configuration identifier derived with HMAC-SHA256 from the validated signing secret and the absolute durable nonce-store path.
- The configuration identifier is non-reversible and does not expose or retain the signing secret. It is stored only in identity-bound Streamlit session state and is cleared on identity transition, logout, or fail-closed durable-store initialization.
- When the signing secret or nonce-store path changes, the app invalidates the cached approval authority and execution gateway and rotates the approval session scope. This rejects receipts issued under the previous configuration, including receipts whose nonce is unknown to a newly selected database.
- Added an authenticated AppTest regression that issues a receipt, rotates only the signing secret, and verifies the old receipt is rejected; it then issues another receipt, changes only the durable security database path, and verifies that receipt is rejected too. Both rotations are checked for fresh authority/gateway objects and a changed session scope.
- The test performs no project creation or external execution.

### Current-head CI evidence

All four required GitHub Actions checks completed successfully for the exact reviewed code commit:

| Workflow | Event | Run ID | Result |
|---|---|---:|---|
| Python Demo CI | push | 43691991479 | PASS |
| Agent Foundation CI | push | 43691991471 | PASS |
| Python Demo CI | pull_request | 43691996216 | PASS |
| Agent Foundation CI | pull_request | 43691996223 | PASS |

The four check runs on commit `1ab9d03c9261a99f85b6f5aa21e6fa85ce0340fb` report `completed/success`. The workflows cover the Python demo test suite and smoke test, dependency audit, Python compilation, and foundation tests.

### Scope and release status

This verifies in-process AppTest behavior for signing-secret and nonce-store-path rotation. It does not establish real-browser OIDC behavior, deployment secret-manager rotation procedures, browser cookie/session controls, CSRF resistance, or multi-identity isolation in a live deployment. A process restart naturally discards in-memory Streamlit session state; operational secret rotation and rollback still require a controlled deployment procedure.

PR #5 remains open and Draft on `feature/approval-ui-e2e-p06`, targeting `feature/agent-v0.3-zero-cost-core`. No merge, deployment, paid-provider activation, payment, purchase, trading, or real-world handler enablement is authorized. Auto-Run remains disabled. Production remains **NOT APPROVED**.

### Next serial work

Continue S04 with an offline-verifiable review of authenticated session binding and approval-scope lifecycle across identity transitions, logout, and partially restored session state. Add focused tests for configuration-fingerprint cleanup and ensure no old gateway or receipt context survives. Live OIDC/browser verification remains blocked on a private test deployment and two controlled non-production identities.
