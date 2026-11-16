# APAA-S09-C01-P61 — Independent monotonic anchor adapter design

**Status:** Provider-neutral design specification; no production adapter instantiated.  
**Security classification:** Design-only. No endpoint, credential, paid service, or production data used.

## 1. Purpose and trust boundary

The anchor stores a per-issuer monotonic high-water mark for signed inspector trust bundles. It must be administered independently from the APAA worker and its host. Compromise or rollback of the worker, its filesystem, its database, or its backups must not permit a previously accepted trust bundle to be accepted again.

An anchor is not independent merely because it is a remote URL. It needs a separate administrative identity, separate credential lifecycle, durable storage, protected backups, and an operator/audit boundary not controlled by the worker.

## 2. Minimal adapter contract

The adapter implements the existing `MonotonicSequenceBackend` interface:

- `read_sequence(issuer_key_id) -> int`: return the durable high-water mark; return zero only for a genuinely uninitialized issuer.
- `advance_sequence(issuer_key_id, expected_current, new_sequence) -> bool`: atomically compare the stored value with `expected_current`, require `new_sequence > expected_current`, durably commit the new value, and only then return true. A mismatch returns false without mutation.

Required invariants:

1. Linearizable compare-and-swap per issuer.
2. A successful acknowledgement means the value is durable across process and service restart.
3. No backup restore, replica failover, disaster recovery, or operator action may reduce the high-water mark.
4. Unknown issuer, malformed value, stale expected value, timeout, unavailable service, ambiguous commit outcome, or authorization failure must fail closed.
5. The APAA worker must not possess anchor administration, backup restore, or high-water-mark reset privileges.

## 3. Suggested service-side data model

Use one record per issuer with `issuer_key_id`, `sequence`, `updated_at`, and an audit/event reference. Enforce a unique issuer key. The storage transaction must conditionally update only where the current sequence equals `expected_current` and the proposed sequence is greater. Do not implement read-then-unconditional-write.

The anchor service must own its own durable transaction boundary. The APAA adapter should not cache authoritative sequence values; a cache may be used only as a non-authoritative optimization and must never allow acceptance without a fresh authoritative compare-and-swap.

## 4. Failure and retry semantics

- CAS mismatch: return false; caller reloads the latest signed bundle and retries only through normal policy.
- Definite pre-commit outage: raise an unavailable error; do not accept the bundle.
- Timeout or connection loss after submitting a write: outcome is ambiguous. Read back from the authoritative service before any retry; never assume the write failed and never return an accepted registry until the committed sequence is confirmed.
- Authentication/authorization failure: fail closed and emit a security event without leaking credentials.
- Corrupt, negative, non-integer, or missing persisted value for an initialized issuer: fail closed and require operator-led recovery; do not silently reset to zero.

## 5. Backup, restore, and disaster recovery

Backups must be protected in a separate administrative and recovery domain. A restore must reconcile against a monotonic witness that is not contained solely in the backup being restored. If the system cannot prove that the restored value is at least the last acknowledged high-water mark, it must refuse service and enter a recovery-required state. Never offer a worker-accessible reset or downgrade operation.

Qualification drills must include stale backup restore, lost primary replica, region/service recovery, interrupted transaction, and concurrent writers across independent service instances. Record the pre-event and post-event sequence, transaction/audit IDs, operator identity, and independent witness result.

## 6. Credential and administration model

The worker receives only the minimum identity needed to read and request a monotonic advance. It must not be able to create/delete issuers, alter policy, lower sequence values, restore backups, change retention, or administer the anchor. Anchor administrators use separate strong authentication and independently reviewed break-glass procedures. Credentials must be rotatable and revocable without exposing a reset path.

## 7. Audit and observability

Record issuer, old sequence, proposed sequence, outcome, request/correlation ID, service transaction ID, timestamp, caller identity, and reason code. Audit records must be append-only or independently tamper-evident. Do not log private keys, tokens, PINs, bearer credentials, or sensitive request payloads. Alert on repeated CAS conflicts, rollback attempts, restore attempts, authorization failures, and unexplained sequence gaps.

## 8. Conformance test matrix

| Scenario | Required result |
|---|---|
| Two writers use same expected value | Exactly one CAS succeeds |
| Restart after acknowledged write | Latest sequence remains |
| Stale or equal proposed sequence | Rejected without mutation |
| Restore backup older than acknowledged sequence | Restore blocked or service remains unavailable pending witness reconciliation |
| Timeout after write submission | Read-back reconciliation; no blind retry or acceptance |
| Service unavailable | Fail closed |
| Worker attempts admin/reset/restore operation | Denied and audited |
| Replica failover | No acknowledged sequence loss |
| Audit tampering attempt | Detected or prevented by independent audit control |

## 9. Qualification gates and explicit non-claims

This document is a design specification, not implementation or production qualification. The P61 in-memory reference model does not prove database durability, independent administration, remote service availability, backup safety, or disaster recovery. Those require a selected real service, a reviewed adapter implementation, test environment, independent credentials, and observed evidence.

No provider has been selected. No paid service or API is authorized. Do not request or use production credentials as part of this phase. No deployment or merge is permitted. PR #11 remains Draft/Open/Unmerged; Auto-Run OFF; Worker OFF; C02 NOT STARTED; C01 remains OPEN.
