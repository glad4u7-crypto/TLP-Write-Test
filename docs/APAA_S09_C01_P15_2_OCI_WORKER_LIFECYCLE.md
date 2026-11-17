# APAA S09 C01 P15.2 — Two-Phase OCI Worker Lifecycle

## Delivered and CI verified

- `core/oci_worker_lifecycle.py` adds an explicit stateful lifecycle:
  `NEW → CREATED → INSPECTED → ATTESTED → RUNNING → STOPPED → REMOVED`.
- The command runner and signed-evidence provider are mandatory injected ports. There is no subprocess import, shell execution, default runner, or automatic host integration.
- The only start path is the callback supplied to `AttestedBrowserRuntime`. It checks the exact launch-spec digest and verified evidence's `created` state before invoking start argv.
- Failed create/inspect/evidence/start operations fail closed and attempt cleanup. If start was attempted, cleanup attempts stop and then remove; removal is attempted even when stop fails.
- Cleanup is idempotent after successful removal. A lifecycle instance is one-shot; callers must create a new lifecycle for a new job.
- `abort()` is the explicit cancellation/timeout/proxy-outage hook and triggers cleanup.
- The lifecycle and worker-adapter tests pass in GitHub Actions run #833 at exact branch head `56f6b6440df9b9891be1595386b5d7785dfe49e4`.

## Required external integration contract — not yet delivered

A future production adapter must still provide all of the following outside this module:

1. A reviewed rootless Podman/Docker runner that accepts argv vectors only, enforces command timeouts, and returns normalized results.
2. An independent host/runtime inspector that reads the stopped container's actual configuration and kernel/network state.
3. A fresh one-time challenge and Ed25519-signed inspector envelope bound to exact runtime ID, worker ID, image digest, launch-spec digest, namespace identity, seccomp, mounts, resource limits and nftables rules.
4. A replay-resistant challenge issuer/consumer and trusted public-key provisioning/rotation outside the worker.
5. Real failure handling for process termination, cancellation, host reboot, proxy outage, partial container creation and ambiguous runtime command outcomes.
6. Disposable-Linux integration tests for each supported Podman/Docker version, including proof that direct TCP, direct DNS, UDP/QUIC and alternate-route egress are blocked.

## Test scope and limitations

Mock tests cover successful two-phase ordering, invalid signed evidence blocking start, create/start failure cleanup, one-shot launch, abort cleanup and argv-only runner interaction. CI success proves these repository contracts and tests; it does not prove a real OCI runtime, firewall, namespace or browser is secure.

No runtime command was executed. No container, network, namespace, firewall rule, mount, browser or website was created or accessed. Android/Termux compatibility remains unqualified. Live browsing remains disabled. No paid provider, API key, payment, purchase, trading or money movement was used. No merge or deployment was performed.

## Acceptance status

- [x] OCI lifecycle orchestration and mock tests committed.
- [x] Exact-head GitHub Actions CI passes.
- [ ] Trusted external runner and inspector implemented and independently assessed on a disposable Linux host.
- [ ] Actual namespace, seccomp, mount, resource-limit and firewall state verified from the host.
- [ ] Direct egress/DNS/UDP/QUIC bypass and proxy-outage behavior proven from inside the real worker.
- [ ] P12 proxy/worker topology mismatch resolved.
- [ ] Real-worker browser integration matrix passed.

**Decision:** P15.2 repository implementation is PASS; operational acceptance remains **BLOCKED** until the external runtime and network-security evidence is independently verified. Browser execution remains disabled.
