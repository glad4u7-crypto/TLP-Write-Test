# APAA S09 C01 — P17 to P19 delivery record

**Branch:** `feature/apaa-s09-c01-p16-oci-lifecycle`  
**Scope:** Proxy/worker topology, durable identity-bound inspector challenge, strict egress evidence parsing.  
**Status:** P17–P19 implementation and automated tests committed. The exact code head `b45383deb50613fd8780f5ad2f732ff0250a2ff2` passed both Agent Foundation CI and Python Demo CI (2026-11-16). A disposable Linux namespace qualification job has been added to CI; its result is pending on the new head. No production network or firewall was changed.

## P17 — Proxy/Worker topology

### Implemented
- `core/proxy_worker_topology.py` defines an immutable topology contract with a dedicated network name, RFC1918 IPv4 subnet, distinct proxy/worker addresses and one explicit unprivileged TCP proxy port.
- Worker proxy URL is fixed to the proxy's private network address (example only: `http://172.30.0.2:3128`); loopback, hostnames, wrong ports, credentials, paths and out-of-subnet endpoints are rejected.
- `core/egress_proxy.py` retains loopback-only binding by default. A non-loopback bind is permitted only when a validated `ProxyWorkerTopology` is supplied and the bind address, port and CONNECT allowlist exactly match it.
- Tests cover topology input rejection and topology-scoped proxy binding.

### Required deployment topology
```text
Internet
   ^ proxy-side outbound only (validated DNS + pinned upstream IP)
[ Egress Proxy ] 172.30.0.2:3128 / dedicated private network
   |
[ Worker ] 172.30.0.3
   X direct DNS / arbitrary TCP / UDP / QUIC / IPv6 / alternate NIC
```

The deployment MUST create a dedicated internal OCI network, publish no proxy host port, give the worker exactly one non-loopback interface, keep proxy management out-of-band, and enforce worker egress default DROP. The Python contract does not create or prove this network.

## P18 — Durable, identity-bound attestation

### Implemented and test coverage added
- `core/oci_worker_executor.py` refuses stateless attestation. A configured `InspectorEvidenceControlPlane` and validated `TenantKey` are mandatory for any successful start.
- After stopped-container inspection, the control plane issues a durable single-use challenge bound to the exact OCI container ID and planned worker name.
- Evidence is verified against the active trusted key registry, launch-spec digest, signed runtime facts, exact proxy IP/port firewall allowlist and challenge. The challenge is atomically consumed only after signature and identity checks pass.
- Executor independently checks the accepted evidence's runtime ID, worker ID and launch-spec digest against the inspected OCI plan before issuing START.
- Added `tests/test_oci_worker_executor_attestation.py`: successful attestation is required before START; bad signature blocks START and triggers removal.
- Existing `tests/test_inspector_control_plane.py` covers durable single-use challenges, replay, expired/revoked keys, wrong tenant, wrong runtime/worker identity, and rejection without burning the valid owner's challenge.
- Existing `tests/test_sqlite_security_store.py` covers challenge persistence after reopening, tenant/runtime/worker binding, expiry, raw-challenge hashing and concurrent single-winner consumption.

### Existing trusted components reused
- `core/inspector_control_plane.py`
- `core/sqlite_security_store.py` (filesystem-backed SQLite challenge issue/consume)
- `core/inspector_key_registry.py`
- `core/browser_inspector.py`

Key provisioning remains out-of-band. The SQLite database must be private to the control-plane principal and backed up/recovered according to the host operator's security policy. The control plane is not a substitute for an authenticated host collector.

## P19 — Strict egress and bypass rejection

### Implemented
- `core/browser_nftables.py` accepts only one inet table and one output base chain with policy DROP; unmodelled sets, elements, counters, maps or other nftables objects fail closed.
- Only exact TCP destination IP + TCP destination port allow rules are accepted; the complete allowlist must equal the configured proxy IP set and port.
- Negative tests cover direct HTTPS, direct DNS over TCP/UDP, DNS to proxy on port 53, UDP/443 QUIC, IPv6 egress and unmodelled nftables objects.
- Existing collector signs the ruleset digest, namespace inode, interface and runtime/worker identities; verifier checks signature and freshness.

## Verification and remaining qualification

- P18 executor integration tests and P19 strict nftables parser/collector tests are included in the repository test suites. Both repository workflows passed on exact code head `b45383deb50613fd8780f5ad2f732ff0250a2ff2`: Agent Foundation CI run `43794016584` and Python Demo CI run `43794016699`.
- Added `scripts/qualify_linux_egress_namespace.sh`, executed only on an ephemeral GitHub-hosted Ubuntu runner. It creates and removes its own network namespace and veth pair, installs a namespace-local nftables output chain with default DROP and one exact TCP proxy allow, verifies that the proxy endpoint works, and probes prohibited TCP/HTTPS, TCP/UDP DNS, UDP/443 and IPv6 against host-side sink sockets. It does not modify host firewall rules. CI result on the new head is pending.
- Still required: real Docker/Podman runtime compatibility; inspect runtime-created network and namespace configuration; verify host firewall hook precedence and production topology; test proxy upstream DNS rebinding and pinned-IP dial; exercise runtime cancellation and cleanup.
- No OCI container, network, firewall, browser or website was created/accessed in this implementation. No merge, deployment, payment, purchase, paid provider, API key or Auto-Run was used.

**Checkpoint decision:** P17/P18/P19 code and parser/unit-test layers are delivered. Disposable Linux kernel-level namespace qualification has been added to CI but is not complete until the new head's job passes. Full OCI runtime and host firewall integration, proxy DNS-rebinding/pinned-IP qualification remain pending. Live browser remains disabled.
