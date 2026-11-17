# APAA Personal Edition P83 — Persistent Task Plans

**Status:** Implemented; exact-head CI verification required.
**Scope:** Store and recover Owner-approved structured plans per personal project.

## Data model

- New `saved_task_plans` table in the existing private SQLite memory database.
- Each record is scoped by Owner issuer, Owner subject, project ID and deterministic plan ID.
- Plan snapshots are stored as bounded canonical JSON with creation/update timestamps.
- Existing memory database backup/restore automatically includes this table because the database is snapshotted as a whole.
- Saving and deleting require explicit consent at the storage API; the app routes saving through a fresh payload-bound Owner approval receipt and the durable action audit.

## User workflow

1. Prepare a structured offline plan.
2. Select an existing project.
3. Review the exact plan and explicitly approve saving it.
4. Later, open Saved task plans for this project and load a snapshot.
5. The saved JSON is reconstructed into typed plan objects and fully revalidated before display.

## Safety

- Persisted plans are proposals only. Saving or loading does not approve or execute any task step.
- Proposed mutation steps continue to require separate action-specific approval if an executor is added in the future.
- Secret-like content, oversized snapshots, mismatched plan IDs/descriptions and malformed typed steps are rejected.
- Plan listing is Owner/project scoped; no cross-owner or cross-project lookup is exposed.
- No task is dispatched and no browser, shell, file-write or external mutation handler is enabled by this checkpoint.

## Verification

Automated tests cover explicit consent, restart persistence, owner/project isolation, snapshot validation, tampered approval flags and consent-gated deletion. Exact-head CI is required before marking the checkpoint verified.