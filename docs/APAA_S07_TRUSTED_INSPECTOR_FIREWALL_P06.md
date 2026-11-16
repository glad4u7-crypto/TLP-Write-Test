# APAA S07 — P06 Trusted Inspector Signature and Host Firewall Evidence

**Checkpoint:** APAA-S07-C01-P06  
**Implementation:** `core/browser_inspector.py`  
**Tests:** `tests/test_browser_inspector.py`  
**Dependency:** `cryptography>=50,<51` (Ed25519 verification only)  
**Worker deployment:** NOT PERFORMED  
**Host inspector collector:** NOT IMPLEMENTED  
**Firewall changes:** NOT PERFORMED  
**Browser execution:** DISABLED

## 1. Objective

P06 establishes a signed evidence protocol between a future trusted host-side inspector and the APAA control plane. It strengthens P05's offline runtime-attestation checks with Ed25519 authenticity verification and an exact, signed nftables egress snapshot.

The control plane must receive the evidence and challenge from a separately trusted source. It must never accept evidence authored by the worker being inspected.

## 2. Signed evidence protocol

The envelope is closed-schema:

- `schema_version`: protocol version 1
- `key_id`: identifier in the out-of-band trusted public-key registry
- `payload.challenge`: 256-bit caller-generated challenge
- `payload.runtime_attestation`: complete P05 pre-start attestation
- `payload.firewall`: normalized host-side nftables observation
- `signature`: base64 Ed25519 signature over canonical JSON containing schema version, key ID and the complete payload

Canonical serialization uses sorted keys, compact separators, ASCII escaping and rejects NaN/Infinity. Unknown and missing fields are rejected at each envelope, payload, firewall and rule level. Ed25519 signatures are verified using a trusted 32-byte public key; the private signing key must remain outside the worker and outside the repository.

## 3. Host firewall evidence checked

The signed firewall observation must contain:

- runtime ID and worker ID matching the P05 attestation;
- positive network-namespace inode and a bounded interface name;
- reviewed backend identifier `nftables`;
- default egress policy exactly `drop`;
- direct DNS egress blocked and proxy-side DNS only;
- fresh observation timestamp;
- SHA-256 digest of the observed effective ruleset;
- an explicit egress allowlist consisting of exactly the externally configured proxy IP address(es), TCP only, on the approved proxy port.

Wildcard/CIDR destinations, extra internet destinations, UDP/QUIC, DNS ports, alternate ports, wrong proxy addresses, duplicate or malformed rules are rejected. The verifier does not resolve the proxy hostname: expected proxy IPs must be supplied by trusted deployment configuration and the firewall snapshot must match those exact IPs.

## 4. Freshness and replay boundary

The caller supplies a fresh 256-bit challenge and the verifier requires an exact match. The challenge is signed together with the complete evidence. The verifier is intentionally stateless: the caller/control plane must generate unpredictable one-time challenges and atomically mark them consumed after successful verification. It must reject reused challenges outside this function.

Evidence timestamps are independently checked for runtime and firewall observations, with a default 60-second maximum age and a small future-clock tolerance.

## 5. Tests

Offline tests cover:
- valid Ed25519 signed evidence;
- unknown/malformed trust keys and signature corruption;
- payload tampering and challenge mismatch;
- missing/unknown envelope and nested fields;
- default-accept firewall policy, wrong backend, direct DNS allowance and stale/future observations;
- extra internet egress, UDP, wrong port, wildcard/CIDR, wrong proxy IP;
- runtime/worker identity mismatch and invalid namespace metadata;
- duplicate and unsafe expected proxy addresses;
- no socket, DNS or process side effects.

## 6. Explicit trust limitations

This package verifies the authenticity and internal consistency of a signed report. It does **not** implement the host-side collector that reads the kernel, runtime, namespace inode, nftables ruleset or packet counters. It does not parse live `nft list ruleset` output, configure nftables, inspect effective packets, verify routing, or independently prove that the signer is uncompromised.

A valid signature means only that the matching private key signed the report. Operational trust still requires:
1. public keys provisioned and rotated out-of-band;
2. private key held by a hardened host inspector, never mounted into the worker;
3. collector independently reads the effective namespace and firewall state, not merely desired configuration;
4. collector hashes the actual effective ruleset and signs the normalized observation;
5. challenge generation and one-time consumption are enforced by the control plane;
6. independent packet-level tests prove all non-proxy egress and direct DNS are blocked;
7. the firewall observation is refreshed immediately before any separately authorized worker start.

No runtime API, shell command, root operation, network request, DNS lookup, socket, firewall mutation, browser binary, worker process, Playwright dependency or ExecutionGateway handler was introduced.

## 7. Security invariants retained

- Auto-Run OFF; Ask First remains the default.
- No payment, purchase, checkout, trading, investment order or money movement.
- No paid provider, API key, billable service or automatic fallback.
- No arbitrary shell, filesystem, credential, cookie, token, clipboard, email or Android device control.
- No browser handler registered; browser execution remains disabled.
- Existing CI workflows only; no new workflow.
- PR #5 remains Open + Draft + unmerged. No merge or deployment.

**P06 disposition:** SIGNED EVIDENCE VERIFIER + OFFLINE FIREWALL POLICY VALIDATOR IMPLEMENTED. Host collector, live firewall inspection and packet-level enforcement remain NOT IMPLEMENTED.
