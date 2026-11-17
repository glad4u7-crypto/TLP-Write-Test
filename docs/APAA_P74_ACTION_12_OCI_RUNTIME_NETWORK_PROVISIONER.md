# APAA-P74-ACTION-12 — OCI Runtime and Network Provisioner

## Status

Repository implementation is in progress. **Real-host qualification is NOT RUN**.
Public Live Browsing, browser worker dispatch, and automatic execution remain
disabled. Mocked unit tests and GitHub-hosted CI are not evidence of host-level
network isolation.

## Implemented in this checkpoint branch

- `core/oci_runtime_backend.py`: argv-only Podman CREATE/INSPECT/START/STOP/REMOVE;
  digest-pinned image only, immutable 64-hex container IDs, no shell, no pull,
  read-only root filesystem, all capabilities dropped, no-new-privileges,
  explicit seccomp profile, non-root UID, memory/CPU/PID limits, and a required
  pre-created network namespace.
- `core/linux_network_namespace.py`: explicit privileged Linux network
  namespace + veth pair + IPv4/IPv6 address and default-route provisioning,
  with fail-closed rollback on setup errors.
- `core/nftables_firewall_provisioner.py`: per-namespace nftables input/output
  policies default to DROP; only explicitly supplied proxy IPs and one TCP port
  are allowed. Direct DNS, UDP/443/QUIC, and arbitrary destinations are not
  allowed. IPv6 neighbour discovery is limited to link-local control traffic.
- `core/cgroup_seccomp_provisioner.py`: cgroup-v2 memory/CPU/PID limit writer
  and read-back verification; strict seccomp profile preflight requires a
  deny-by-default action.
- `core/pinned_egress.py`: validates canonical DNS records and the complete
  IPv4/IPv6 answer set, then dials only a selected numeric IP; no second DNS
  lookup or hostname fallback is possible.
- `core/pinned_connect_proxy.py`: a bounded CONNECT proxy permits only the
  configured exact HTTPS hostname on port 443. It preserves Chromium's
  end-to-end TLS SNI/certificate validation while pinning the proxy's upstream
  TCP connection to one validated numeric DNS answer.
- `scripts/p74_real_worker_chromium_e2e.py`: provisions a fresh dual-stack
  namespace/veth, exact nftables policy, delegated cgroup parent and OCI
  container; runs real Chromium through both IPv4 and IPv6 proxy listeners;
  probes direct DNS/IPv4/IPv6 bypass; and attempts full resource cleanup.
- `containers/chromium-worker/Containerfile`: builds the disposable Chromium
  worker image. Its final local image ID is passed to OCI as an immutable
  `sha256:` identifier with `--pull=never`.
- `.github/workflows/p74-real-worker.yml`: manual-only qualification on a
  disposable GitHub-hosted Linux VM. It requires an owner-supplied exact HTTPS
  test URL and origin, builds the worker image, and uploads a short-retention
  evidence artifact. It does not enable product browsing.
- Focused unit tests exercise command construction, invalid inputs, rollback,
  default-DROP rules, mixed public/private DNS answers, IPv4/IPv6 pins and
  numeric-IP dialing.

## Important integration boundary

The qualification script is an opt-in host-side integration harness, not the
production browser-worker backend and not permission to dispatch user browsing.
The cgroup-v2 helper requires a host-provided delegated subtree and has not
been qualified against the target host's systemd/cgroup delegation. Podman
also applies the requested cgroup limits itself; inspect/read-back evidence
must confirm the effective limits. Seccomp profile compatibility with the
actual Chromium build remains unverified.

The firewall rules are installed inside the worker network namespace. The
approved proxy must be bound to the host-side veth address and must enforce
destination DNS/IP pinning itself. Host routing, proxy binding, IPv4/IPv6
forwarding, neighbour discovery, nftables hook precedence and alternate
interface bypass still require sink-side verification on the real host.

## Required real-host acceptance — all are mandatory

1. Run the manual `APAA P74 real OCI Chromium worker` workflow with an
   owner-approved HTTPS test URL, exact origin and unique expected HTML marker.
   The workflow defaults to the reserved `https://example.com/` documentation
   page with marker `Example Domain`; the owner may override these inputs.
   Before merge, its push-triggered job runs only when the commit message
   contains the explicit marker `[run-p74-real-worker]`. Ordinary pushes skip
   the host qualification. The automated repository-file commits used during
   this work did not dispatch that new workflow; a user-authored push to this
   branch is required for pre-merge execution (example commit message:
   `run(APAA P74): execute isolated worker [run-p74-real-worker]`). The
   `workflow_dispatch` path becomes available after this workflow exists on
   the default branch. It creates a disposable
   GitHub-hosted Linux VM, installs Podman/iproute2/nftables, builds the
   Chromium worker image and requires a dedicated delegated cgroup subtree.
