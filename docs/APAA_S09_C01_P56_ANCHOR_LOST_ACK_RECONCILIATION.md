# APAA-S09-C01-P56 — Lost-acknowledgement reconciliation for external anchor CAS

**Status:** coordinator change and adversarial tests committed; exact-head CI pending.

## Problem

An external anchor may durably commit a compare-and-advance request while the network response is lost. Treating every transport exception as a definite failed write is safe but leaves a committed anchor transition unnecessarily unreconciled. Retrying the CAS blindly is also unsafe.

## Delivered

Updated `OfflineOwnerRecoveryService.apply()`:

1. Attempt the one-step anchor CAS.
2. If the call raises (including timeout/connection loss), perform one authoritative anchor read.
3. Continue only if the read returns the exact intended target state.
4. If the read fails or returns any other state, raise a sanitized RecoveryDenied with outcome unknown; do not mutate local owner state.
5. Never issue an automatic second CAS after an ambiguous result.

Added tests:
- Provider commits target and loses acknowledgement: exact read-back reconciles and owner-state commit completes.
- Provider commits target but read-back is unavailable: local owner state remains unchanged and recovery fails closed.
- Existing pre-commit outage regression remains: anchor stays at expected state and local state is not mutated.

This implements the P36B/P41 rule: timeout-after-commit is reconciled only by exact authoritative read-back. It does not make a fake provider independent or durable; the remote provider must still prove its own consistency and rollback behavior.
