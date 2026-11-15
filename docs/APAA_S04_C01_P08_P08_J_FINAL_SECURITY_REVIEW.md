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
