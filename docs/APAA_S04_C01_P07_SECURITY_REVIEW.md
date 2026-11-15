# APAA-S04-C01-P07 — Live Approval Gateway Security Review

Review date: 2026-11-15
Review scope: current prototype on `feature/approval-ui-e2e-p06`
Status: **Prototype security review; not production approval**

## Executive result

The current approval path has useful fail-closed controls for the tested in-process project-creation workflow. It is **not** a production-grade multi-user execution boundary. No real-world execution handlers are approved by this review.

## Verified controls

| Control | Evidence in repository | Assessment |
|---|---|---|
| Explicit UI confirmation before project creation | `tests/test_streamlit_approval.py` | Covered by Streamlit AppTest |
| Review and cancel do not create a project | `tests/test_streamlit_approval.py` | Covered |
| Approval receipt binds exact action and payload | `tests/test_approvals.py`, `tests/test_execution.py` | Covered |
| Receipt is short-lived, signed, and single-use | `core/approvals.py`, approval tests | Covered in-process |
| Receipt issued by one authority is rejected by another | `tests/test_approvals.py` | Covered |
| Cross-session receipt is rejected by second session gateway | `tests/test_streamlit_approval.py` | Covered by AppTest session objects |
| Task planner text cannot create a project or issue UI approval | `tests/test_streamlit_approval.py` | Covered |
| Audit intent must persist before handler runs | `tests/test_execution.py` | Fail-closed test exists |
| Completion audit failure is surfaced after side effect | `tests/test_execution.py` | Manual-review outcome tested |
| Multiple log objects in one process serialize concurrent appends | `tests/test_audit.py` | Thread-level test added |
| Tampering, truncation/reordering, symlink target and file mode checks | `tests/test_audit.py` | Covered by local tests |

## Findings and residual risks

### P0 — No production identity/authentication boundary

Streamlit session-state separation is not user authentication or authorization. The current AppTest checks object separation, not authenticated users, browser cookie/session theft, CSRF, or authorization across a deployed multi-user server.

**Required before deployment:** implement and independently test authenticated identity, per-user authorization, secure session lifecycle, CSRF protections where applicable, and server-side ownership checks for every object.

### P1 — ApprovalAuthority is an in-process capability

Anyone able to execute arbitrary Python inside the app process can potentially reach or misuse trusted objects. HMAC receipts protect integrity, but do not isolate untrusted code from the Python process.

**Required before real handlers:** isolate the approval issuer and execution broker behind a narrow trusted service boundary; do not pass authority objects to model/task code.

### P1 — Audit lock is process-local

The shared lock protects multiple log instances/threads in one Python process only. It does not serialize writes across processes, containers, or hosts.

**Required before multi-worker deployment:** use a transactional/centralized append-only audit store or a proven inter-process locking design, with access control and recovery procedures.

### P1 — Local hash chain is not tamper-proof

A privileged attacker who can rewrite the file can recompute the SHA-256 chain. The chain detects ordinary corruption and edits, not a fully privileged rewrite.

**Required before production:** protected remote storage, independently protected checkpoints/signatures, access controls, monitoring, retention and recovery policy.

### P1 — Audit completion can fail after a side effect

If intent persistence succeeds, the handler executes, and completion persistence fails, the side effect may already have happened. The gateway reports manual review, but cannot roll back an arbitrary external effect.

**Required before irreversible actions:** idempotency keys, durable transactional outbox or equivalent reconciliation, and action-specific compensation/recovery.

### P2 — No multi-process or live-browser E2E verification

AppTest does not prove isolation under a real deployed Streamlit server, reverse proxy, multiple workers, or concurrent browser clients.

**Required before production:** run a staging deployment with two separately authenticated browser users and test session fixation, cross-user access, stale/replayed approvals, concurrent mutation, and server restart.

## Execution restrictions retained

- No payment, purchase, checkout, trading, or money movement.
- No paid/external provider activation; no API keys or charges.
- Auto-Run remains disabled in the app's default configuration.
- No shell, browser, arbitrary network, email, file-system, or device handlers are registered.
- Do not merge this draft PR or enable real-world handlers based solely on this review.

## Release decision

**NOT APPROVED for production or real-world execution.** Continue only with isolated, reversible, local prototype tests until the P0/P1 findings are closed and reviewed.
