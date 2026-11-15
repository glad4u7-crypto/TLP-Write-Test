# APAA S07 — P09 Durable Inspector Challenge Replay Protection

**Checkpoint:** APAA-S07-C01-P09  
**Implementation:** `core/sqlite_security_store.py`  
**Tests:** `tests/test_sqlite_security_store.py`  
**Storage:** existing owner-only SQLite security database  
**CI:** PENDING exact P09 verification commit  
**Deployment / firewall / worker / browser:** NOT PERFORMED

## Objective

P09 adds durable, one-time challenges for signed host-inspector evidence. It reuses the existing SQLite security store and the existing two CI workflows; no new workflow, service, daemon or network listener is introduced.

## Challenge lifecycle

1. Trusted control-plane code supplies a validated `TenantKey`, trusted runtime ID and trusted worker ID.
2. `issue_inspector_challenge` generates a cryptographically random 256-bit lowercase-hex challenge and persists only its SHA-256 hash.
3. Challenge issuance is committed transactionally before the raw challenge is returned to the caller.
4. The caller supplies the challenge to the host collector. The host signs it as part of the P06 closed evidence envelope.
5. The control plane verifies the Ed25519 signature, trusted key ID, exact expected challenge, runtime attestation, freshness and firewall evidence using the existing stateless P06 verifier.
6. Only after all verification succeeds, trusted control-plane code calls `consume_inspector_challenge` with the same tenant, runtime ID and worker ID.
7. A conditional SQL UPDATE inside `BEGIN IMMEDIATE` marks the challenge consumed only if it exists, is unexpired, matches all bindings and has not previously been consumed.

The control plane must reject the evidence if challenge consumption returns false. It must never consume a challenge before signature and evidence verification.

## Security properties

- 256-bit random challenge generated with Python's `secrets` module.
- Database stores SHA-256 challenge hash, never the raw challenge.
- Bound to issuer + subject, runtime ID and worker ID.
- TTL constrained to 10–300 seconds (default 60 seconds).
- Expired challenge rejected.
- Conditional update and SQLite write transaction provide single-use semantics across concurrent processes sharing the same database.
- Reopening the store does not reset issued or consumed challenge state.
- Owner-only database and directory protections are inherited from the existing `SQLiteSecurityStore`.
- No evidence payload, private key, signature, credential or raw challenge is persisted.

## API contract

`issue_inspector_challenge(tenant, runtime_id=..., worker_id=..., ttl_seconds=60, now=None)` returns `(challenge, expires_at)`.

`consume_inspector_challenge(tenant, challenge, runtime_id=..., worker_id=..., now=None)` returns true only for the first valid consumption. Invalid, expired, mismatched or replayed challenges return false. Invalid tenant types raise `TypeError`.

## Test coverage

New deterministic tests cover:
- persistent issuance across store reopen;
- runtime, worker and tenant binding;
- expiration and invalid input rejection;
- concurrent duplicate consumption with exactly one winner;
- database stores only the challenge hash.

The existing P06 verifier remains stateless by design. This persistence primitive does not itself authenticate the caller or verify signatures. Those operations must occur in trusted control-plane code before consumption. SQLite is suitable only when the database path is protected and all control-plane instances share the same authoritative database. Multi-host deployments require a separately reviewed shared transactional store.

## Remaining gates

- Integrate verifier → challenge consume in one trusted control-plane request path; no handler is registered by this P09 storage change.
- Authenticate tenant and runtime/worker identity outside untrusted evidence.
- Independently review database backup/restore, clock synchronization, concurrent multi-process use and same-UID threat assumptions.
- Out-of-band Ed25519 private-key custody, public-key trust registry and rotation remain separate.
- Run P09 tests and both existing workflows on the exact verification-record commit.
- Live host, packet-level firewall and production acceptance remain unperformed.

**P09 disposition:** DURABLE HASH-ONLY CHALLENGE ISSUE/CONSUME STORAGE AND TESTS ADDED. CI AND TRUSTED CONTROL-PLANE INTEGRATION PENDING. No deployment, firewall modification, worker launch or browser activation.
