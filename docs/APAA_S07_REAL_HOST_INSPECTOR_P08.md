# APAA S07 — P08 Real Host Inspector Adapter + Secure Evidence Collection

**Checkpoint:** APAA-S07-C01-P08  
**Implementation:** core/linux_host_inspector.py  
**Tests:** tests/test_linux_host_inspector.py  
**Integration:** P07 HostSnapshotSource + P06 Ed25519 evidence verifier  
**Host deployment:** NOT PERFORMED  
**Live host collection:** NOT PERFORMED  
**Firewall changes:** NOT PERFORMED  
**Browser execution:** DISABLED

## 1. Objective

P08 supplies the first concrete Linux host-side adapter for the P07 read-only HostSnapshotSource boundary. It reads the target worker network-namespace identity and the effective nftables JSON ruleset from inside that namespace, then lets the existing P07 collector validate and sign the result using the existing P06 closed-schema Ed25519 evidence protocol.

This is an adapter implementation, not a deployed inspector daemon and not proof that a particular host or firewall is secure.

## 2. Read-only collection

LinuxHostInspectorAdapter requires:
- a runtime-attestation reader supplied by a separately trusted runtime integration;
- runtime ID and worker ID from that same trusted integration;
- the target container/runtime init PID supplied by the trusted integration;
- Linux procfs access to that PID's namespace metadata;
- fixed nsenter and nft executable paths.

It performs only these observations:
1. Reads the supplied runtime attestation mapping; P05 remains responsible for its closed-schema, launch-spec and freshness checks.
2. Reads /proc/<pid>/ns/net metadata to obtain the network namespace inode.
3. Reads /proc/<pid>/net/dev and requires exactly one non-loopback interface.
4. Runs one fixed, read-only command in the target network namespace:
   nsenter --target <trusted-pid> --net -- <fixed-nft-path> -j list ruleset
5. Returns the JSON snapshot to the P07 strict nftables parser.

The command is invoked as an argument array with shell=False, no stdin, a fixed minimal environment, closed file descriptors, a five-second timeout and a 1 MiB output ceiling. stderr is never returned to callers. No command, path, argument, environment variable or executable is accepted from the worker or from page content.

The namespace inode is captured before ruleset inspection and rechecked before and after the command. This detects ordinary PID/namespace replacement during collection. The runtime integration remains responsible for authenticating the PID-to-runtime mapping and for using a stable runtime identity.

## 3. Explicit non-capabilities

The adapter does not:
- call sudo, setuid, setcap, nsenter into user/mount/PID namespaces, or request additional privileges;
- create, start, stop, restart or delete a worker or process;
- change nftables, iptables, routes, DNS, interfaces, sysctls or firewall configuration;
- use a shell, execute arbitrary commands, open network sockets, resolve DNS or contact a remote service;
- read process command lines, environment variables, credentials, cookies, tokens, home directories or arbitrary host files;
- generate or provision signing keys, publish public keys, or rotate trust roots;
- issue or consume one-time challenges on behalf of the control plane.

If procfs, nsenter, nftables, namespace permissions, output bounds or schema checks fail, collection fails closed. The adapter does not fall back to host-global firewall state or weaker inspection.

## 4. Evidence and trust chain

The intended offline call sequence is:

1. Trusted runtime integration binds runtime ID, worker ID and PID.
2. LinuxHostInspectorAdapter reads namespace metadata and the effective namespace nftables ruleset.
3. P07 validates the runtime attestation, namespace identity and strict proxy-only nftables policy.
4. P07 assembles the exact P06 evidence schema and signs the canonical payload with the caller-supplied Ed25519 private key.
5. P06 verifies the emitted envelope against the matching public key before it is returned.

The private key must remain outside the worker and outside Git. Key provisioning and rotation remain out-of-band. The control plane must issue unpredictable 256-bit challenges, persistently consume each challenge exactly once, and reject replay. The current adapter does not implement key custody or challenge storage; these remain explicit release gates.

## 5. Tests and evidence semantics

The new tests use a synthetic procfs tree, temporary executable stubs and a mocked subprocess boundary. They verify:
- namespace inode and interface extraction;
- runtime-attestation reader injection;
- exact namespace-scoped nft read command and shell=False;
- timeout, nonzero exit, empty output and oversized output fail-closed behavior;
- invalid PID, missing fixed binaries and ambiguous interface state rejection.

These are deterministic adapter unit tests. They are not live host tests, packet-level firewall tests, proof of kernel enforcement, or evidence that an actual APAA worker namespace exists. P07's strict parser and P06's signature verifier remain separate validation layers.

## 6. Remaining production gates

- Independently review and authenticate the runtime integration that maps runtime/worker IDs to PID.
- Provision and rotate Ed25519 keys out-of-band; protect the signing key from the worker and control plane.
- Implement durable, atomic, one-time challenge issuance/consumption in the trusted control plane.
- Run the adapter on a dedicated Linux test host with a real isolated worker namespace under the intended unprivileged account.
- Verify namespace identity and nftables state against independent host observations.
- Perform packet-level tests for non-proxy egress, direct DNS, UDP/QUIC, IPv4/IPv6 and routing/forwarding escape paths.
- Independently review PID lifecycle/namespace race handling and host privilege boundaries.
- Keep deployment, firewall changes and browser activation behind separate explicit approval.

## 7. Existing safety invariants

- Auto-Run OFF; Ask First remains default.
- No payments, purchases, checkout, trading, investment orders or money movement.
- No paid API/provider, API key, automatic fallback or billable feature.
- No arbitrary shell, filesystem, credential, cookie, token, clipboard, email or Android device-control handler.
- No new CI workflow; use only the two existing workflows.
- PR #5 remains Open + Draft + unmerged.
- No deployment, firewall modification, worker launch or browser execution.

**P08 disposition:** CONCRETE READ-ONLY LINUX ADAPTER + DETERMINISTIC UNIT TESTS ADDED. LIVE HOST ACCEPTANCE, SIGNING-KEY CUSTODY, DURABLE CHALLENGE REPLAY PROTECTION AND PACKET-LEVEL ENFORCEMENT REMAIN OPEN.
