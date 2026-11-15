# APAA-S04-C01-P08-P07-B — SQLite ProjectStore Adapter

Status: **Adapter and automated tests added; runtime integration remains deferred**

## Added
- `core/sqlite_storage.py`: local SQLite implementation of the `ProjectStore` protocol.
- `tests/test_sqlite_storage.py`: persistence, issuer/subject isolation, cross-tenant mutation denial, field validation, and parameterized-input tests.

## Implementation details
- Uses Python standard-library `sqlite3`; no new dependency or hosted service.
- Initializes schema version 1 and migration ledger transactionally.
- Uses parameterized SQL for all user-provided values.
- Every list/read/update/delete operation filters by both `tenant_issuer` and `tenant_subject`.
- Create derives ownership only from the supplied TenantKey; caller must construct it from a validated server-side Principal.
- Write operations use `BEGIN IMMEDIATE`; connection busy timeout is configured.
- Database parent directory is created when the store is explicitly instantiated.

## Important limitations
- This adapter is not yet wired into Streamlit or the existing in-memory ProjectRegistry.
- No migration of legacy in-memory records is performed; legacy ownership remains unresolved and must not be auto-assigned.
- SQLite WAL mode, backup/restore, production file permissions, multi-host deployment, and process-level operational testing remain open.
- Approval nonce replay protection and audit persistence are not addressed in this step.
- Tests are authored but CI must pass before marking this checkpoint verified.

## Security and release
No paid service, API key, network service, payment, trading, or execution capability was introduced. Auto-Run remains disabled. PR #5 remains draft and must not be merged or deployed as production-ready.
