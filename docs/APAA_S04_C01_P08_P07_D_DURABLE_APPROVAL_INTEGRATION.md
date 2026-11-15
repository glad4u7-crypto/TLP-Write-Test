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


## Phase 2 runtime wiring update
- Authenticated Streamlit sessions now derive `TenantKey` from the validated OIDC Principal's issuer + subject.
- The runtime requires an operator-provided stable signing secret (hex, at least 32 bytes) in Streamlit secrets before enabling authenticated durable mode; it fails closed rather than silently using an ephemeral key.
- Authenticated mode instantiates `SQLiteSecurityStore`, `ApprovalAuthority(nonce_store=..., signing_secret=...)`, and `SQLiteExecutionAuditLog`; the same TenantKey is passed to receipt issue and gateway consume.
- ExecutionGateway's existing append/verify audit interface is adapted to SQLite; intent and completion events are persisted before/after handler dispatch.
- Project ownership now stores and checks both OIDC issuer and subject. Session identity switching also uses issuer + subject.
- Legacy projects with missing issuer ownership are intentionally not visible/readable to authenticated users; no automatic owner assignment or migration is performed.
- Added tests for cross-issuer approval transfer, same-subject cross-issuer project access, unscoped legacy project denial, and SQLite audit adapter persistence.

## Operator configuration (never commit secrets)
Authenticated deployment requires Streamlit OIDC configuration and a local/private `.streamlit/secrets.toml` entry similar to:
```toml
[apaa]
require_auth = true
approval_signing_secret_hex = "<at-least-64-hex-characters>"
security_db_path = ".apaa_security/security.sqlite3"
```
The `[auth]` OIDC section must also be configured according to Streamlit's supported OIDC setup. Keep `.streamlit/secrets.toml` and the SQLite database out of Git; restrict filesystem permissions and back up the database securely.

## Remaining verification and limits
- CI for the integration series is pending; do not mark this phase complete until the current PR head passes.
- Project data itself remains in the session-local in-memory registry; the SQLite ProjectStore adapter is not yet wired into CRUD.
- The local SQLite audit hash chain detects changes but is not tamper-proof against a writer who can rewrite and recompute the database. Protect the database file and host.
- Local unauthenticated prototype mode deliberately retains in-memory approvals + JSONL audit; it must not be exposed publicly.


## Latest verification
- Run #293 on commit `630c8eda5647c4df9be27798cccc9bd37147593e`: **SUCCESS** — pytest suite and `demo.py` passed.
- Foundation CI Run #234 on the same commit: **SUCCESS** — module compilation and foundation tests passed.
- Earlier failures were corrected and the latest head is green; continue with full app/runtime integration testing before release.

## Superseding integration status — APAA-S04-C01-P08-P09-AJ
The earlier `Not yet integrated` and Phase 2 notes above are historical checkpoint records. The current feature branch has since wired the authenticated Streamlit runtime to durable stores:
- Authenticated sessions construct `SQLiteSecurityStore`, `SQLiteExecutionAuditLog`, and `SQLiteProjectStore` from server-side configuration and validated OIDC issuer + subject.
- `ApprovalAuthority` uses the durable nonce store and protected signing secret; receipt issuance and gateway consumption use the same tenant and session scope.
- `ExecutionGateway` persists the intent audit before dispatch and completion/failure audit afterward. Audit append failure before dispatch blocks the handler.
- Authenticated project CRUD uses `PersistentProjectRegistry` backed by `SQLiteProjectStore`, with issuer + subject predicates. Unscoped legacy project records are not adopted.
- Logout and identity-switch regression tests verify identity-bound session state and stale approval capabilities are cleared; same subject under a different issuer is treated as a different identity.

Current verification on commit `11dd02d2ba2e3a77493e16a2f4e0f0d718865605`: Python Demo CI runs #481 and #482 **SUCCESS**; Agent Foundation CI runs #391 and #392 **SUCCESS**. The new SQLite gateway integration tests cover durable intent/completion rows and fail-closed audit-storage failure.

These results are offline CI evidence only. They do not complete live OIDC/browser verification with two controlled identities, production secret provisioning, multi-host storage design, protected backups/retention/monitoring, independent audit anchoring, or deployment controls. PR #5 remains open and Draft. No merge, deployment, provider activation, or real-world handler enablement is authorized. Production remains **NOT APPROVED**.
