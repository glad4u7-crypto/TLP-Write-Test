# APAA-S04-C01-P08-P07-A — Storage Interface & Tenant Schema

Status: **Contract and schema defined; no persistence adapter or migration executed**

## Implemented artifacts
- `core/storage.py`: immutable `TenantKey` (issuer + subject), `StoredProject` DTO, tenant-scoped `ProjectStore` protocol, SQLite schema v1 contract.
- `tests/test_storage.py`: validation for tenant identity, issuer collision separation, protocol surface, and schema contract.
- No changes to current runtime project storage or authentication flow.

## Security properties designed into the contract
- Tenant key is the pair `(issuer, subject)`; subject alone is never sufficient.
- Every read, update, and delete operation requires the tenant key.
- Project persistence columns store issuer and subject separately and index tenant-scoped lookups.
- Schema rejects empty issuer/subject and enforces project name/description bounds.
- Schema contains no client-supplied owner field.
- SQL schema is a static constant; future adapter must use parameterized SQL for all values.

## Migration and legacy-data policy
- This step does not import or assign legacy in-memory/session records.
- Records with absent or ambiguous ownership must be quarantined; never attach them to the first authenticated user.
- Migration must be explicit, reviewed, backed up, and tested before any legacy record is exposed.
- Schema version is declared as 1. Actual migration ledger writes and database initialization belong to P07-B.

## Deferred
- SQLite connection lifecycle, WAL/locking, transactions, and adapter implementation.
- Integration with `ProjectRegistry` and Streamlit.
- Cross-process and concurrent mutation tests.
- Persistent approval nonce consumption and durable audit storage.

## Verification
- Prior architecture commit `7085ee43d5ff243f8345a6c3ef97e126b432669a`: Python Demo CI Run #219 succeeded.
- CI for this P07-A commit must be checked after push.

## Safety boundaries
- Local/free-only design. No hosted database, paid service, API key, or external provider.
- Existing runtime behavior is unchanged.
- No payment, purchase, trading, money movement, arbitrary execution, or Auto-Run.
- Keep PR #5 draft; do not merge or deploy publicly.
