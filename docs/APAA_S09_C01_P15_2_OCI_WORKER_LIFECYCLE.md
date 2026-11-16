# APAA S09 C01 P15.2 — Two-Phase OCI Worker Lifecycle

## Delivered

- `core/oci_worker_lifecycle.py` adds an explicit stateful lifecycle:
  `NEW → CREATED → INSPECTED → ATTESTED → RUNNING → STOPPED → REMOVED`.
- The command runner and signed-evidence provider are mandatory injected ports. There is no subprocess import, shell execution, default runner, or automatic host integration.
- The only start path is the callback supplied to `AttestedBrowserRuntime`. It checks the exact launch-spec digest and the verified evidence's `created` state before invoking the start argv.
- Failed create/inspect/evidence/start operations fail closed and attempt cleanup. If start was attempted, cleanup attempts stop and then remove; removal is attempted even when stop fails.
- Cleanup is idempotent after successful removal. A lifecycle instance is one-shot; callers must create a new lifecycle for a new job.
- `abort()` is the explicit cancellation/timeout/proxy-outage hook and triggers cleanup.

## Required external integration contract

A future production adapter must still provide all of the following outside this module:

1. A reviewed rootless Podman/Docker runner that accepts argv vectors only, enforces command timeouts, and returns normalized results.
2. An independent host/runtime inspector that reads the stopped container's actual configuration and kernel/network state.
3. A fresh one-time challenge and Ed25519-signed inspector envelope bound to the exact runtime ID, worker ID, image digest, launch-spec digest, namespace identity, seccomp, mounts, resource limits and nftables rules.
4. A replay-resistant challenge issuer/consumer and trusted public-key provisioning/rotation outside the worker.
5. Real failure handling for process termination, cancellation, host reboot, proxy outage, partial container creation and ambiguous runtime command outcomes.
6. Disposable-Linux integration tests for each supported Podman/Docker version, including proof that direct TCP, direct DNS, UDP/QUIC and alternate-route egress are blocked.

## Test scope and limitations

Mock tests cover successful two-phase ordering, invalid signed evidence blocking start, create/start failure cleanup, one-shot launch, abort cleanup and argv-only runner interaction. These are unit-level contract tests, not proof that a real OCI runtime, firewall, namespace or browser is secure.

No runtime command was executed. No container, network, namespace, firewall rule, mount, browser or website was created or accessed. Android/Termux compatibility remains unqualified. Live browsing remains disabled. No paid provider, API key, payment, purchase, trading or money movement was used. No merge or deployment was performed.

## Acceptance status

P15.2 code and mock tests are committed. Operational acceptance remains blocked until a trusted external runner and inspector are implemented and independently tested on a disposable Linux host. The P12 proxy/worker topology mismatch also remains unresolved.
