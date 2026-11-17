# APAA S07 — Trusted Inspector Evidence Control-Plane Integration

**Checkpoint:** APAA-S07-C01-P11  
**Implementation:** `core/inspector_control_plane.py`  
**Tests:** `tests/test_inspector_control_plane.py`  
**Prerequisites:** P06 signed evidence verifier, P09 durable challenge store, P10 public-key trust registry  
**CI:** pending exact integration verification commit  
**Execution side effects:** none; offline control-plane composition only

## Flow

1. An already authenticated caller supplies a validated `TenantKey` and trusted runtime/worker identifiers.
2. `issue_challenge` persists a cryptographically random 256-bit challenge, bound to tenant, runtime and worker, before returning it.
3. The trusted host inspector returns an Ed25519-signed envelope containing that challenge, runtime attestation and firewall observation.
4. The control plane resolves the envelope key ID against the active P10 public-key registry snapshot.
5. P06 validates envelope schema, signature, challenge equality, P05 runtime attestation, evidence freshness and exact proxy-only nftables allowlist.
6. The control plane independently compares attested runtime/worker IDs to trusted expected IDs.
7. Only after every cryptographic and semantic check succeeds does P09 atomically consume the challenge for the same tenant/runtime/worker.
8. Unknown, expired, mismatched or replayed challenges fail closed.

## Security properties and deliberate boundaries

- Signature verification precedes durable challenge consumption.
- Failed signature, revoked/expired key, stale evidence, wrong tenant, identity mismatch or firewall-policy mismatch cannot consume the challenge.
- Concurrent replay is delegated to P09's atomic conditional update; at most one caller can win.
- Tenant authentication, launch-spec provenance, expected identity provenance and proxy-IP configuration are caller responsibilities and must be supplied by trusted control-plane state.
- The P10 registry input must originate from independently authenticated out-of-band configuration; this integration does not bootstrap trust.
- This module does not create private keys, sign evidence, read credentials, collect host state, spawn processes, open sockets, resolve DNS, change firewall rules, start workers, activate browsers or deploy services.
- The local SQLite store is a single-host durable primitive. This does not claim distributed/multi-host replay safety.
- Accepted evidence is returned to the caller; no new network endpoint or automatic browser permission is granted.

## Tests

Offline tests cover successful one-time acceptance, replay rejection, invalid signature without challenge consumption, revoked and expired signing keys, wrong tenant, runtime/worker identity mismatch, and expired challenges.

## Remaining release gates

1. Authenticate caller principal and source launch spec, expected runtime/worker IDs and proxy IPs from trusted control-plane state.
2. Integrate with an audited request handler and define authorization policy for what accepted evidence permits.
3. Establish out-of-band key custody, dual-control rotation/revocation governance and registry distribution.
4. Establish independent host-side runtime ID/worker ID-to-PID attestation.
5. Run dedicated Linux live-host acceptance and independent packet-level escape-path tests (IPv4/IPv6, DNS, UDP/QUIC, routing/forwarding).
6. Independently review SQLite deployment location, backup/restore, file permissions, process model and recovery behavior.

**P11 disposition:** OFFLINE CONTROL-PLANE COMPOSITION ADDED. It is not a production service, does not independently authenticate its caller, and does not authorize worker execution. No deployment, firewall mutation, worker launch or browser activation.
