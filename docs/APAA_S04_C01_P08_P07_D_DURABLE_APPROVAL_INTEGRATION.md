# APAA-S04-C01-P08-P07-D — Durable Approval Integration (Phase 1)

Status: **ApprovalAuthority and gateway tenant plumbing added; application wiring and durable audit adapter remain pending**

## Changes
- `ApprovalAuthority` accepts an optional `nonce_store` and an externally managed signing secret.
- Durable mode requires a validated `TenantKey` at both issue and consume.
- Approval HMAC now binds action, payload digest, expiry, nonce, issuer, and subject.
- Nonce consumption is delegated to `SQLiteSecurityStore.consume_approval_nonce`; backend errors fail closed.
- `ExecutionGateway.execute` accepts a tenant context and passes it to approval verification.
- Added tests for durable replay denial across authority reconstruction, missing tenant fail-closed behavior, and tenant-scoped consumption.

## Critical security requirements
- Production signing secret must be generated and supplied by the operator through a protected runtime secret mechanism; never commit it or expose it in logs/UI.
- Use the same protected signing secret across app restarts/workers if outstanding receipts must remain verifiable. If secret rotation occurs, old receipts should fail closed.
- The tenant must be built from the validated server-side OIDC Principal, never from task text, query parameters, or client-supplied owner fields.
- Durable receipts are cryptographically bound to issuer + subject to prevent cross-tenant transfer.
- Keep receipt lifetime short and confirmation explicit.

## Not yet integrated
- Streamlit UI/controller does not yet construct the durable store, load a protected signing secret, or pass the verified Principal's TenantKey.
- Current application may continue using in-memory ApprovalAuthority until explicit wiring is reviewed.
- `ExecutionGateway` still persists audit through the existing `JsonlAuditLog`; the SQLite durable audit backend is not yet adapted into the gateway.
- No production secrets, OIDC provider, hosted service, or paid API were configured.

## Verification
- Prior P07-C CI Run #240 succeeded.
- CI for this integration commit series must pass before claiming P07-D verified.
- PR #5 remains open/draft. No merge or deployment approval.
