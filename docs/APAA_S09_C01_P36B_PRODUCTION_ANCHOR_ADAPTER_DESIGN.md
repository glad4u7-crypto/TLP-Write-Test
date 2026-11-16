# APAA S09-C01 P36B — Production Monotonic Anchor Adapter Design

**Status:** provider-neutral design and synthetic contract tests only  
**Production adapter:** NOT IMPLEMENTED  
**Production credentials / cloud accounts / TPM / HSM:** NOT USED  
**Release state:** PR #11 Draft / Open / Unmerged; Global Owner inactive

## 1. Purpose and trust boundary

The anchor is an independently administered, durable monotonic high-water mark for the Global Owner generation. It protects against restoring an older local SQLite database and against two recovery coordinators attempting to advance the same revision.

The existing `MonotonicOwnerAnchor` protocol is the only coordinator-facing interface:

- `read() -> AnchorState`
- `compare_and_advance(expected, target) -> bool`

A future adapter must be outside the SQLite database, outside its backup/restore domain, and administered independently of the APAA application host. A second table, file, volume snapshot, or database in the same administrative/backup domain is not independent.

## 2. Required provider semantics

A provider is eligible only if it can demonstrate all of the following:

1. **Linearizable conditional write:** compare the complete expected state and advance to the target as one atomic operation. No read-then-unconditional-write emulation.
2. **Monotonic revision:** target revision is exactly expected revision + 1. Lower revisions, same-revision mutation, skipped revisions and conflicting targets are rejected.
3. **Durable acknowledgement:** success is returned only after the provider's documented durability boundary. A timeout/lost response is treated as unknown outcome; the caller must re-read and reconcile, never blindly issue a new transition.
4. **Independent rollback domain:** APAA host operators and SQLite backup administrators cannot restore or rewrite anchor history. Provider backup/restore must preserve the high-water mark or require a separately controlled, audited break-glass ceremony.
5. **Restart and multi-client consistency:** reads after process restart and across independent clients return the committed state. Concurrent CAS requests have exactly one winner for one expected revision.
6. **Authenticated transport and least privilege:** mutually authenticated or provider-native workload identity; adapter identity can read and conditionally advance only the designated anchor. No broad account, project or tenant administrator credential.
7. **Key and identity lifecycle:** provider identity rotation/revocation is separately approved, audited, tested, and fail-closed. No private operator/approver signing key is stored in the anchor adapter.
8. **Bounded failure behavior:** unavailable, malformed, stale, unauthorized, rate-limited or ambiguous responses never cause local owner-state mutation or rollback.
9. **No silent reset:** missing anchor, recreated resource, empty state or provider-side rollback is a hard failure, not an implicit revision-zero initialization. Bootstrap is a separate offline dual-control ceremony.
10. **Audit evidence:** provider-side immutable or independently retained records bind expected revision, target revision, change ID, result and provider request identifier without storing owner credentials or private keys.

## 3. State and transition contract

The logical anchor state is `(revision, generation, change_id)`. Revision zero is the sole uninitialized state and must contain null generation and change ID. Every later state has a non-negative revision, optional SHA-256 generation digest, and valid change ID.

For a transition from state E to state T:

- T.revision must equal E.revision + 1.
- T.change_id must be present.
- The adapter atomically succeeds only if the stored complete state equals E.
- Repeating the same request after a lost acknowledgement must not advance again. A subsequent read returning T allows the coordinator to reconcile the known target; a different state is a conflict.
- The adapter must not provide a rollback, delete, reset, restore-old-snapshot or force-write method through the application interface.

The current coordinator intentionally treats a one-revision anchor lead as potentially resumable because an anchor commit followed by a local SQLite crash produces the same observable state as restoring a one-revision-old SQLite backup. A gap greater than one revision is blocked. Even a one-step lead can resume only with the exact still-valid dual-signed envelope that binds the target.

## 4. Candidate provider evaluation — no selection made

Provider options may include a hardware-backed monotonic counter or a remote conditional-write service in a separate security account. No provider is selected in this phase. A generic object store, ordinary mutable file, same-database row, or service without atomic compare-and-advance is not acceptable merely because it is remote or encrypted.

