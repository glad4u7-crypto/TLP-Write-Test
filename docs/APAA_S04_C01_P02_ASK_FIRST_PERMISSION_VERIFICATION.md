# APAA-S04-C01-P02 — Ask First Permission Verification

Checkpoint ID: `APAA-S04-C01-P02`
Status: **IN PROGRESS — repository review recorded; exact-head CI and live boundary evidence pending**
Project baseline: APAA Master Roadmap v1.0
Repository: `glad4u7-crypto/TLP-Write-Test`
Working branch: `feature/apaa-s09-c01-p16-oci-lifecycle`
Pull request: #11 (Draft / Open / Unmerged)

## 1. Scope

Verify the existing permission model and Ask First approval path without enabling any real-world handler, browser/worker, Auto-Run, paid provider, payment, purchase, checkout or financial operation.

This is a repository-level review of the current code and tests. It is not a production security certification, live identity test, deployed multi-user test, or approval to activate execution.

## 2. Code reviewed

- `core/safety.py`: exact read-only action allowlist; exact reviewed mutation allowlist; prohibited financial/provider token and phrase rejection; unknown actions denied; mutation approval must match the exact canonical action; Auto-Run requires a separately configured exact allowlist.
- `core/approvals.py`: short-lived HMAC receipt bound to canonical action, canonical payload digest, expiry, nonce, tenant and session scope; malformed/tampered receipts fail closed; nonce consumption is one-time; durable mode requires a tenant.
- `core/execution.py`: handlers must be explicitly registered; unknown/prohibited handlers cannot be registered; policy/approval is checked before dispatch; audit intent must persist before handler execution; no handler is registered by default.
- `core/identity.py` and `core/streamlit_auth.py`: identity primitives and Streamlit OIDC claim adapter. These do not independently prove a live identity-provider deployment or browser-session security.
- `core/streamlit_approval.py` and `app.py`: UI approval wiring must remain subject to the same exact-action and payload-bound receipt contract. The current UI test suite is not a substitute for real-browser E2E.

## 3. Existing automated evidence inspected

| Control | Existing test evidence | Review result |
|---|---|---|
| Read-only allowlist is explicit | `tests/test_safety.py` | Covered |
| Unknown actions fail closed | `tests/test_safety.py`, `tests/test_approvals.py` | Covered |
| Mutations require exact action approval | `tests/test_safety.py` | Covered |
| Payment, purchase, checkout, financial and provider actions remain blocked | `tests/test_safety.py` | Covered |
| Auto-Run defaults to denied and cannot override blocked actions | `tests/test_safety.py`, `tests/test_execution.py` | Covered |
| Approval receipt binds exact action and payload | `tests/test_approvals.py`, `tests/test_execution.py` | Covered |
| Receipt expiry, tampering and replay are rejected | `tests/test_approvals.py` | Covered |
| Durable nonce replay is rejected across authority restart | `tests/test_approvals.py` | Covered |
| Session and tenant scope are bound to receipt | `tests/test_approvals.py` | Covered |
| No handler is active by default | `tests/test_execution.py` | Covered |
| Audit intent precedes side effect and fails closed | `tests/test_execution.py` | Covered |
| UI review/cancel does not dispatch action | `tests/test_streamlit_approval.py` | Covered by AppTest only |
| Cross-session UI receipt rejection | `tests/test_streamlit_approval.py` | Covered by AppTest only |

## 4. Security findings and limits

1. **IN-PROCESS TRUST LIMIT:** `ApprovalAuthority` and `ExecutionGateway` are Python-process capabilities. They do not isolate a compromised or arbitrary-code-capable process. Keep them private to trusted application/controller code; never expose them to model output, planner text or task payloads.
2. **LIVE AUTHENTICATION NOT PROVEN:** OIDC claim parsing and Principal validation are code-level primitives. Real provider configuration, two-user browser isolation, secure cookie/session behavior, CSRF, callback/state/nonce handling and logout/session-fixation tests require a private non-production deployment.
3. **AUDIT DURABILITY LIMIT:** local SQLite/JSONL and in-process tests do not establish independently administered immutable audit anchoring or multi-host writer safety.
4. **POST-SIDE-EFFECT AUDIT FAILURE:** if the external handler succeeds but completion audit persistence fails, the side effect may already have occurred. The gateway reports manual review; action-specific idempotency/reconciliation is still required before irreversible real-world handlers.
5. **NO REAL-WORLD HANDLERS APPROVED:** repository tests do not authorize shell, arbitrary browser/network, email, device control, financial or other external actions.

## 5. Required verification before this Part can be marked complete

- Run the exact-head required CI workflows after this review record is committed.
- Inspect the exact-head job results; do not reuse results from earlier commits.
- Perform a safe, local practice exercise with a denied mutation, a mismatched approval, and a blocked payment/provider action; verify that no handler is called.
- When a private test deployment and controlled identities exist, run two-profile browser E2E for login/logout, identity switching, cross-user resource access, approval replay and stale-session behavior.
- Obtain independent review for any production boundary. Do not infer production readiness from CI.

## 6. Hands-on practice — APAA-PRACTICE-S04-P02

Use only the existing test suite / disposable test data:

1. Attempt `write_file` without approval. Expected: denied; handler call count remains zero.
2. Supply approval for `write_file`, then request `delete_file`. Expected: denied; handler call count remains zero.
3. Attempt `place_order` or `paid_api_call`, even with a matching approval or Auto-Run allowlist. Expected: denied.
4. Replay a successfully consumed approval receipt. Expected: denied.
5. Make the audit-intent append fail. Expected: handler is not called.

Do not use real accounts, real files, real browser sessions or external services for this exercise.

## 7. Checkpoint record

- Checkpoint ID: `APAA-S04-C01-P02`
- Part name: Ask First Approval System — Permission Verification
- Completed work: repository code review; existing test-to-control mapping; security limitations and hands-on practice documented.
- Remaining work: exact-head CI; safe practice execution; real-browser/two-user evidence when a private test deployment exists; independent security review.
- Test results: existing test cases inspected; **this checkpoint's exact-head CI is pending**.
- GitHub reference: PR #11, branch `feature/apaa-s09-c01-p16-oci-lifecycle`.
- Next checkpoint: `APAA-S04-C01-P03` — Read-only and Modification Permissions verification, only after P02 acceptance criteria are met.

## 8. Safety and release state

Ask First remains the intended default. Auto-Run remains OFF. No payment, purchase, checkout, financial transaction or paid provider is permitted. No real-world handler, browser/worker activation, host mutation, deployment or PR merge is authorized. PR #11 remains Draft / Open / Unmerged.
