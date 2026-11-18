# APAA S09-C01 — Owner Approval Consumption in BrowserExecutionCoordinator

Status: implementation added; exact-head APAA Security CI and independent review pending. Live browser dispatch remains NO-GO.

## Implemented boundary

- `BrowserExecutionCoordinator.execute(..., approval_receipt=...)` now fails closed unless the trusted Owner approval configuration is present.
- Configuration binds an authenticated `Principal` to the exact `TenantKey`; mismatched identity is rejected at construction and rechecked for each execution.
- A durable `ApprovalAuthority` nonce store is mandatory. `ApprovalAuthority.durable_nonce_store` exposes whether replay protection survives process restart.
- A durable `SQLiteBrowserRecoveryLedger` is mandatory whenever Owner approval is configured.
- Each execution rechecks the Owner session before receipt consumption and again immediately before the worker adapter is invoked. The validator must return literal `True`.
- Approval is consumed for action `browser_read`, bound to the exact canonical validated `BrowserJob` payload, tenant and current session scope. Consumption happens before DNS resolution or browser-side work.
- After the durable job claim, the ledger stores one-way SHA-256 references for the approval receipt, Owner and session, together with the request digest. Raw receipts, Owner IDs and session tokens are not persisted in the correlation record.
- If the correlation write fails after claim, the job is transitioned to failed and the ledger's dispatch-block latch is set. Worker execution does not start.
- The attested-runtime factory now requires the complete Owner approval boundary in its eventual construction path.

## Tests added

- Direct production coordinator execution without the Owner approval boundary is denied.
- Exact job-bound one-time approval succeeds and persists hashed correlation.
- Receipt replay is rejected before worker execution.
- Payload mismatch is rejected before DNS resolution.
- Inactive session is rejected before approval consumption.
- Session expiry during DNS is caught again before worker start.
- Owner principal / tenant mismatch is rejected.
- Test harness uses a durable SQLite nonce store and private temporary ledger directory.

## Remaining release gates — do not bypass

The attested-runtime factory intentionally remains hard-disabled. This work does not qualify or enable live browsing. Remaining gates:
1. Real-host Chromium FD ownership issue: still reproduces in disposable OCI qualification; exact offending FD/operation is not yet known.
2. The P74 diagnostic source patch is not compiled into the Debian Chromium runtime binary; a matching instrumented binary or exact build symbols are still needed.
3. Android physical-device qualification remains outstanding.
4. Independent security review and Owner release acceptance remain outstanding.

No live browser, worker dispatch, Auto-Run, payment, purchase, public access, deployment, default-branch change or PR merge is authorized by this change.