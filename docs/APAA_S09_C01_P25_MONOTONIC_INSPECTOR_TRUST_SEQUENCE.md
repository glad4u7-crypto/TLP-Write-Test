# APAA-S09-C01-P25 — Monotonic inspector trust-sequence acceptance gate

**Status:** implementation committed; exact-head CI verification pending  
**Branch:** `feature/apaa-s09-c01-p16-oci-lifecycle`  
**PR:** #11 (Draft/Open/Unmerged)  
**Deployment / merge / Auto-Run:** not authorized

## Delivered

- Added `core/inspector_trust_sequence.py` to compose P24 signed-bundle verification with an independently administered monotonic sequence anchor.
- Added a strict `MonotonicSequenceBackend` protocol. The backend must expose a high-water mark per issuer and atomic compare-and-advance semantics.
- The gate reads the current sequence, requires a strictly higher signed bundle, verifies signature/issuer/validity/key records, and then performs a compare-and-swap advance.
- The verified registry is returned only after the backend confirms that the new sequence was durably advanced.
- A stale bundle, invalid anchor, failed persistence, or concurrent update fails closed. A concurrent update requires the caller to reload and retry.
- Added offline tests for successful advancement, replay rejection, compare-and-swap race, missing backend and invalid anchor values.

## Important security boundary

This change is an integration contract and acceptance gate, **not a production anti-rollback storage implementation**. No local file, ordinary SQLite database, GitHub variable, worker filesystem or Android client is accepted as a secure monotonic anchor merely because it is durable. Any such storage may be restored from an older snapshot.

A production adapter must be backed by an independently protected monotonic primitive or service whose restore/recovery procedure cannot lower the high-water mark. It must be separately threat-modeled, access-controlled, audited and qualified. The repository intentionally does not invent an HSM/TPM/cloud monotonic service or claim one is configured.

## Required production adapter qualification

1. Select an available independent monotonic anchor under the owner's explicit infrastructure decision.
2. Define issuer-scoped identity, authentication, authorization and atomic compare-and-swap.
3. Demonstrate persistence-before-success, concurrent writer safety, restart behavior and backup/restore rollback rejection.
4. Define recovery when the anchor is unavailable; fail closed and never reset to zero.
5. Audit accepted sequence, bundle digest, issuer, actor and timestamp without logging private key material.
6. Inject the qualified adapter into the authenticated control-plane configuration path.

## Verification

CI tests use an in-memory fake only to validate the protocol contract. They do not qualify a production anchor. Exact-head CI must pass before this checkpoint is marked implementation-verified.

No production keys, credentials, paid services, network endpoints, deployment, firewall mutation, worker launch, browser activation, merge or Auto-Run are introduced.
