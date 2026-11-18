# APAA-P74-ACTION-12 — OCI Runtime and Network Provisioner

## Status

Repository implementation is in progress. **Real-host qualification was attempted twice (runs #427 and #430); both failed during Chromium startup with an FD ownership violation. This is NOT a PASS.** Public Live Browsing, browser worker dispatch, and automatic execution remain disabled. Mocked unit tests and GitHub-hosted CI are not evidence of host-level network isolation.

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
- `.github/workflows/p74-real-worker.yml`: gated qualification on a disposable
  GitHub-hosted Linux VM. The owner-authorized reserved public fixture is
  `https://example.com/` with exact origin `https://example.com` and marker
  `Example Domain`; no privately owned domain is required. A push commit must
  contain `[run-p74-real-worker]` to start the qualification. It uploads a
  sanitized evidence artifact and does not enable product browsing.
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

1. The disposable-host workflow has been executed twice with the owner-approved
   public read-only fixture `https://example.com/`, exact origin
   `https://example.com`, and marker `Example Domain` (runs #427 and #430 below).
   Both reached real Chromium execution but failed with the same FD ownership
   violation. This gate remains OPEN. A future run can be triggered by a push
   commit containing `[run-p74-real-worker]`; ordinary pushes skip it.
   `workflow_dispatch` becomes available after the workflow exists on the
   default branch. Each run creates a disposable GitHub-hosted Linux VM,
   installs Podman/iproute2/nftables, builds the Chromium worker image and
   requires a dedicated delegated cgroup subtree.
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


## Observed real-host qualification attempts — 2026-11-18

- **Run #427 / ID `44238475405`** — exact head `618c0fed421d72ede0a8306bb971e2c950605865`. Evidence artifact ID `14398771572`, SHA-256 `1b3ae08658484acbdbee8cab26117c5425cbfc302ae06fd152de07c32e5c577e`.
- **Run #430 / ID `44239047832`** — exact head `2fc720b56d2f05dde8590794572f3e85c13ddc32`. Evidence artifact ID `14399066537`, SHA-256 `9ff0ec51552d69a4ad6bc1650961711c2d267172e0a9559ab5adc4ae7bbfb3bf`.
- Both runs passed disposable-host dependency installation, cgroup-v2 preparation, worker image build and seccomp-profile preparation. Both failed in the local Chromium dump-DOM smoke test with `Crashing due to FD ownership violation` and a network-service restart; stdout was empty.
- Run #427 captured 153 snapshots (10 marker-triggered); run #430 captured 155 (9 marker-triggered). Both had zero collector errors and confirmed cleanup with no cleanup errors.
- Exact Debian Chromium build ID `4a74f6497529d42bb61262c76d7b1add49c4dea6` was matched and symbolicated. The log PID (container PID 20) did not prove the process that owned the mapped stack; the stack-mapped candidate was a separate child (container PID 280 in #427, 279 in #430). Mapping confidence remains partial.
- Neither run had the diagnostic patch compiled into its Chromium binary, so neither recorded the exact FD number or whether the violation was an acquire, release, or raw close. The bounded collector has since been updated to retain only safe argv0/process-type/utility-subtype metadata; its targeted tests pass. A third full host run and a full Chromium source build are intentionally not being launched automatically to avoid additional CI budget consumption.
- Current verification on latest code head `c13ad30cb103bd80051fabbe6d0caf83b5d5df32`: P74 diagnostic tests #26 / ID `44239625919` **SUCCESS**; P93 pinned-source patch/parser validation #99 / ID `44239625923` **SUCCESS**; APAA Security CI #1381 / ID `44239626347` **SUCCESS**. These do not establish a Chromium-native fix or a passing OCI run.

The host qualification gate remains OPEN. Do not weaken sandbox settings to obtain a green run.
