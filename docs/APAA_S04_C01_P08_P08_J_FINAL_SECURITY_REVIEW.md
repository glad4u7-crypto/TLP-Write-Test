## P08-P09-BG — Exact-head CI verification and S04 release-readiness matrix

Verification date: 2026-11-15  
Reviewed PR head: `50df9720e800ca37ad23bdfbfc2514efead96a01`  
Pull request: #5, open and Draft; head `feature/approval-ui-e2e-p06`, base `feature/agent-v0.3-zero-cost-core`

### Exact-head CI evidence

Both required workflows completed successfully for the exact reviewed head:

| Workflow | Check run | Result | Evidence |
|---|---:|---|---|
| Agent Foundation CI | `132753174707` | PASS | Full test suite: 378 passed; `pip-audit -r requirements.txt`: `No known vulnerabilities found`; `compileall` passed |
| Python Demo CI | `132753171299` | PASS | Full test suite: 378 passed; demo smoke test output exactly `Hello TradeLab Pro` |

The earlier `test` and `test-demo` runs on the same commit were cancelled by the configured concurrency policy when the corresponding PR/push runs superseded them. The completed runs above are successful and are the evidence used for this checkpoint. The workflow-policy regression test itself is included in the 378-test suite.

### Consolidated S04 gate matrix

| Gate | Status | Evidence / remaining action |
|---|---|---|
| Workflow action pinning, least-privilege permissions, bounded runtime, concurrency | PASS | Existing workflow configuration and `tests/test_ci_workflow_security.py`; exact-head CI passed |
| Python dependency audit | PASS (point-in-time) | `pip-audit` reported no known vulnerabilities for declared requirements on this run |
| Application compile and automated regression suite | PASS | `compileall` passed; 378 tests passed in both workflows |
| Demo smoke test | PASS | Exact expected output verified |
| Approval receipt lifecycle, replay prevention, audit fail-closed and crash recovery | PASS (automated scope) | Existing unit/integration tests passed; does not imply external side-effect safety |
| Tenant ownership, identity transition and logout cleanup | PASS (automated scope) | Existing OIDC adapter, storage and Streamlit AppTest suites passed |
| Live OIDC login/logout and two-user browser isolation | BLOCKED | Requires a private non-production deployment, configured OIDC test client, two controlled identities and isolated browser profiles |
| Repository branch protection / ruleset enforcement | BLOCKED / UNVERIFIED | Current GitHub integration cannot read the administrative settings; repository owner must inspect and confirm required reviews/status checks |
| Production capability isolation and external-action sandbox | BLOCKED | Approval/execution capabilities remain in-process; no hostile-code isolation or real-world handlers are approved |
| Production audit operations, backup/retention, independent anchoring and multi-host topology | BLOCKED | Local SQLite/hash-chain implementation is not a centralized production audit service; operational design and recovery evidence are absent |
| Deployment security controls (cookies, CSRF, reverse proxy, session lifecycle) | BLOCKED | Requires deployment-specific review and real-browser verification |

### Decision

**Code-level CI and offline-verifiable S04 regression gates: PASS for this exact head.**  
**Full S04 security/release readiness: BLOCKED.**

The successful CI result does not close any external deployment or repository-administration blocker. PR #5 must remain open and Draft. Do not merge, deploy, enable Auto-Run, activate paid/external providers, or register real-world execution handlers. Payment, purchase, checkout, trading and money movement remain prohibited. Production remains **NOT APPROVED**.

### Next serial checkpoint

P08-P09-BH: continue offline-verifiable S04 review by inspecting the authorization/tenant boundary and trusted UI mutation routes for any untested bypass or stale-session path. Add only a focused regression test when a concrete gap is demonstrated. Keep live OIDC and repository-administration checks listed as external blockers; do not fabricate their completion or advance to S05.


## P08-P09-BH — Trusted UI mutation and tenant-boundary review

Review date: 2026-11-15  
Reviewed code head: `50df9720e800ca37ad23bdfbfc2514efead96a01`

### Review scope

Read-only review of `app.py`, `core/project_actions.py`, `core/identity.py`, `core/approvals.py`, `core/persistent_projects.py`, `core/sqlite_project_store.py`, and the existing UI, identity, project-action, approval, and persistent-project regression tests.

### Findings

