# APAA S09-C01 — Owner Approval Consumption in BrowserExecutionCoordinator

Status: implementation and trusted UI-to-coordinator bridge added; exact-head APAA Security CI and independent review pending. Live browser dispatch remains NO-GO.

## Implemented boundary

- `BrowserExecutionCoordinator.execute(..., approval_receipt=...)` now fails closed unless the trusted Owner approval configuration is present.
- Configuration binds an authenticated `Principal` to the exact `TenantKey`; mismatched identity is rejected at construction and rechecked for each execution.
- A durable `ApprovalAuthority` nonce store is mandatory. `ApprovalAuthority.durable_nonce_store` exposes whether replay protection survives process restart.
- A durable `SQLiteBrowserRecoveryLedger` is mandatory whenever Owner approval is configured.
- Each execution rechecks the Owner session before receipt consumption and again immediately before the worker adapter is invoked. The validator must return literal `True`.
- Approval is consumed for action `browser_read`, bound to the exact canonical validated `BrowserJob` payload, tenant and current session scope. Consumption happens before DNS resolution or browser-side work.
- After the durable job claim, the ledger stores one-way SHA-256 references for the approval receipt, Owner and session, together with the request digest. Raw receipts, Owner IDs and session tokens are not persisted in the correlation record.
- If the correlation write fails after claim, the job is transitioned to failed and the ledger's dispatch-block latch is set. Worker execution does not start.
- `core/browser_control.py` provides the trusted UI boundary: `request_approval` issues the receipt only after explicit Owner confirmation; `dispatch_with_approved_coordinator` verifies that the coordinator shares the exact same durable authority, Owner Principal, tenant, session scope and session-check callback before passing the receipt to `BrowserExecutionCoordinator.execute`.
- The legacy `BrowserControlBoundary.dispatch` path remains explicitly disabled through its guarded ExecutionGateway handler. `BROWSER_HANDLER_ENABLED` remains false.
- `browser_read` is now an exact registered read-only action in `core/safety.py`; it does not enable Auto-Run or any mutation.
- The attested-runtime factory now requires the complete Owner approval boundary in its eventual construction path, but remains hard-disabled by release gates.

## Tests added

- Direct production coordinator execution without the Owner approval boundary is denied.
- Exact job-bound one-time approval succeeds and persists hashed correlation.
- Receipt replay is rejected before worker execution.
- Payload mismatch is rejected before DNS resolution.
- Inactive session is rejected before approval consumption.
- Session expiry during DNS is caught again before worker start.
- Owner principal / tenant mismatch is rejected.
- Trusted UI approval bridge verifies exact shared context and rejects a different coordinator, inactive session, missing explicit confirmation or non-durable nonce store.
- Test harness uses a durable SQLite nonce store and private temporary ledger directory.

## Remaining release gates — do not bypass

The attested-runtime factory intentionally remains hard-disabled. This work does not qualify or enable live browsing. Remaining gates:
1. Real-host Chromium FD ownership issue: still reproduces in disposable OCI qualification; exact offending FD/operation is not yet known.
2. The P74 diagnostic source patch is not compiled into the Debian Chromium runtime binary; a matching instrumented binary or exact build symbols are still needed.
3. Android physical-device qualification remains outstanding.
4. Independent security review and Owner release acceptance remain outstanding.

No live browser, worker dispatch, Auto-Run, payment, purchase, public access, deployment, default-branch change or PR merge is authorized by this change.

## Latest PR / CI state

- Draft PR #25: https://github.com/glad4u7-crypto/TLP-Write-Test/pull/25
- Current code includes the UI bridge in `core/browser_control.py`, exact context matching in `BrowserExecutionCoordinator.matches_approval_context`, and integration tests in `tests/test_browser_control_coordinator.py`.
- An earlier run exposed that `browser_read` was not registered as a read-only action; this is corrected in `core/safety.py` and covered by `tests/test_safety.py`.
- Exact-head CI for the latest bridge/test changes is pending. Do not mark this integration verified until the latest PR-head run succeeds.
