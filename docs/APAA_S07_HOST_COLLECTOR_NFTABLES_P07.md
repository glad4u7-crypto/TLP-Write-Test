# APAA S07 — P07 Read-only Host Snapshot Collector + nftables Parser

**Checkpoint:** `APAA-S07-C01-P07`  
**Implementation:** `core/browser_nftables.py`  
**Tests:** `tests/test_browser_nftables.py`  
**CI:** pending exact-commit verification  
**Host adapter / daemon:** NOT PROVIDED  
**Firewall changes / deployment:** NOT PERFORMED  
**Browser execution:** DISABLED

## 1. Objective

P07 adds a strict, offline parser for a narrow nftables JSON subset and an injected read-only collection boundary. The collector validates runtime attestation, namespace identity and firewall state, normalizes the observation into the P06 schema, signs it with a caller-supplied Ed25519 key, and self-verifies the envelope through the P06 verifier before returning it.

## 2. Read-only source boundary

`HostSnapshotSource` is a protocol with three explicit read methods:
- `read_runtime_attestation()`
- `read_network_namespace_identity()`
- `read_nftables_json()`

APAA supplies no concrete host adapter. No shell, subprocess, Docker/OCI API, kernel API, filesystem path, DNS resolver, socket, nft command or firewall mutation is used. The source must be separately reviewed and authenticated; it must read effective kernel/runtime state rather than echo desired configuration.

The caller supplies:
- an already-built P05 `WorkerLaunchSpec`;
- a one-time 256-bit challenge;
- a key ID and externally provisioned Ed25519 private key;
- exact proxy IP addresses from trusted deployment configuration.

Private key custody, public-key provisioning/rotation and one-time challenge consumption remain external.

## 3. nftables parser scope

The parser accepts only:
- JSON from `nft -j list ruleset`-style output;
- exactly one `inet` family `filter` base chain with hook `output`;
- default chain policy exactly `drop`;
- output rules containing exactly three equality matches (L4 protocol TCP, exact IPv4 destination, exact TCP destination port) followed by `accept`;
- the exact configured proxy IP set and approved proxy port, with no duplicates or additional output rules.

It rejects default accept, multiple output base chains, unsupported expressions, jumps, verdict maps, UDP, alternate ports, CIDR/wildcard destinations, extra proxy destinations and unknown output rules. It computes a SHA-256 digest over canonicalized JSON.

This intentionally narrow parser is not a general nftables interpreter. It does not prove the kernel is enforcing the supplied snapshot, inspect packet counters, validate routing, inspect host-level forwarding chains, or prove there is no alternate network path. Unsupported nftables syntax must fail closed pending explicit reviewed support.

## 4. Evidence assembly

The collector:
1. obtains runtime attestation from the injected source and revalidates it with P05;
2. checks runtime ID, worker ID, namespace inode and interface identity;
3. parses the supplied nftables JSON against the exact proxy IP/port allowlist;
4. builds the P06 firewall evidence schema and ruleset digest;
5. signs the complete canonical payload using the supplied Ed25519 key;
6. verifies the generated envelope against the matching public key using P06 before returning.

Collection time is supplied by the caller or system clock. Challenge freshness and one-time consumption are still caller responsibilities. The collector cannot independently authenticate the source or signing key.

## 5. Tests

Offline tests cover:
- valid exact-proxy output chain and canonical digest;
- default accept and multiple output base chains;
- extra output destination, UDP, wrong port, wildcard/CIDR and unsupported/jump expressions;
- wrong expected proxy IP/port;
- valid signed evidence round-trip through P06 verifier;
- runtime/worker namespace mismatch and invalid firewall snapshot;
- invalid source and challenge;
- no host command or live network operation.

## 6. Trust and production gate

P07 delivers a reusable collection protocol and deterministic parser, not a live host inspector. A production adapter still needs independent security review, rootless/read-only operation where feasible, namespace-bound reads, atomic snapshot acquisition, signer isolation, challenge replay storage, key rotation, packet-level egress/DNS leak tests, and host-side verification that the nftables snapshot corresponds to the actual worker namespace at the time of launch.

No browser process or worker is started. No runtime deployment adapter, host daemon, firewall command, firewall mutation, network request, DNS lookup, socket or ExecutionGateway browser handler is introduced.

## 7. Existing safety invariants

- Auto-Run OFF; Ask First remains default.
- No payments, purchases, checkout, trading, investment orders or money movement.
- No paid API/provider, API key or billable feature.
- No arbitrary shell, filesystem, credential, cookie, token, clipboard, email or Android device control.
- No new CI workflow; strengthen the two existing workflows.
- PR #5 remains Open + Draft + unmerged. No merge or deployment.

**P07 disposition:** READ-ONLY SOURCE PROTOCOL + STRICT NFTABLES JSON PARSER + SIGNED EVIDENCE ASSEMBLER IMPLEMENTED. Concrete host adapter and live enforcement remain NOT IMPLEMENTED.
