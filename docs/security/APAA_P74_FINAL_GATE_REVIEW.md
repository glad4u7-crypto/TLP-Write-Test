# APAA P74 Final-Gate Review Packet

**Date:** 2026-11-18  
**Scope:** PR #14 — OCI runtime, host inspector, and worker integration  
**Review type:** Internal adversarial engineering review; **not** an independent external security review.  
**Release state:** NO-GO. Browser/Worker dispatch OFF. Auto-Run OFF.

## Executive result

The exact-head APAA Security CI for commit `44031533331d7152734e263d960b9ee49aa828b7` passed in run #1322 / ID `44236702192`. This run includes syntax, Chromium TLS, controller policy/lifecycle, worker attestation/lifecycle contract, Linux host-inspector contract, and the remaining security suite. This verifies the checked-in contract tests, not the production isolation boundary.

The gated real-host Chromium qualification failed in run `44144480688`: Chromium reported an FD ownership violation and timed out. This remains a release blocker. The run's recorded preparation and cleanup success do not turn the browser execution failure into a pass.

The current PR contains useful components — a Podman lifecycle primitive, network namespace/firewall provisioners, a signed nftables policy parser, a Linux procfs/nftables snapshot source, and an attested worker adapter contract — but these pieces are not yet wired into one concrete, production-trusted `IsolatedWorkerBackend` and authenticated runtime observation provider.

## Findings

### F-01 — Production OCI backend is not implemented (Critical)

`AttestedBrowserWorkerAdapter` requires a trusted backend implementing `provision`, `snapshot_source`, `start_worker`, and `destroy_worker`. The current `PodmanOCIRuntime` is a lifecycle primitive only. It creates a container with an inert `sleep infinity` entrypoint, but does not implement the worker protocol, browser process control, job transport, or confirmed end-to-end worker lifecycle.

**Required closure:** implement a concrete backend with a narrowly scoped, reviewed control protocol; bind every operation to the immutable container ID and session; launch Chromium only after signed pre-start evidence verifies; terminate and destroy with independently confirmed exit and storage cleanup. Do not use a fake backend as production evidence.

### F-02 — OCI launch settings are not yet proven to match WorkerLaunchSpec (High)

The launch contract requires user, PID, network, IPC, UTS, and mount namespace isolation and carries UID/GID, writable mounts, CPU, memory, PID, seccomp, and network policy. The current OCI spec has a fixed `65532:65532` user and a network namespace path, while the launch command does not explicitly bind all six namespace requirements to the contract or read back every effective setting.

**Required closure:** define a single validated translation from `WorkerLaunchSpec` to OCI configuration; reject unsupported fields rather than silently ignoring them; explicitly configure and inspect namespace modes, UID/GID, mount policy, resource limits, seccomp, capabilities, read-only root, and no-new-privileges before accepting the worker handle.

### F-03 — Trusted runtime observation provider is a contract, not a production provider (Critical)

`LinuxHostSnapshotSource` depends on `LinuxRuntimeObservationProvider`. The protocol itself does not authenticate the runtime or prove that the supplied PID/container identity came from the trusted OCI runtime. The current tests use a fake provider and synthetic attestation data.

**Required closure:** implement an owner-controlled Podman/runtime API observer that obtains the immutable container ID, runtime state, host PID, image digest, namespace/cgroup identity and effective config directly from the runtime; bind PID start-time and container identity; reject ambiguous or stale observations. Protect the observer channel and signing-key custody separately.

### F-04 — Host inspector evidence requires real-host authentication and capability validation (High)

The signed inspector parser validates a strict dual-stack nftables policy, but the signature only authenticates the injected snapshot after collection. A production source must prove it queried the intended worker namespace and had sufficient authority to read the effective ruleset. A successful fake-source test does not establish those properties.

