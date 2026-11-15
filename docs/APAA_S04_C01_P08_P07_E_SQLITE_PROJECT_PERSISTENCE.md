# APAA-S04-C01-P08-P07-E — Tenant-Scoped SQLite Project Persistence

Status: **Implementation committed; current-head CI verification pending**

## Implemented
- Added `core/sqlite_project_store.py`, a SQLite-backed project CRUD store.
- Every list/get/update/delete query is constrained by the composite OIDC tenant key: issuer + subject.
- Added transactional create/update/delete operations, SQLite busy timeout, input validation, and schema version record.
- Added `core/persistent_projects.py`, a ProjectRegistry-compatible facade bound to one validated TenantKey.
- Authenticated Streamlit mode now creates the persistent project store using `[apaa].project_db_path` (default `.apaa_projects/projects.sqlite3`) and uses the persistent registry.
- Unauthenticated local prototype mode intentionally remains in-memory and is not suitable for public exposure.
- Session identity changes clear the tenant-bound registry, selection, pending approvals, gateway, and user-specific drafts.
- Added `.apaa_projects/` to `.gitignore`; no database or secrets are committed.
- Added tests for restart persistence, tenant isolation, CRUD, concurrent creates, registry authorization, and approved gateway creation followed by store reconstruction.

## Operator configuration
The authenticated Streamlit configuration requires:
```toml
[apaa]
require_auth = true
approval_signing_secret_hex = "<at-least-64-hex-characters>"
security_db_path = ".apaa_security/security.sqlite3"
project_db_path = ".apaa_projects/projects.sqlite3"
```
Configure Streamlit's `[auth]` OIDC settings separately. Never commit `.streamlit/secrets.toml`, either SQLite database, or production signing material. Restrict host filesystem access and back up databases securely.

## Legacy data
No migration or ownership guessing is performed. Old in-memory projects disappear with their original session; legacy records without trusted issuer + subject ownership are not imported. If a future legacy import is needed, require explicit owner verification and a reviewed migration.

## Verification boundaries
- The latest preceding head `8929955c00de0f4472493ad7d2fe0ffa4c996c60` passed Python Demo CI #311 and Agent Foundation CI #243.
- The current integration commit adds an end-to-end approved gateway -> persistent project store -> reconstructed registry test. Its CI runs must pass before this checkpoint is marked verified.
- Live OIDC provider login, multi-process deployment, filesystem permission hardening, and backup/restore drills have not been performed.
- SQLite hash chaining detects accidental/unauthorized row changes when verified, but a privileged attacker able to rewrite the database can recompute hashes. Protect the host and database file.
- PR #5 remains Draft; do not merge or deploy based only on unit CI.