- The Streamlit UI's only currently wired mutation is project creation. It requires a separate review event followed by an explicit Confirm-button event; Cancel clears the pending draft. Task-planner text does not issue approvals or dispatch project mutations.
- The confirmation handler constructs the exact two-field payload from the server-side pending draft, issues a short-lived receipt bound to action, canonical payload, tenant and session scope, then dispatches through the server-side gateway. The gateway is not exposed to planner/task text.
- The trusted project handler is registered explicitly by `build_project_gateway`; it rejects payloads with missing or additional keys and derives owner subject/issuer from the trusted Principal closure rather than caller-controlled payload fields.
- Authenticated reads are filtered through `list_projects_for_owner` / `get_for_owner`; persistent registry operations verify both issuer and subject. Existing tests cover same-subject/different-issuer and same-issuer/different-subject denial, unauthenticated access denial, and cross-tenant read/update/delete denial.
- Identity transition and logout cleanup remove pending project data, selected project, approval authority, execution gateway, tenant registry and approval session scope. Existing tests cover account changes, issuer changes, logout and stale receipt rejection.
- No additional authorization bypass or stale-session mutation path was demonstrated in this read-only review. No runtime code change or speculative test was added.

### Residual limitations

- These checks establish only the current in-process Streamlit prototype boundary. They do not prove deployed browser-cookie isolation, CSRF resistance, reverse-proxy/session behavior, multi-worker isolation, or protection from hostile Python executing in the same process.
- Live OIDC verification with two controlled identities remains externally blocked. Repository branch-protection/ruleset enforcement remains unverified because administrative settings are not readable through the current integration.
- Only project creation is wired; the existence of lower-level CRUD methods is not authorization to expose additional mutation handlers.

### Decision

The reviewed UI mutation and tenant ownership paths have automated regression coverage and no new offline-verifiable defect was identified. This is not a production security approval. Keep PR #5 open and Draft; do not merge, deploy, enable Auto-Run, enable real-world handlers, activate paid providers, or permit payment/purchase/trading/money movement. Production remains **NOT APPROVED**.

### Next serial checkpoint

P08-P09-BI: verify the BG documentation commit's exact-head CI, then review the OIDC claim adapter and authentication-required startup/failure branches for mismatches between documented claim validation and actual code. Add focused tests only for a demonstrated gap. Live provider/browser testing remains an external blocker.


## P08-P09-BI — OIDC exact-claim preservation and exact-head CI

