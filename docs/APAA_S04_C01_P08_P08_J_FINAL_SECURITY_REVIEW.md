# APAA-S04-C01-P08-P08-J — CI Verification & Final Security Review

Review date: 2026-11-15
Repository: `glad4u7-crypto/TLP-Write-Test`
Review branch: `feature/approval-ui-e2e-p06`
Reviewed code snapshot: `84214318fe255d47df5638fbf27bb5f656c8a771`
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

The latest PR head at review time was `84214318fe255d47df5638fbf27bb5f656c8a771`. Earlier failed runs exist in the history, but later corrected commits have successful runs. They are not current-head failures.

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

### MEDIUM — CI workflow least privilege / PR coverage
The Agent Foundation workflow previously relied on repository-default token permissions and only ran PR events targeting `main`, while PR #5 targets `feature/agent-v0.3-zero-cost-core`. This checkpoint updates the workflow to explicit `contents: read` permission and includes that PR base branch. The updated workflow must itself pass CI on the new commit before this correction is considered verified.

## 4. Release decision

**NOT APPROVED for production, public deployment, or real-world execution.**

The code snapshot has passing automated CI and useful prototype security controls. The outstanding live-authentication and production-boundary findings remain release blockers. Keep PR #5 in draft. Do not merge or enable real-world handlers based on CI success alone.

## 5. Next checkpoint

1. Verify current-head Python Demo CI and Agent Foundation CI after the workflow permission/PR-trigger correction and this report are committed.
2. Complete P08-P06 live OIDC/browser matrix with two identities.
3. Review deployment configuration and durable storage operations.
4. Reassess production approval only after the blockers are closed and independently verified.

Safety policy remains unchanged: no payments or purchases; no paid API/provider activation or charges; no automatic execution by default.