2. Provision namespace and veth; prove the worker has no route outside the
   approved proxy path. Confirm both IPv4 and IPv6.
3. Install nftables and capture `nft list ruleset` from the namespace and host.
   Verify default DROP and only the exact proxy IP/port rule. Test direct DNS
   TCP/UDP, arbitrary TCP, UDP/443, QUIC, WebSocket, loopback, alternate
   interfaces and IPv4/IPv6 bypass attempts from the worker.
4. Create the container with the pinned image and namespace. Inspect the
   immutable container ID and verify read-only rootfs, non-root user, dropped
   capabilities, no-new-privileges, seccomp profile, memory, CPU, PID limits,
   and actual cgroup membership before permitting browser work.
5. Run Chromium **inside that container** against the exact owner-approved
   HTTPS test origin through both IPv4 and IPv6 proxy listeners. The script
   verifies allowed-page success, direct DNS failure, direct IPv4/IPv6 TCP
   failure, DNS answer-set validation and numeric dial peer equality. A
   separate Chromium TLS suite verifies trusted CA, hostname mismatch and
   expired-certificate behavior.
6. Kill the runtime/proxy during traffic; verify fail-closed behavior, bounded
   cleanup, no orphan container, no orphan namespace, no stale veth and no
   residual cgroup.
7. Preserve command outputs, immutable image digest, runtime version, kernel
   version, nftables ruleset, cgroup read-backs, sink-side packet evidence,
   Chromium logs, cleanup evidence and exact source commit SHA. Redact secrets.
8. Independent review of the exact evidence and explicit owner acceptance.

## Stop conditions

Any missing capability, unavailable cgroup controller, nftables error, DNS
ambiguity, unexpected route, missing IPv6 control, seccomp mismatch, container
inspect mismatch, proxy failure, timeout, orphan resource or evidence gap
must block worker startup and keep Public Live Browsing disabled.

No merge, deployment, host firewall mutation on a non-disposable host, paid
provider, API key, purchase/payment, or Auto-Run is authorized by this work.


## Production integration boundary (not yet enabled)

The real-host script is a disposable qualification harness. It creates and runs a
real Chromium process inside a Podman OCI container, but it is not yet injected
as the production `IsolatedWorkerBackend` for
`AttestedBrowserWorkerAdapter`. The existing adapter remains fail-closed and
requires a separately trusted backend and Ed25519 host-attestor key.

The earlier host-inspector JSON parser currently accepts a narrower nftables
output-rule grammar than this new dual-stack ruleset (loopback, IPv6 neighbour
discovery, and proxy-scoped established-state rules). Before production wiring,
the signed host-inspector parser/provider must be extended and tested against
the exact live `nft -j list ruleset` output. Do not synthesize attestation
fields from the launch request or use the text verifier as a substitute for
signed host evidence.

Accordingly, passing the manual worker qualification will be necessary but
not sufficient to enable Public Live Browsing. Production adapter integration,
key provisioning/rotation, challenge replay protection, and full lifecycle
recovery must also pass independently.


## Remaining production-gate sequence

1. Run the gated real-host Chromium qualification and retain the JSON evidence artifact.
2. Extend the signed host-inspector nftables JSON parser to attest this exact dual-stack policy, including loopback and narrowly scoped IPv6 neighbour discovery, while rejecting every other ACCEPT path.
3. Implement a trusted Podman runtime observation provider that independently reads inspect data, process start-time/PID identity, namespace inode, cgroup membership and live nftables JSON.
4. Implement the production `IsolatedWorkerBackend` adapter and align its UID/GID, memory, CPU, PID, writable-mount and proxy settings exactly with `WorkerLaunchSpec`; do not hardcode a second independent profile.
5. Bind host-attestor key provisioning, one-time challenge consumption, evidence freshness and cleanup/recovery to the owner-controlled control plane.
6. Re-run the complete hostile-network, TLS, crash, timeout, orphan and cleanup matrix. Only then consider enabling any browser dispatch, with a separate explicit owner approval.
