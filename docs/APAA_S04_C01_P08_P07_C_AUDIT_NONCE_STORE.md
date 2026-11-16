# APAA-S04-C01-P08-P07-C — Durable Audit & Approval Nonce Store

Status: **SQLite persistence primitives added; audit verification bug corrected; latest CI pending**

## Added implementation
- `core/sqlite_security_store.py`: local SQLite tables for durable approval nonce consumption and payload-free audit events.
- Nonce uniqueness is scoped by composite tenant identity (issuer + subject) and nonce.
- `BEGIN IMMEDIATE` serializes nonce consumption; duplicate concurrent submissions have at most one winner.
- Audit events are appended transactionally and linked by a SHA-256 hash chain.
- Audit event fields are bounded and exclude task payloads and bearer tokens.
- `tests/test_sqlite_security_store.py`: tenant scoping, expiry, invalid input, concurrent replay, restart persistence, and audit-chain tests.

## CI failure and correction
- First CI for the new storage module: Run #236 failed during pytest.
- Inspection found audit verification calling `hashlib.compare_digest`, which is not the correct API.
- Corrected to `hmac.compare_digest` in commit `090feb32a2dbf4ebda50600b82a76497f1608f9f`.
- The corrected commit's CI must pass before this checkpoint is verified.

## Integration boundary
- This module is not yet wired into `ApprovalAuthority`, `ExecutionGateway`, or the Streamlit app.
- Current approval signing secret and in-memory consumed nonce set remain unchanged.
- Current `JsonlAuditLog` remains in runtime use unless a later reviewed integration replaces it.
- Callers must validate identity and receipt signature before nonce consumption.
- A local hash chain is tamper-evident, not tamper-proof against an attacker with database write access.

## Safety
Local SQLite only; no paid service, external API, credentials, payment, purchase, trading, money movement, or execution handlers added. Auto-Run remains disabled. PR #5 stays draft; no merge or production approval.
