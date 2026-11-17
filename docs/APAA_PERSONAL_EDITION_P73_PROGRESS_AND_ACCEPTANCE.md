# APAA Personal Edition — P73 Runtime and Persistence Progress

**Checkpoint:** APAA-PERSONAL-P73  
**Date:** 2026-11-17  
**Branch:** `apaa-personal-edition-foundation`  
**Current reviewed head:** `54b6f0806cadfed869e199ed347b83ac7bc0ba34`  
**Status:** In progress; not release-ready.

## Completed in this increment

- Added `core/personal_runtime.py`: fixed local owner context, owner-private data directory checks, symlink rejection, stable local approval signing-key creation/loading, and fail-closed handling of invalid key files.
- Added `core/personal_storage.py`: SQLite project persistence with a composite (issuer, subject) owner scope on every read/update/delete operation; validated project fields; owner-only database and directory permissions; basic schema version tracking; deterministic connection cleanup.
- Added `tests/test_personal_runtime.py` and `tests/test_personal_storage.py`: unit coverage for local owner identity, persistence across store instances, owner isolation, CRUD, input validation, file permissions, symlink rejection and corrupt-key behavior.
- Preserved the existing OIDC/enterprise paths and did not remove modules whose dependency graph has not yet been proven safe to remove.

## Important limitation

The new SQLite Personal Project Store is a persistence adapter, but it is **not yet wired into the Streamlit app's local Personal Edition startup or Project Manager UI**. Existing unauthenticated prototype mode still uses session-scoped projects. Do not describe persistent projects as available in the running app until runtime integration and restart acceptance tests pass.

The current approval authority and audit implementations also need a Personal Edition durable configuration using the local signing key and durable nonce/audit stores. The existence of the key helper or audit modules alone does not establish that this flow is integrated.

## Required remaining work — C01 only

1. **Runtime Integration:** initialize one local owner runtime from a private data directory; ensure loopback-only startup for unauthenticated local mode; wire project, approval and audit services without trusting browser/task-supplied identity.
2. **Persistent Storage:** connect project/task/checkpoint data to durable SQLite; define backup/export and restore behavior; test restart, corruption, permissions, and recovery.
3. **Approval & Audit:** use stable local signing material and durable one-time nonce consumption; require fresh action/payload-bound confirmation for each mutation; record every attempted/approved/denied/executed/failed action without secrets or sensitive payloads; fail closed if audit persistence fails.
4. **Browser Security:** keep browser execution disabled until origin allowlists, SSRF/private-network defenses, download/upload boundaries, session isolation, cancellation and approval gates have dedicated tests.
5. **Android Acceptance:** responsive UI review and physical Android browser testing; do not claim native APK/PWA or remote device control without implementation and evidence.
6. **Final Verification:** run the full test suite and exact-head CI; review PR stack/dependencies; perform backup/restore and security regression tests; document limitations.

## Non-negotiable boundaries

- One owner; Android is the primary client.
- Free-only; no paid API, provider, hosting or billable service.
- Ask First; Auto-Run remains OFF.
- Payment, purchase, checkout, trading, investment orders and money movement remain prohibited.
- No public signup, collaborator access, public/LAN exposure, deployment or merge in this checkpoint.
- Do not start C02 until C01 is complete and the owner explicitly approves the C01 result.

## Verification record

At the time this note was written, GitHub reported no status checks and no workflow runs for the current head. Tests have **not** been executed in this environment. Therefore no PASS claim is made. The PR remains Draft/Open/Unmerged.