Before selecting a provider, document its consistency model, durability guarantees, administrative separation, restore semantics, IAM policy, identity rotation/revocation, audit retention, outage behavior, cost and operational recovery. Any paid service requires a separate explicit user decision and cost approval; it is not part of this free-only implementation.

## 5. Synthetic contract-test strategy

`tests/test_owner_anchor_contract.py` exercises the protocol against a test-only shared-state backend:

- concurrent CAS contention: exactly one writer wins;
- stale expected-state and invalid revision transitions are rejected;
- a simulated process restart sees the same committed state;
- lost acknowledgement after a committed write is reconciled by reading the target;
- an unavailable or ambiguous anchor never authorizes local recovery;
- no reset/rollback operation is exposed by the adapter interface.

The fake backend is not durable hardware, a remote service, a production security boundary, or qualification evidence. Tests prove the coordinator-facing contract only. Provider-specific integration, independent administrative review, recovery ceremony, and real outage/restore drills remain mandatory.

## 6. Mandatory acceptance gates before a production adapter can be enabled

- Provider and separate administrative domain selected and threat-modelled.
- Atomic CAS and durability semantics independently verified from provider documentation and adversarial integration tests.
- Identity scoped to one anchor; no static long-lived credential in source, environment dumps, CI logs or mobile app.
- Multi-process race, restart, network partition, timeout-after-commit, stale replica, provider restore, deletion/recreation and revocation tests pass.
- Break-glass/bootstrap and recovery procedure reviewed by two independent humans.
- External audit checkpoint and alerting verified.
- Independent security review and owner approval recorded.
- Production adapter remains disabled until every gate is complete.

## 7. Safety locks

No production credentials, cloud account, paid service, HSM/TPM, production endpoint, owner key or live identity is used here. No deployment, merge, Global Owner activation, Worker/browser activation, host mutation or firewall change is authorized. PR #11 remains Draft/Open/Unmerged; Auto-Run OFF.


## 8. Implemented local fallback adapter (P47)

Added `core/local_owner_anchor.py` with `LocalSQLiteOwnerAnchor`. This concrete adapter supports local development, integration testing and single-host crash/restart exercises. It uses a separate SQLite file, mode 0600 on POSIX, rejects symlinks and broad permissions, refuses to silently initialize an existing empty/corrupt file, and uses `BEGIN IMMEDIATE` with `synchronous=FULL` for cross-process compare-and-advance.

Automated tests in `tests/test_local_owner_anchor.py` cover one-time bootstrap, corruption/missing-row fail-closed behavior, symlink and permission rejection, stale/jump rejection, and an eight-process CAS race where exactly one writer may advance.

**Explicit limit:** this local adapter is not independently administered and is vulnerable to privileged host rollback or restoration of an older file. It does not satisfy the production anti-rollback gate and must not be substituted for an external monotonic anchor in a production owner-recovery policy. It is a safe development fallback, not an automatic production fallback.


## 9. P51 mutual-TLS remote anchor client

Added `core/remote_owner_anchor.py` with `HTTPSMonotonicAnchor`, implementing both `MonotonicOwnerAnchor` and `MonotonicSequenceBackend` over an explicit mTLS API. It enforces HTTPS, trusted CA and hostname validation, TLS 1.2 minimum, optional server certificate SHA-256 pin, a private client-key file, bounded timeouts and payloads, strict JSON with duplicate-key rejection, exact one-step CAS, no redirects/bootstrap/reset, and fail-closed handling for ambiguous outcomes. The client returns success only when the service confirms the exact target state.

Tests in `tests/test_remote_owner_anchor.py` exercise reads, CAS success/conflict, malformed response, redirect rejection, TLS-key permissions, HTTPS-only configuration, invalid revision jumps and sequence operations.

**Boundary:** this is a production-shaped client adapter, not a running independent service. No service endpoint, certificate, separate account, administrative domain or provider has been selected/provisioned. The service must prove atomic CAS, durable acknowledgement, separate administration, non-rollback backup/restore, immutable audit receipts, identity revocation and failure behavior. TLS alone does not establish anti-rollback. P51 contract tests are not external-provider qualification.
