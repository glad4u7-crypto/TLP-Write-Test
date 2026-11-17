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
- `core/pinned_egress.py`: validates the complete DNS answer set and dials only
  a selected numeric IP from that set; it does not resolve the hostname again.
  The caller must preserve the original hostname for TLS SNI/certificate checks.
- Focused unit tests exercise command construction, invalid inputs, rollback,
  default-DROP rules, mixed public/private DNS answers, IPv4/IPv6 pins and
  numeric-IP dialing.

## Important integration boundary

The modules are not yet composed into one worker provisioning transaction.
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

1. Disposable Linux host with cgroup v2, Podman/OCI runtime, iproute2, nftables,
   Chromium image available locally by immutable sha256 digest, and a dedicated
   delegated cgroup subtree.
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
5. Run Chromium **inside that container** against a controlled test origin
   through the approved proxy. Verify TLS certificate/hostname validation,
   allowed destination success, blocked destination failure, DNS rebinding
   rejection, dial-time IP equality, and that no direct socket escapes.
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
