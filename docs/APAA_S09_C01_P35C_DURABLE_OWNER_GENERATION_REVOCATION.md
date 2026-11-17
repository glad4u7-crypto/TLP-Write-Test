# APAA P35-C — Durable Owner Generation, CAS Revocation and Audit

**Status:** local shared-SQLite coordination primitive implemented; API guard requires its generation reader; operator authentication and external anti-rollback anchor NOT implemented.  
**PR:** #11 — Draft / Open / Unmerged  
**Date:** 2026-11-16

## What changed

Extended `SQLiteSecurityStore` with a singleton `global_owner_config_state` record and these APIs:

- `read_global_owner_state()`: reads the current revision and owner configuration generation from the shared security database.
- `compare_and_set_global_owner_generation(expected_revision, generation, change_id)`: atomically changes or revokes the generation, increments a monotonic-in-database revision and appends the corresponding local hash-chain audit event in the same SQLite transaction.

Generation values must be lowercase SHA-256 hex digests or `None` (revoked/unprovisioned). Change IDs are bounded and strictly validated. Stale concurrent writers receive `GlobalOwnerStateConflict`. A malformed value, no-op transition, stale revision or broken audit chain does not commit the owner-state update.

The Global Admin request guard now requires BOTH:
1. a fresh trusted server-side owner-config loader; and
2. a fresh durable generation reader.

Every request compares the configured generation with the current shared-store generation before checking the exact issuer + subject. A missing, stale or unavailable generation denies access. Therefore a re-key is deliberately fail-closed until the separately authorized operator workflow updates the durable generation.

## Test coverage added

- New `tests/test_global_owner_state.py` covers unprovisioned initial state, two store instances sharing one DB, re-key and revocation revision progression, stale CAS rejection, concurrent CAS single-winner behavior, malformed input rejection, atomic rollback if the existing audit chain is corrupt, and audit privacy.
- Global Admin guard tests now require the durable generation reader and cover stale/missing state and state-reader failure.

These are repository tests added to CI; no local test execution or exact-head CI PASS is claimed in this record.

## Security boundary and limitations

This is a **same-host/shared-SQLite coordination primitive**, not a production anti-rollback anchor:

- SQLite's transaction serializes writers on one shared database and lets multiple app processes observe the same generation, assuming they all use the same authoritative file and storage semantics.
- It does not coordinate independent hosts with separate database copies.
- A privileged attacker who can rewrite/restore the database can roll back both the generation and local audit chain. The existing audit chain detects some accidental/tamper inconsistencies but is not an independently anchored tamper-proof log.
- The audit row intentionally records `external_operator_identity_not_verified`; this code does not authenticate an operator or prove that a change ID was approved.
- The CAS method is a low-level storage primitive. It MUST NOT be exposed to a browser, task, model, or ordinary API route. A future operator-only offline workflow must authenticate the operator out of band, require an independently approved change record, and retain evidence outside this database.
- No automatic config synchronization exists. A mismatch between deployment config and the durable generation denies all Global Admin requests until a separately authorized reconciliation is performed.
- No cross-process session deletion is attempted; the per-request generation check is the enforcement mechanism for future API handlers. Existing Streamlit owner capability caches remain separately subject to identity/config invalidation and do not constitute an API integration.

## Remaining blockers

- Wire the guard into actual privileged routes when an API router exists; current app is Streamlit and no Global Admin API route was found.
- Build and independently review an offline operator provisioning/re-key/revocation workflow.
- Anchor revision/hash externally with independently administered monotonic storage and test restore/rollback attacks.
- Implement authenticated audit identity, protected append-only external retention and recovery.
- Qualify live OIDC, physical Android, production Linux host and independent security review.

## Safety

Global Owner remains inactive. No owner identity, token, secret, API key or private key was added. No privileged route or UI was enabled. PR #11 remains Draft/Open/Unmerged; Auto-Run OFF; Worker/browser OFF; no merge, deployment, production activation, paid API or payment. S09-C01 remains OPEN / NOT COMPLETE.
