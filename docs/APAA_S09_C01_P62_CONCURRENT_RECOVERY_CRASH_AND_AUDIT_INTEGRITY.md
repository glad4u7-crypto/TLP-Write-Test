# APAA-S09-C01-P62 — Concurrent recovery, crash injection and audit integrity

**Date:** 2026-11-16  
**Branch:** `feature/apaa-s09-c01-p16-oci-lifecycle`  
**PR:** #11 — Draft / Open / Unmerged  
**Scope:** Disposable software tests for concurrent owner recovery, crash boundaries and audit-chain tampering.  
**Status:** Implementation committed; exact-head CI verification required.  
**Production qualification:** NOT QUALIFIED. No physical token, production anchor, host or credential was used.

## Implemented test coverage

Added `tests/test_apaa_p62_recovery_crash_audit_integrity.py`.

1. **Concurrent recovery race:** two independently dual-signed requests race from the same owner revision. Exactly one transition may commit; the losing request is denied; local owner state, reference anchor and audit count remain consistent.
2. **Crash at audit append:** a disposable SQLite trigger injects an abort at the durable audit INSERT after the reference anchor has advanced. The local SQLite transaction must roll back the owner-state update. The service must report the anchor-ahead resumable state; after removing the injected fault, the same valid request must safely resume and converge.
3. **Audit field/hash/deletion tampering:** alter a recorded reason, alter an entry hash, or delete an earlier entry from a multi-entry chain. Verification must fail and owner recovery must be blocked before another anchor transition.
4. **Audit reordering:** alter sequence ordering and require chain verification to fail; subsequent recovery must be denied.

The P62 tests are isolated, use ephemeral Ed25519 keys, a temporary SQLite database and a deterministic in-memory anchor. They are not evidence of production anchor independence, physical key custody, filesystem durability under real power loss, or external audit immutability.

## Existing recovery boundaries exercised

The existing recovery implementation verifies the audit chain before changing the independent anchor, advances the anchor with CAS, and only then commits the local owner generation with a transactional audit append. A one-revision anchor-ahead state is resumable because it can represent a crash after the external CAS; larger divergence is blocked. P62 adds explicit failure injection at the local audit append boundary.

## Acceptance and residual risks

- P62 software tests are accepted only after all required exact-head CI workflows pass.
- Real multi-process/host failure drills and a separately administered durable anchor remain external qualification work.
- Physical HSM/PKCS#11 rotation and recovery remain blocked pending an owner-approved, independently identified compatible device.
- No real backup was restored, no production key was rotated/revoked, and no external anchor account or credential was created.

## Safety and release locks

PR #11 remains Draft / Open / Unmerged. Auto-Run OFF; Worker and Browser DISABLED. No merge, deployment, production activation, host/firewall mutation, paid provider, payment, purchase or C02 start. C01 remains OPEN pending P63 review and the mandatory external evidence gates.


## 6. Latest branch-head regression verification

The P62 tests remain included in current branch head `c5908fe926c1e3ba37b446d26fe765652d6e4fdb`. On that exact head, Agent Foundation CI #1214, Python Demo CI #1303, P20 #343 and P23 #325 all completed successfully (4/4 PASS); each pytest job reported 1,348 passed and 9 skipped. This validates the disposable software concurrency, injected SQLite crash and audit-chain tampering tests only. Real multi-host/power-loss/disaster-recovery and external immutable-audit qualification remain BLOCKED.

**P62 software scope: COMPLETE. Production qualification: NOT QUALIFIED.**


## 7. Remediation clarification — inspection status after audit tampering

`OfflineOwnerRecoveryService.inspect()` now verifies the durable audit chain before reporting an owner/anchor disposition. An invalid or unavailable audit chain is reported as `AUDIT_INTEGRITY_BLOCKED`, rather than incorrectly presenting an otherwise matching owner state and anchor as `CONSISTENT`. P62 regression coverage asserts this disposition after audit field/hash/deletion tampering and sequence reordering. Recovery continues to fail closed before any subsequent anchor mutation.
