# APAA-S04-C01-P08-P07-C — Durable Audit & Approval Replay Storage

Status: **Transactional storage primitives added; execution integration is deferred**

## Added
- `core/sqlite_security_store.py`: SQLite-backed durable approval nonce consumption and payload-free audit event append.
- `tests/test_sqlite_security_store.py`: one-time nonce, tenant scope, expiry, concurrent duplicate, restart persistence, audit chain, and tamper-detection tests.

## Approval nonce properties
- Unique key is (issuer, subject, nonce).
- `BEGIN IMMEDIATE` serializes writes; database uniqueness guarantees at most one successful consume for a tenant/nonce.
- Expired nonce rows are cleaned during consume.
- Caller MUST authenticate the principal and verify the receipt HMAC, action, payload digest, and expiry before calling consume.
- The existing in-memory ApprovalAuthority is NOT replaced in this step. Runtime integration and receipt principal binding are a separate reviewed change.

## Audit properties
- Audit append is serialized in a SQLite write transaction, including previous-hash lookup and insert.
- Stored fields are restricted to action, result, reason code, principal fingerprint, request ID, timestamp, and hash-chain metadata.
- Task payloads, raw OIDC claims, bearer tokens, and secrets are not accepted as event fields.
- Chain verification detects ordinary row alteration, deletion, and reordering.
- A plain hash chain is not tamper-proof against an attacker with unrestricted database write access. Production needs independently protected HMAC/signing keys or an external append-only trust boundary.

## Deferred / limitations
- No integration with ExecutionGateway, ApprovalAuthority, or current JsonlAuditLog.
- No production key management, database backup/retention/rotation, WAL policy, or multi-host deployment.
- No migration of existing JSONL audit records or consumed nonces.
- A failed audit append must continue to block execution; caller integration tests are still required.
- SQLite is local-file, single-host storage, not distributed consensus.

## Verification and release
- P07-B CI must be verified on the current head before relying on it.
- P07-C CI is pending until GitHub Actions completes.
- PR #5 remains draft; no merge or production approval.
- No paid service, API key, network service, payment, trading, or execution capability enabled. Auto-Run remains disabled.

## Superseding implementation status — APAA-S04-C01-P08-P09-AJ
The original P07-C status above is historical and has been superseded by later integration work. On the current feature branch:
- `ExecutionGateway` accepts the durable SQLite audit adapter through its append interface and records a durable intent event before invoking a registered handler, followed by a completion/failure event.
- Authenticated Streamlit mode constructs `SQLiteSecurityStore` and `SQLiteExecutionAuditLog` using the validated issuer + subject tenant context.
- Authenticated project CRUD uses `SQLiteProjectStore` through `PersistentProjectRegistry`; legacy unscoped rows are not silently adopted.
- Regression coverage now includes gateway-to-SQLite intent/completion persistence, fail-closed behavior when intent audit append fails, crash recovery of an uncommitted audit event, and tenant isolation.

The historical deferred bullets above describe the earlier P07-C checkpoint, not the current implementation. Remaining limits are unchanged: SQLite is local single-host storage; the hash chain is not independently tamper-proof against a database writer; production still requires protected host/storage, backup/retention/monitoring, and independent anchoring. Live OIDC/browser verification and production deployment gates remain outstanding. PR #5 stays Draft; production is NOT APPROVED.
