# APAA-S09-C01-P51 — Mutual-TLS independent monotonic anchor client

**Status:** client adapter and contract tests committed; exact-head CI pending.  
**Production service:** NOT SELECTED / NOT CONNECTED.  
**PR:** #11 Draft/Open/Unmerged.

## Delivered

Added `core/remote_owner_anchor.py` with `HTTPSMonotonicAnchor`, implementing both existing protocols:

- `MonotonicOwnerAnchor.read()` and `compare_and_advance()`.
- `MonotonicSequenceBackend.read_sequence()` and `advance_sequence()`.

Security controls:
- HTTPS only; no embedded URL credentials, query or fragment.
- Mutual TLS with a trusted CA, hostname verification, TLS 1.2 minimum and a client certificate/key.
- Optional exact SHA-256 server-certificate pin.
- Client private-key file must be a regular non-symlink file with POSIX 0600 or stricter permissions.
- Bounded 1–30 second timeout, bounded request/response sizes, strict JSON schema and duplicate-key rejection.
- No redirects, implicit bootstrap, reset, rollback or force-write operation.
- Only exact one-step revision/sequence transitions are accepted.
- HTTP 409 is a conflict, not success. Timeout/transport ambiguity raises a fail-closed error and requires an authoritative re-read before retry.
- Response must confirm the exact requested target before the adapter returns success.

Added `tests/test_remote_owner_anchor.py` for owner-state reads, exact CAS success, conflict handling, malformed responses, redirect rejection, TLS key permissions, HTTPS-only enforcement, invalid revision jumps and trust-sequence operations.

## Required external service API

The independent service must implement these endpoints with a single atomic conditional write and durable acknowledgement:

- `GET /v1/anchors/{id}` → `{"schema_version":1,"state":{"revision":N,"generation":...,"change_id":...}}`
- `POST /v1/anchors/{id}/compare-and-advance` with expected and target state → HTTP 200 only for exact durable success; HTTP 409 for a state conflict.
- `GET /v1/sequences/{issuer}` → current non-negative sequence.
- `POST /v1/sequences/{issuer}/compare-and-advance` with expected and next sequence → HTTP 200 only for exact durable success; HTTP 409 for conflict.

The service must enforce atomic CAS in its authoritative store, authenticate the client certificate to one narrowly scoped anchor identity, retain independent audit receipts, and never acknowledge before the provider's durability boundary.

## What this does and does not complete

This is a real client adapter that can connect to an independently hosted service; it is not a fake local SQLite fallback. However, no independent service endpoint, certificate, account, administrative domain or provider has been selected or provisioned. Mocked contract tests cannot prove the server's atomicity, durable commit, administrator separation, backup/restore anti-rollback, identity revocation or append-only audit history.

The service's own backup/restore and deletion/recreation behavior must be proven independently. A remote database is not automatically anti-rollback just because it is remote or uses TLS. Provider-side rollback, stale replicas and lost acknowledgements must be tested against the actual provider.

## Production acceptance gates still open

1. Select a free/owner-controlled or otherwise explicitly approved independent service; no paid service is presumed or enabled.
2. Deploy it under a separate administrative identity and backup/restore domain from APAA.
3. Provision mTLS client identity with least-privilege access to one anchor; pin CA/server identity out-of-band; test revocation.
4. Prove atomic CAS across multiple independent clients and restart.
5. Prove durability after process/host restart and timeout-after-commit.
6. Prove backup restore, deletion/recreation and disaster recovery cannot lower the high-water mark; use a separate immutable receipt/history or hardware monotonic root if required.
7. Run stale replica, network partition, rate-limit, identity revocation and provider outage drills.
8. Obtain independent security review and owner approval.

No provider has been selected or contacted by this change. No credentials, payment, paid API, deployment, firewall mutation or production host action occurred. C01 remains OPEN; C02 NOT STARTED.
