# APAA S09 C01 P41 — Provider Failure and Trust-Boundary Qualification

**Status:** synthetic adversarial tests and explicit limitation record  
**Production adapter:** NOT IMPLEMENTED  
**Owner recovery / execution integration:** NOT ENABLED

## Added tests

- Provider identity revocation between a successful read and conditional write. A permission failure must leave reconciliation denied and must not be interpreted as success.
- Stale-replica read-back after a conditional write reaches the authoritative primary. The coordinator must reject stale confirmation rather than claim success; a later authoritative read may establish CONSISTENT.

## Important anti-rollback limitation

The provider-neutral protocol cannot prove that the provider itself has not been restored to an older snapshot. In particular, a provider rollback of exactly one sequence can be observationally indistinguishable from the legitimate state "one local audit append committed, external checkpoint not yet advanced". The coordinator can reject multi-sequence gaps, provider-ahead states, same-sequence hash divergence, malformed responses and stale confirmations, but it cannot independently distinguish that one-step provider rollback.

Therefore the external provider must itself guarantee durable monotonic history across backup/restore, deletion/recreation and administrative recovery, or expose independently verifiable append-only receipts/history under a separate trust root. This guarantee requires provider-specific design, real integration tests, independent administration and external review. It is not established by the in-memory fake or these tests. Never claim the external checkpoint is production anti-rollback protection until this gate is qualified.

## Failure handling

- Revoked or unauthorized provider identity: fail closed; no local owner-state mutation.
- Stale or unavailable provider read: fail closed; do not accept a non-authoritative acknowledgement.
- Timeout after commit: exact authoritative read-back only; otherwise outcome remains unknown.
- External provider rollback or recreated state: cannot be proven safe by this generic contract; block production acceptance pending independently evidenced provider guarantees and recovery ceremony.

## Safety locks

PR #11 remains Draft/Open/Unmerged. Global Owner inactive. Auto-Run OFF. Worker/browser OFF. No deployment, merge, real credential, paid API, payment, production activation, host mutation, or firewall change.
