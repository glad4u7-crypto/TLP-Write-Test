# APAA Personal Edition — P73 Runtime and Persistence Progress

**Checkpoint:** APAA-PERSONAL-P73  
**Date:** 2026-11-17  
**Branch:** `apaa-personal-edition-foundation`  
**Current reviewed head:** `54b6f0806cadfed869e199ed347b83ac7bc0ba34`  
**Status:** In progress; not release-ready.

## Completed in this increment

- Added `core/personal_runtime.py`: fixed local owner context, owner-private data directory checks, symlink rejection, stable local approval signing-key creation/loading, and fail-closed handling of invalid key files.
- Added `core/personal_storage.py`: SQLite project persistence adapter with composite (issuer, subject) owner scope, validated fields, private file permissions and deterministic connection cleanup.
- Wired the unauthenticated local Personal Edition app startup to the fixed local owner, private `~/.apaa_personal` data directory (overridable only by server-side `APAA_PERSONAL_DATA_DIR`), persistent SQLite projects, stable local signing key, durable SQLite approval nonces and SQLite execution audit.
- Local project actions now take the fixed owner from the server-side persistent registry, never from task/browser payloads. Existing in-memory test registries retain their prototype behavior.
- Local mode rejects non-loopback Streamlit server address configuration.
- Added `tests/test_personal_runtime.py` and `tests/test_personal_storage.py`: unit coverage for local owner identity, persistence across store instances, owner isolation, CRUD, input validation, file permissions, symlink rejection and corrupt-key behavior.
- Preserved the existing OIDC/enterprise paths and did not remove modules whose dependency graph has not yet been proven safe to remove.

## Important limitation

The SQLite project store is now wired into the local Project Manager path, and local approval nonce consumption plus execution audit use the durable SQLite security store and stable local signing key. Integration tests have been added for project restart persistence, one-time approval replay rejection and audit-chain verification. However, these tests have not yet been executed in this environment, so runtime acceptance is not yet proven.

Tasks and checkpoints are not yet fully migrated to the Personal Edition local database. The current UI's task/plan state and memory/checkpoint surfaces need a separate persistence integration pass.

## Required remaining work — C01 only

1. **Runtime Integration:** run the Streamlit app and acceptance suite on an actual Android/Python environment; verify loopback binding behavior and confirm project/approval/audit services restart cleanly.
2. **Persistent Storage:** migrate task and checkpoint state to durable SQLite; define backup/export and restore behavior; test restart, corruption, permissions, and recovery.
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