Review date: 2026-11-15  
Reviewed code commit: \`26c9138511d96d43ec16ca1421bf73ed5485e2aa\`

### Change and verification

- OIDC issuer claims with leading/trailing whitespace are rejected rather than silently normalized.
- OIDC subject is treated as an opaque, case-sensitive ASCII identifier and preserved exactly; no trimming or case normalization is performed.
- \`core.identity.Principal\` and \`require_authenticated\` validate identity presence without mutating issuer or subject.
- Exact-head PR CI completed successfully:
  - Agent Foundation CI run \`43696373596\` — PASS; 381 tests passed, compile passed, dependency audit reported no known vulnerabilities.
  - Python Demo CI run \`43696373598\` — PASS; 381 tests passed and the demo emitted exactly \`Hello TradeLab Pro\`.

### Decision

The exact-claim preservation change passed both required workflows. This does not establish live OIDC provider or browser-session security; those remain external release blockers.

## P08-P09-BJ — Authentication startup and failure-path review

Review date: 2026-11-15  
Reviewed files: \`app.py\`, \`core/streamlit_auth.py\`, \`core/identity.py\`, \`core/session_security.py\`, \`tests/test_app_smoke.py\`, \`tests/test_streamlit_auth.py\`, and \`tests/test_session_security.py\`.

### Findings

- When authentication is required but OIDC configuration is absent, startup displays a configuration error and stops before rendering authenticated controls. AppTest covers this fail-closed branch.
- When the user is not logged in, the app clears identity-bound state, presents the login action, and stops. Existing AppTest verifies stale drafts, approval authority, gateway, tenant registry and user-specific state are cleared.
- Invalid or expired OIDC claims clear the same identity-bound state and stop before authenticated controls. Adapter tests cover malformed claims, expiry, future issue time, issuer URL ambiguity, subject bounds and clock-skew boundaries.
- Durable security/project storage initialization errors clear identity-bound state and stop before authenticated project/task controls. Existing AppTests cover weak signing material, unsafe database paths, project-store initialization failure, and safe retry with fresh capabilities.
- A concrete session identity-key ambiguity was found: the old delimiter-concatenated issuer/subject marker could collide when a literal delimiter sequence occurred in an accepted issuer path and subject. This could make two distinct identity pairs compare equal for session-state invalidation.
- Corrected this by introducing \`session_identity_key\`, which encodes the issuer and subject as a compact JSON array, and using that structured key in \`app.py\`. Added regression tests proving delimiter-like values produce distinct keys and empty identity components are rejected.

### Exact-head verification of the correction

Reviewed code head: \`d3a1d468c1c70a553c4949b45488cd0baf003a74\`

| Workflow | Run | Result | Evidence |
|---|---:|---|---|
| Agent Foundation CI | \`43696620709\` | PASS | 383 tests passed; compile passed; dependency audit reported no known vulnerabilities |
| Python Demo CI | \`43696620722\` | PASS | 383 tests passed; demo output exactly \`Hello TradeLab Pro\` |

The successful runs above are PR-triggered runs on the exact reviewed head. Superseded push-triggered runs were cancelled by the configured concurrency policy and are not counted as failures.

### Residual limitations

- These tests validate application-level state handling, not real OIDC provider behavior, browser cookie isolation, CSRF, reverse-proxy behavior or multi-worker session isolation.
- The login/logout interaction still requires a real-browser test against a configured non-production OIDC client.
- Branch protection/ruleset enforcement remains unverified because repository administration settings are not available through the current integration.

### Decision

The offline-verifiable authentication startup/failure paths and collision-safe session identity key pass their automated checks at the reviewed code head. Full S04 release readiness remains BLOCKED by the external deployment and repository-administration requirements already listed above. PR #5 remains open and Draft. Do not merge, deploy, enable Auto-Run, activate paid/external providers, or register real-world execution handlers. Payment, purchase, checkout, trading and money movement remain prohibited. Production remains **NOT APPROVED**.

### Next serial checkpoint

P08-P09-BK: continue the offline review of logout callback behavior, login callback/session renewal and identity-bound capability invalidation after re-authentication. Add tests only for demonstrated gaps; keep live browser/OIDC verification as an explicit external blocker.


## P08-P09-BK — Explicit logout callback and re-authentication boundary

Review date: 2026-11-15  
Reviewed code head: \`c66be606644f7ce703fb8cae98f4736f77674b24\`

### Findings

- The explicit Log out callback calls \`clear_session_identity\` before invoking Streamlit's \`st.logout()\`. The identity-bound state is therefore cleared before the provider logout transition is requested.
- When the next rerun observes \`st.user.is_logged_in == False\`, the authentication-required branch clears identity-bound state again, renders only the login path and stops before private project/task controls.
- Re-authentication with a different identity is bound through the structured issuer/subject key. \`bind_session_identity\` clears identity-bound capabilities whenever the marker changes; existing session-security tests cover identity switching and stale approval invalidation.
- Added an AppTest integration regression test that starts an authenticated session with durable stores, invokes the actual Log out button, simulates provider logout, and asserts that approval authority, execution gateway, tenant registry, drafts and private task state do not survive.
- The login button delegates to Streamlit's OIDC login callback. Its actual redirect/provider round trip cannot be established by AppTest and remains part of the live browser/OIDC test matrix.

### Exact-head CI verification

Reviewed code head: \`c66be606644f7ce703fb8cae98f4736f77674b24\`

| Workflow | Run | Result | Evidence |
|---|---:|---|---|
| Agent Foundation CI | \`43696768949\` | PASS | 384 tests passed; compile passed; dependency audit reported no known vulnerabilities |
| Python Demo CI | \`43696768938\` | PASS | 384 tests passed; demo output exactly \`Hello TradeLab Pro\` |

Both results are PR-triggered runs on the exact reviewed head. Superseded push-triggered runs were cancelled by the configured concurrency policy and are not treated as failures.

### Decision

The explicit logout cleanup callback and the identity transition invalidation path pass automated tests at this exact head. Live OIDC redirects, browser cookie/session behavior, CSRF, reverse proxy and multi-worker isolation remain externally blocked. Full S04 security/release readiness remains BLOCKED. PR #5 stays open and Draft; do not merge, deploy, enable Auto-Run, activate paid/external providers, or register real-world execution handlers. Payment, purchase, checkout, trading and money movement remain prohibited. Production remains **NOT APPROVED**.

### Next serial checkpoint

P08-P09-BL: inspect whether all session-state keys that carry user-specific or approval-related information are included in the central identity cleanup list, including any future UI state introduced by later modules. Check for stale references outside the current list and add a focused regression test only if a concrete omission is found.


## P08-P09-BL — Complete inventory of app session-state cleanup keys

Review date: 2026-11-15  
Reviewed code head: \`d72238a2483ed19a049337e456406370c9d2355d\`

### Review result

- Enumerated all literal \`st.session_state[...] \`, \`st.session_state.get(...)\` and \`st.session_state.pop(...)\` keys referenced by \`app.py\`.
- The app currently references 11 keys: \`approval_authority\`, \`approval_authority_config_id\`, \`approval_session_scope\`, \`draft_task\`, \`execution_gateway\`, \`execution_gateway_owner\`, \`free_plan\`, \`pending_project\`, \`project_registry\`, \`project_registry_tenant\`, and \`selected_project_id\`.
- All 11 are present in the central \`_IDENTITY_BOUND_KEYS\` cleanup tuple in \`core/session_security.py\`.
- The \`active_identity_subject\` marker is removed separately by \`clear_session_identity\`; it is not omitted from cleanup.
- No additional literal app session-state key was found outside the cleanup inventory.
- Added an AST-based regression test that derives literal session-state keys from \`app.py\` and asserts every key is covered by the central cleanup tuple or the separately-cleared identity marker. This will detect future UI state additions that are not added to identity cleanup.

### Exact-head CI verification

Reviewed code head: \`d72238a2483ed19a049337e456406370c9d2355d\`

| Workflow | Run | Result | Evidence |
|---|---:|---|---|
| Agent Foundation CI | \`43696885991\` | PASS | 385 tests passed; compile passed; dependency audit reported no known vulnerabilities |
| Python Demo CI | \`43696885984\` | PASS | 385 tests passed; demo output exactly \`Hello TradeLab Pro\` |

Both runs are PR-triggered checks on the exact reviewed head.

### Decision

All current literal Streamlit session-state keys are covered by identity cleanup, and the regression guard passes. No further runtime change was justified by this inventory review. This remains offline code/test evidence only; it does not prove live browser or multi-worker isolation. Full S04 release readiness remains BLOCKED. PR #5 remains open and Draft; do not merge, deploy, enable Auto-Run, activate paid/external providers, or register real-world execution handlers. Payment, purchase, checkout, trading and money movement remain prohibited. Production remains **NOT APPROVED**.

### Next serial checkpoint

P08-P09-BM: continue the offline review of state-bearing callbacks and approval/session capability references outside \`app.py\`. Verify that no callback, controller or storage object caches an identity-bound capability beyond the Streamlit session cleanup lifecycle. Add a focused test only if a concrete stale-reference path is demonstrated.


## P08-P09-BM — State-bearing callback and capability-reference lifecycle

Review date: 2026-11-15  
Reviewed code head: \`6075f38b825ada059cb477be552bb9736c13c1a5\`

### Findings

- \`build_project_gateway\` creates a per-session gateway whose registered project handler closes over the active registry and validated owner identity. The gateway also retains its approval authority, audit backend and session scope.
- In authenticated mode, the persistent project registry retains the active \`TenantKey\` and SQLite store. These objects are stored through the Streamlit session registry/gateway references rather than in a separate global cache.
- The approval authority, execution gateway, gateway owner marker, project registry and registry tenant marker are all in the central identity cleanup tuple. Logout and identity transition remove these references. The local callback functions are recreated during app reruns; no module-level cache or global singleton retaining a Principal, TenantKey, registry, approval authority or gateway was found in the reviewed path.
- The logout callback clears session identity state before calling \`st.logout()\`. Re-authentication binds a new structured identity marker and creates fresh session-scoped capabilities.
- One remaining inconsistent marker was found during this review: \`execution_gateway_owner\` still used the old delimiter-concatenated issuer/subject string even after the main session marker had been made collision-safe. Updated it to reuse the canonical \`session_identity\` value so both identity-bound markers use the same unambiguous representation.
- No additional stale capability reference outside the session cleanup lifecycle was demonstrated. This review does not establish isolation against hostile Python executing in the same process.

### Exact-head CI verification

Reviewed code head: \`6075f38b825ada059cb477be552bb9736c13c1a5\`

| Workflow | Run | Result | Evidence |
|---|---:|---|---|
| Agent Foundation CI | \`43697006038\` | PASS | 385 tests passed; compile passed; dependency audit reported no known vulnerabilities |
| Python Demo CI | \`43697006010\` | PASS | 385 tests passed; demo output exactly \`Hello TradeLab Pro\` |

Both workflows passed on the exact reviewed code head.

### Decision

The reviewed session-scoped capability references are cleared by the identity lifecycle; the gateway owner marker now uses the same collision-safe identity key. Automated verification passed. Full S04 release readiness remains BLOCKED by live OIDC/browser, deployment and repository-administration requirements. PR #5 remains open and Draft. Do not merge, deploy, enable Auto-Run, activate paid/external providers, or register real-world execution handlers. Payment, purchase, checkout, trading and money movement remain prohibited. Production remains **NOT APPROVED**.

### Next serial checkpoint

P08-P09-BN: inspect tenant-bound persistent project and SQLite audit-store lifecycle for retained connections, caches or session-independent references that could survive logout or identity switching. Verify actual object ownership and cleanup behavior; do not add cleanup that would close a shared store still in use by another session.


## P08-P09-BN — SQLite connection and tenant-store reference lifecycle

Review date: 2026-11-15  
Reviewed code head: \`6075f38b825ada059cb477be552bb9736c13c1a5\`

### Findings

- \`SQLiteProjectStore\` and \`SQLiteSecurityStore\` do not retain a long-lived SQLite connection. Each initialization/read/write operation opens a connection inside \`contextlib.closing\`; write paths explicitly commit or roll back before the connection is closed.
- The tenant-bound \`PersistentProjectRegistry\` retains its \`TenantKey\` and \`SQLiteProjectStore\`, but the registry is held in Streamlit session state and is included in the central identity cleanup tuple.
- \`SQLiteExecutionAuditLog\` retains a reference to the security store and a one-way principal fingerprint, not a live database connection or raw issuer/subject. It is retained by the session's execution gateway, which is removed during identity transition/logout.
- SQLite nonce and audit operations open/close their own connections and use transactional write reservations. Existing tests cover tenant-scoped nonce replay, concurrent writes, multi-process audit appends, crash recovery, audit tamper/truncation detection, rollback behavior and owner-only database/sidecar permissions.
- The local JSONL audit logger's module-level path-lock registry retains path-keyed thread locks, not principals, tenants, registries or approval capabilities. The current app configures a fixed local audit path; no per-user-controlled arbitrary path is exposed. This process-local lock registry is not a cross-process coordination mechanism and is not a production audit service.
- No persistent SQLite connection or tenant-bound store reference outside the session-owned registry/gateway lifecycle was found in the reviewed path. No additional cleanup code was justified.

### Verification basis

The reviewed code head \`6075f38b825ada059cb477be552bb9736c13c1a5\` passed both required PR workflows:
- Agent Foundation CI run \`43697006038\` — PASS; 385 tests, compile and dependency audit passed.
- Python Demo CI run \`43697006010\` — PASS; 385 tests and exact demo output passed.

The documentation-only review commit \`ce1973ec2bc1c3f2fed6e23f89b90f1d14ed51e7\` was also verified:
- Agent Foundation CI run \`43697117613\` — PASS; 385 tests, compile and dependency audit passed.
- Python Demo CI run \`43697117662\` — PASS; 385 tests and exact demo output passed.

### Decision

SQLite connections are operation-scoped and closed; tenant-bound registries and audit adapters are reachable only through session-owned objects that are cleared on identity transitions/logout. No offline-verifiable lifecycle defect was found. Production multi-host, external audit anchoring, backup/retention and live browser isolation remain unverified and blocked. PR #5 remains open and Draft; do not merge, deploy, enable Auto-Run, activate paid/external providers, or register real-world execution handlers. Payment, purchase, checkout, trading and money movement remain prohibited. Production remains **NOT APPROVED**.

### Next serial checkpoint

P08-P09-BO: review process-global caches and lock registries for cross-session data retention, unbounded growth and unsafe ownership assumptions. Distinguish harmless process-wide synchronization from identity-bearing state; do not remove shared locks or introduce per-session locks that would weaken concurrent audit append safety.


## P08-P09-BO — Process-global cache and lock-registry review

Review date: 2026-11-15  
Reviewed code head: \`6075f38b825ada059cb477be552bb9736c13c1a5\`

### Process-global objects found

The reviewed core modules define only these mutable/process-global objects relevant to this boundary:

- \`core.audit._PATH_LOCKS\`: a process-local mapping from resolved audit-log path to a shared \`threading.Lock\`. It synchronizes different \`JsonlAuditLog\` instances targeting the same file within one Python process. It does not retain a Principal, TenantKey, approval authority, project registry or task payload.
- \`core.audit._PATH_LOCKS_GUARD\`: the lock protecting updates to the path-lock mapping; it contains no user identity.
- \`core.projects._PROJECT_MUTATION_CAPABILITY\`: a module-level sentinel used to distinguish trusted in-process project mutation calls. It is not tenant-specific and is not a security sandbox against hostile Python in the same process.
- \`core.session_security._IDENTITY_BOUND_KEYS\`: an immutable tuple of session-state key names, not user data or cached capabilities.

No Streamlit cache decorator, module-global Principal, tenant-bound registry, SQLite store, execution gateway or approval authority was found in the reviewed core module set.

### Retention and ownership assessment

- The current app constructs the JSONL audit logger with one fixed configured path (\`.apaa_audit/execution.jsonl\`), so the path-lock map has one production path entry in the current UI flow. If future features allow arbitrary per-user or per-task log paths, the map would need bounded/weak-reference lifecycle handling to avoid retaining one lock per historical path.
- Do not replace the shared per-path lock with per-instance locks: doing so would weaken same-process concurrent append serialization. The lock is intentionally process-wide for the configured file path and is not a cross-process lock.
- The project mutation sentinel remains an in-process trust convention only. Python code running with the same interpreter privileges can import private module objects; production isolation requires a separate process/service boundary and is not claimed here.
- No identity-bearing process-global cache was identified. No change was justified for the current fixed-path prototype.

### Exact-head CI verification

Documentation commit: \`509799b3901d9e25fd539a7ffae507323e0d586c\`

| Workflow | Run | Result | Evidence |
|---|---:|---|---|
| Agent Foundation CI | \`43697232345\` | PASS | 385 tests passed; compile passed; dependency audit reported no known vulnerabilities |
| Python Demo CI | \`43697232231\` | PASS | 385 tests passed; demo output exactly \`Hello TradeLab Pro\` |

Both checks completed successfully for the exact documentation commit, whose code tree includes reviewed code head \`6075f38b825ada059cb477be552bb9736c13c1a5\`.

### Decision

No identity-bearing global cache or store was found. The only shared lock registry is path-scoped and required for same-process append serialization; its current app usage is one fixed path. The module-level mutation sentinel remains explicitly non-isolating. Full S04 release readiness remains BLOCKED by live OIDC/browser, deployment, production isolation and repository-administration requirements. PR #5 remains open and Draft; do not merge, deploy, enable Auto-Run, activate paid/external providers, or register real-world execution handlers. Payment, purchase, checkout, trading and money movement remain prohibited. Production remains **NOT APPROVED**.



## P08-P09-BO addendum — Trusted mutation sentinel and controller exposure review

Review date: 2026-11-15
Reviewed code head: 730a7565b7ec8e32f68d2f7929b1dde50bd16922

### Findings

- core/__init__.py exports no project mutation capability or execution gateway objects.
- The private _PROJECT_MUTATION_CAPABILITY sentinel is defined in core/projects.py and imported only by the trusted project controller and persistent project registry implementation. It is not placed in Streamlit session state or passed to planner/provider code.
- AIBrain, create_plan and the deterministic RuleBasedProvider handle task text as planning input only. They have no reference to the project registry, approval authority, gateway builder or mutation sentinel.
- app.py issues an approval receipt and invokes the project gateway only inside the explicit Confirm-button branch. The task planner branch only calls the built-in planner and records a text plan; it does not dispatch project actions.
- The controller constructs the exact project payload and supplies the private mutation sentinel from trusted server-side code. The owner identity is captured from the validated Principal closure, not task text or payload.
- Existing tests cover no self-approval, task text cannot trigger project creation, exact confirmation, payload validation, replay prevention and session-scope rejection.
- The sentinel is still an in-process convention: any hostile Python code executing with the same interpreter privileges could import the module-private object. This is a known isolation limitation, not a hardened sandbox. No code change was justified.

## P08-P09-BP — Filesystem path anchoring and durable SQLite configuration

Review date: 2026-11-15
Reviewed code head: 730a7565b7ec8e32f68d2f7929b1dde50bd16922

### Findings and remediation

- JsonlAuditLog now anchors its path with Path(path).absolute() at construction. SQLiteProjectStore and SQLiteSecurityStore similarly anchor database paths with Path(database_path).absolute(). Later working-directory changes therefore cannot redirect operations to a different relative path.
- Both SQLite stores now reject the literal :memory: before path normalization. These stores open a fresh connection per operation, so an in-memory database would otherwise disappear when the initialization connection closes and later operations would fail or lose durability.
- Added regression tests for all three path-bearing stores: construct under one working directory, change the process working directory, then verify subsequent operations remain anchored to the original location.
- Added regression tests that both durable SQLite stores reject :memory: configuration.
- Existing checks remain: symlinked parent rejection, owner-only parent/file permissions, regular-file validation, JSONL final-component O_NOFOLLOW, and SQLite sidecar permission tests.
- CI concurrency groups now include github.event_name, so push and pull_request runs on the same branch no longer cancel each other. The workflow-policy regression test checks for this event separation.

### Exact-head CI verification

Reviewed code head: 730a7565b7ec8e32f68d2f7929b1dde50bd16922

| Workflow | PR run | Result | Evidence |
|---|---:|---|---|
| Agent Foundation CI | 43697663733 | PASS | 390 tests passed; compile passed; dependency audit reported no known vulnerabilities |
| Python Demo CI | 43697663665 | PASS | 390 tests passed; demo output exactly Hello TradeLab Pro |

The same exact head also completed push-triggered runs successfully. PR-triggered runs above are used as the primary verification evidence.

### Residual path-security boundary

- Absolute path anchoring removes working-directory drift; it does not eliminate a time-of-check/time-of-use race if a hostile process running as the same OS account renames or replaces a parent directory between validation and a later file open/SQLite connection.
- The standard-library SQLite connection opens by pathname, so the preceding path checks cannot pin the database inode across a same-account rename race.
- JSONL final-component no-follow flags and lexical parent checks reduce symlink redirection, but a same-account attacker may still race parent-directory replacement.
- These risks require a dedicated OS account, non-writable private parent directories, and process/container isolation. Do not claim same-UID hostile-process protection.

### Decision

Relative-path working-directory drift and the :memory: durability misconfiguration are corrected and covered by passing tests. Same-account path-swap/TOCTOU protection remains an explicit production blocker. PR #5 remains open and Draft. Do not merge, deploy, enable Auto-Run, activate paid/external providers, or register real-world execution handlers. Payment, purchase, checkout, trading and money movement remain prohibited. Production remains NOT APPROVED.

### Next serial checkpoint

P08-P09-BQ: inspect SQLite path revalidation, parent-directory rename/symlink races and sidecar handling in detail. Implement only portable mitigations that can be proven with regression tests; retain explicit OS-isolation blockers.



## P08-P09-BR — CI cancellation and SQLite path-replacement follow-up

Review date: 2026-11-15
Verified code head: 3f85425e5adff0411e4e1a7534ff3a979e60a6a0

- CI duplication/cancellation root cause: branch push and pull_request events duplicated feature-branch checks, while branch-scoped concurrency with cancel-in-progress enabled superseded in-flight runs.
- Remediation: feature-branch push triggers removed from the two PR-focused workflows; main push validation retained; concurrency groups now include workflow/event/SHA and set cancel-in-progress false.
- The CI policy test initially failed because it still asserted the old cancel-in-progress=true behavior. The assertion was corrected to enforce the new non-cancelling policy.
- Exact-head PR run 43698205731 (Agent Foundation CI) PASS.
- Exact-head PR run 43698205658 (Python Demo CI) PASS.
- Both workflows completed dependency audit/compile/tests and demo execution as applicable.
- A new parameterized test verifies both SQLite stores reject a parent directory that is renamed and replaced with a symlink after store initialization.

### Boundary and status

The test covers a deterministic path replacement before a subsequent connection. It does not prove protection against a same-UID attacker racing the path check and pathname-based sqlite3 open. The residual TOCTOU limitation remains explicit and requires OS-level isolation.

PR #5 remains Open and Draft. No merge/deploy, Auto-Run, paid provider, payment/purchase/checkout/trading/money-movement capability, or real-world action handler is enabled. Production remains NOT APPROVED.

### Next checkpoint

P08-P09-BS: inspect JSONL audit path handling and SQLite journal/WAL sidecar lifecycle, permissions, cleanup and tamper-detection limits.


## P08-P09-BU — JSONL crash-tail test and runtime mode boundary

Review date: 2026-11-15  
Reviewed code head: `74930fbcc505d87c42263db8712118e1635a86e2`

- Added `test_jsonl_audit_log_fails_closed_on_truncated_trailing_record`. It simulates a process-crash-style partial final JSONL record, verifies the chain rejects it, and verifies append remains blocked. There is deliberately no silent truncation/repair path.
- Exact-head Agent Foundation CI `43699703242` and Python Demo CI `43699703273` both passed; all job steps completed successfully.
- Reviewed `app.py` audit selection: authenticated OIDC mode uses `SQLiteExecutionAuditLog`; unauthenticated local-prototype mode uses `JsonlAuditLog` and visibly warns that authentication is not enforced and the instance must not be publicly exposed.
- JSONL uses process-local thread locks, not cross-process locks. Its use must remain restricted to one local prototype process. It is not a production multi-process audit backend.
- Authenticated SQLite audit durability, multi-process/multi-host topology, backup, retention, external anchoring and recovery still require separate verification. No claim of production readiness is made.

Decision: latest exact-head code-level CI PASS; full S04 remains BLOCKED. PR #5 remains Open + Draft, and Production remains NOT APPROVED.

Next checkpoint: P08-P09-BV — inspect authenticated SQLite audit transaction and recovery semantics, and add targeted tests only for demonstrated gaps.


## P08-P09-BW — SQLite audit backup/restore, tamper fail-closed and remaining operational gates

Review date: 2026-11-15
Test change: `tests/test_sqlite_security_store.py` commit `b2ef2fa1b4456b763c4e4bf7c5b448f4148011e9`

### Work package 1 — SQLite backup and restore verification

Added an automated test using SQLite's online backup API:
- Writes two committed audit events to the source database.
- Uses `Connection.backup()` to create a consistent backup and verifies `PRAGMA integrity_check = ok`.
- Restores that backup into a fresh database and repeats the integrity check.
- Opens the restored database through `SQLiteSecurityStore`, verifies the audit hash chain and confirms its last hash matches the source.
- Appends a new event after restore and verifies the extended chain and exact event order.

This proves the tested local SQLite backup/restore path preserves a valid audit chain. It does not prove scheduled backups, encrypted/off-site storage, retention, disaster recovery objectives, or protection from an attacker who can rewrite both database and backup.

### Work package 2 — tamper fail-closed and append atomicity

Added a test that modifies an existing audit event directly, attempts to append a new event, and asserts:
- append raises a verification error;
- no additional event is inserted;
- chain verification remains failed.

The implementation already verifies the complete chain inside the same `BEGIN IMMEDIATE` write transaction before appending. This regression test now asserts that tampering cannot be silently extended into a new apparently valid chain.

### Work package 3 — independent anchor and live/deployment verification runbook

The application currently has no independent external audit anchor. A hash chain stored only in the same SQLite database is not an independent trust source. Do not describe it as tamper-proof.

Before production consideration, an operator-controlled independent anchor must:
1. Receive the monotonically increasing audit sequence and latest chain hash from a separately administered trust boundary.
2. Store immutable or append-only checkpoints with authenticated transport and restricted write identities.
3. Reject sequence rollback, duplicate conflicting checkpoints and unexpected hash discontinuity.
4. Support periodic verification against a restored database and alert on mismatch or missed checkpoint.
5. Keep credentials outside this repository and outside application task-controlled configuration.
6. Be tested with database rollback, backup rollback, anchor outage and credential-revocation scenarios.

No external service, credentials, paid provider or network integration is enabled by this change.

#### Live OIDC and browser acceptance procedure

Run only in a private, non-production test deployment:
- Configure an OIDC test client and protected signing secret using the deployment's secret manager; never commit secrets.
- Create two controlled test identities and separate browser profiles.
- Verify unauthenticated access is denied; login binds the correct issuer/subject; logout clears identity-bound state; switching identities does not retain drafts, approvals, project data or capabilities.
- Exercise invalid issuer, subject, audience, expiry, nonce/state, callback error and redirect mismatch cases.
- Verify secure cookie attributes, CSRF defenses, exact redirect allowlist, TLS termination and reverse-proxy header trust.
- Capture sanitized evidence (test IDs, timestamps, outcomes); do not store tokens, cookies, secrets or personal data in artifacts.
- Stop on any cross-user visibility, retained session capability or unexpected redirect.

#### Host isolation and production deployment acceptance procedure

- Run under a dedicated unprivileged OS identity with a private owner-only data directory and non-writable parent.
- Ensure only one explicitly supported audit writer topology; do not share local SQLite/JSONL files across hosts or network filesystems without a separately tested design.
- Keep application, secrets and audit storage permissions separate; disable shell/device/network/browser handlers by default.
- Use an OS/container boundary with resource limits and deny-by-default filesystem, network and process capabilities before considering hostile-code execution.
- Verify backups are encrypted, access-controlled, independently retained and periodically restore-tested.
- Configure monitoring for audit verification failures, backup age, storage exhaustion, auth failures and policy denials.
- Verify repository branch protection and required status checks with repository-admin access; this integration cannot establish administrative enforcement.
- Keep production approval blocked until each item has named owner, evidence and independent review.

### Disposition

The new local backup/restore and tamper-append regression tests are committed; their CI result is pending until GitHub Actions completes on the resulting head. Independent anchoring, live OIDC/browser testing, repository administration and host isolation are operational/deployment tasks and cannot honestly be marked complete from this repository-only session.

PR #5 remains Open + Draft. No merge, deployment, Auto-Run, paid provider, payment, purchase, checkout, trading, money movement or real-world execution handler is enabled. Production remains NOT APPROVED.

Next checkpoint: P08-P09-BX — verify exact-head CI for the new backup/restore and tamper tests, fix any failures, then update the consolidated matrix with exact evidence.


## P08-P09-BX — Exact-head CI verification for SQLite audit backup/restore and tamper tests

Verification date: 2026-11-15  
Reviewed code commit: `b2ef2fa1b4456b763c4e4bf7c5b448f4148011e9`

### Exact-head CI evidence

| Workflow | Run ID | Result |
|---|---:|---|
| Python Demo CI | 43700165143 | PASS |
| Agent Foundation CI | 43700165203 | PASS |

Both runs completed successfully on the reviewed commit. The Python Demo job completed the test suite and demo execution. The Agent Foundation job completed dependency audit, module compilation and foundation tests.

### Verification outcome

- SQLite online backup and restore preserves the tested audit chain and allows a subsequent append.
- SQLite audit tampering causes append to fail closed without adding a new event.
- The two new regression tests are included in the verified CI run.
- No application runtime code was changed in this verification-only checkpoint.
- This is local SQLite test evidence only; it does not establish independent audit anchoring, encrypted/off-site backup, scheduled recovery, multi-host safety or production readiness.

### Decision

P08-P09-BX automated CI verification: PASS for the exact reviewed code commit. The broader S04 release-readiness matrix remains BLOCKED by live OIDC/browser verification, repository branch-protection administration, host/process isolation, independent audit anchoring and deployment-specific controls. PR #5 remains open and Draft. Do not merge, deploy, enable Auto-Run, activate paid/external providers, or register real-world execution handlers. Payment, purchase, checkout, trading and money movement remain prohibited. Production remains NOT APPROVED.

### Next serial checkpoint

P08-P09-BY: inspect authenticated SQLite audit-store initialization and fail-closed recovery behavior for any remaining offline-verifiable gap. Keep the review focused; add tests only for a demonstrated defect. Live OIDC/browser and production operational gates remain external blockers.
