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