**Required closure:** on a disposable Linux host, prove the runtime provider, PID/starttime binding, namespace inode, interface, and exact effective nftables JSON all refer to the same worker. Demonstrate the collector fails closed when privileges, tools, namespace entry, or ruleset visibility are missing.

### F-05 — PID reuse race during namespace snapshot (Medium; software fix added)

The previous `LinuxHostSnapshotSource._network_namespace` checked process start-time before reading namespace inode and interface data, but did not re-check it after those reads. A PID could theoretically be recycled during snapshot collection.

**Change:** re-check `/proc/<pid>/stat` start-time after reading namespace/interface data; discard the snapshot if identity changed. Added a regression test that simulates PID reuse between the two reads.

Commits:
- `8ac633fa48dcd5b05c599d2fc02b64d532e360ca` — collector race fix
- `e70046da26c05fb5729bc6a4743d4c53903ce152` — regression test

### F-06 — URL authority and resolver validation (Closed by exact-head CI)

The navigation policy now rejects an explicit empty URL port (for example, `https://example.com:/`) and validates resolver output before tuple conversion, preventing a bare string from being treated as a sequence of address characters.

Commit: `44031533331d7152734e263d960b9ee49aa828b7`  
Exact-head APAA Security CI: run #1322 / `44236702192` — **SUCCESS**.

## OCI qualification status

- Last recorded disposable-host run: `44144480688` — **FAILED** during Chromium execution (FD ownership violation / worker timeout).
- No root cause is established by this report.
- No Chromium-native compiled regression test has yet demonstrated the failure and the fix.
- Owner has now approved proceeding with a disposable-host OCI qualification in this conversation. The workflow requires an exact HTTPS test URL and matching allowed origin on an owner-approved test origin; that origin must be confirmed before dispatch.
- Do not weaken sandbox, FD ownership, seccomp, namespace, cgroup, or default-DROP network controls to obtain a green run.

## Independent review checklist

An independent reviewer (not the author/implementer of these changes) must receive the exact PR head, threat model, OCI workflow logs, sanitized artifacts, and the following questions:

1. Can any browser process start before the signed runtime/firewall evidence is verified?
2. Can a PID/container/namespace identity be confused or recycled across collection?
3. Can a worker reach direct IPv4/IPv6, UDP/TCP DNS, or arbitrary egress outside the pinned proxy?
4. Can host paths, secrets, CDP, control sockets, or persistent browser profiles become reachable?
5. Are all namespace, UID/GID, cgroup, seccomp, capability, mount and resource controls enforced and read back from the runtime?
6. Do cancellation, timeout, crash, restart, partial create, and cleanup failure all fail closed?
7. Does the FD failure reproduce on the exact Chromium build, and does a compiled native regression fail before / pass after the fix?
8. Is the evidence chain fresh, replay-resistant, authenticated, and bound to the exact immutable worker?

Required outcome: written findings, severity, remediation references, reviewer identity/role, reviewed commit SHA, and explicit approval or rejection. A self-review or automated CI result is not a substitute.

## Release gates — all must pass

- [ ] Concrete production `IsolatedWorkerBackend` implemented and independently reviewed.
- [ ] Authenticated runtime observation provider implemented and independently reviewed.
- [ ] OCI launch settings proven to match `WorkerLaunchSpec` by runtime readback.
- [x] Latest exact-head Python/security CI passes, including the URL-policy fix.
- [ ] Chromium FD ownership root cause identified from exact-build evidence.
- [ ] Chromium-native compiled regression test passes after the fix.
- [ ] Complete gated disposable-host OCI Chromium qualification passes, including hostile-network, timeout, crash and cleanup tests.
- [ ] Sanitized evidence artifact reviewed and hash recorded.
- [ ] Independent external security review completed with no unresolved critical/high findings.
- [ ] Explicit Owner acceptance recorded before any dispatch enablement.

**Until every gate is closed:** keep Browser/Worker dispatch disabled, Auto-Run OFF, PR Draft/Open/Unmerged, and do not deploy.
