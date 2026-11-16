# APAA-S09-C01-P61 — Independent anchor durability and recovery conformance

**Date:** 2026-11-16  
**Scope:** Restart persistence, monotonic high-water mark, concurrent compare-and-swap, backup/restore rollback resistance.  
**Status:** Reference-model tests committed; exact-head CI pending.  
**Production anchor status:** NOT QUALIFIED. No independent remote anchor service or production credentials were accessed.

## Implemented tests

Added `tests/test_apaa_p61_independent_anchor_durability.py`.

The tests exercise the existing `MonotonicSequenceBackend` protocol and signed-bundle acceptance path:

1. **Restart persistence:** recreate the adapter over the same durable-store fixture and confirm the accepted sequence remains visible; replay of the same bundle is rejected.
2. **Old-backup rollback:** reject restoring a snapshot older than the accepted high-water mark.
3. **Current backup restore:** accept restoring a snapshot that does not lower the high-water mark.
4. **Concurrent CAS:** race two writers from the same expected sequence and require exactly one successful advance.
5. **Stale/non-increasing writes:** reject a stale expected value and reject a non-increasing sequence.
6. **Newer-backup rollback:** reject restoring an earlier snapshot after a later sequence has been committed.

## Critical qualification boundary

The included `DurableReferenceAnchor` is a deterministic in-memory reference model. It demonstrates the expected contract and tests the caller's behavior; it is **not** an independent remote service, hardware monotonic counter, durable database adapter, or disaster-recovery system.

A production adapter still needs all of the following evidence:

- independent administrative and credential boundary from the APAA worker/host;
- durable atomic compare-and-swap under concurrent clients;
- commit durability confirmed before acknowledging success;
- restart and service-recovery persistence against the actual service;
- backup/restore procedure that cannot lower the high-water mark;
- stale backup and disaster-recovery drills;
- service outage, timeout and partial-failure behavior that fails closed;
- independent audit of operator access, retention and recovery controls.

A backup stored in the same administrative or rollback domain as the worker does not qualify as an independent anchor. A local file, SQLite database, or ordinary host snapshot is not sufficient evidence.

## Safety and project gates

No production endpoint, credential, token, private key, paid service, deployment or merge was used. No real backup was restored or altered.

PR #11 remains Draft/Open/Unmerged. Auto-Run OFF. Worker OFF. C02 NOT STARTED. C01 remains OPEN pending exact-head CI and external qualification evidence.

## Acceptance

P61 reference-model software tests may be accepted only after exact-head CI passes. Production independent-anchor qualification remains BLOCKED until a real independently administered adapter and its restart/backup/restore evidence are available.
