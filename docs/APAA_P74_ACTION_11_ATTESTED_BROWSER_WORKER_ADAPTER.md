# APAA P74 Action 11 — Attested Browser Worker Adapter

**Status:** Bootstrap/lifecycle adapter and contract tests committed; no production host backend is bundled or enabled.  
**Checkpoint:** `APAA-P74-ACTION-11-ATTESTED-BROWSER-WORKER-ADAPTER`  
**Branch:** `feature/apaa-s09-c01-p01-browser-launch`

## What was implemented

- `core/browser_worker_adapter.py` adds `AttestedBrowserWorkerAdapter`, a concrete per-job orchestration layer implementing the existing `BrowserWorker` structural contract.
- It provisions a fresh worker through an explicitly injected host/container backend.
- It obtains a fresh host snapshot source for that exact worker.
- It generates a 256-bit one-time challenge and asks the host inspector to produce signed runtime + effective nftables evidence.
- It passes the signed evidence through the existing Ed25519 `AttestedBrowserRuntime` gate.
- The backend's `start_worker` is invoked only inside the gate's verified callback.
- It forwards the validated browser job, cancellation token, hard deadline and pinned destination to the remote worker.
- Success, failure and cancellation all converge on process termination plus worker/ephemeral-storage destruction. Any unconfirmed cleanup is a hard failure.
- Duplicate session IDs are rejected; no local-process or direct-network fallback exists.

## Backend contract

The privileged `IsolatedWorkerBackend` must implement:

1. `provision(spec, session_id)`: create an unstarted, unprivileged container/VM exactly matching the launch spec.
2. `snapshot_source(handle)`: read fresh runtime, network namespace and effective nftables state from the host.
3. `start_worker(handle, spec, verified_evidence)`: start the browser only after the signed evidence gate has accepted the exact worker and firewall state.
4. `destroy_worker(handle)`: terminate and remove the worker plus ephemeral storage; return true only after independent confirmation.

The backend must enforce user/PID/network/IPC/UTS/mount namespaces, read-only root, dropped capabilities, no-new-privileges, seccomp, no host/secret mounts, resource limits, a fresh profile, proxy-only egress, blocked direct DNS and no exposed CDP/control socket. It must not trust claims supplied by the browser process itself.

## Tests and CI

- `tests/test_browser_worker_adapter.py` covers bootstrap ordering, a real Ed25519 + nftables evidence-verification path before remote start, missing/invalid inspector, cleanup on failure, mandatory process/storage teardown, duplicate session IDs and cancellation.
- CI now runs the adapter contract tests as a separate step.
- Existing attestation, nftables parser, proxy and pinned-IP connector tests remain part of the broader security suite.

## Explicit limits

This is an attested adapter/orchestration layer, **not a complete Linux container runtime implementation**. No Docker/Podman/Kubernetes/VM backend is included; no host firewall or namespace is modified by this commit. A trusted host-side implementation still needs separate review and real-host evidence. Consequently:

- Public live browsing remains disabled.
- The UI does not expose this adapter.
- No cookies, login sessions, form submission, downloads, purchases, payments, trading, money movement, paid APIs, Auto-Run, deployment or PR merge are enabled.
- No CI result is considered successful until the exact latest commit has a green run.

## Acceptance checklist

- [x] Per-job adapter orchestration behind signed runtime/firewall verification.
- [x] Fresh challenge and evidence collection per worker.
- [x] Browser process starts only after the evidence gate.
- [x] Cancellation and teardown are joined to the coordinator contract.
- [x] Process exit and ephemeral-storage cleanup must both be confirmed.
- [x] Contract tests added to CI.
- [x] Adapter integration test exercises the actual signed-evidence verifier before the backend start callback.
- [ ] Exact-head CI passes all TLS, live-browsing, adapter and regression tests.
- [ ] A concrete host/container backend is implemented and independently reviewed.
- [ ] Real Linux namespace, seccomp, cgroup/resource and nftables enforcement is observed on the target host.
- [ ] DNS is performed only by the proxy and IPv4/IPv6 pinned connections are verified from the worker boundary.
- [ ] UI integration is separately reviewed and requires action-specific user approval.

**Decision:** The application now has the missing attested worker-bootstrap layer, but it deliberately refuses to claim production browsing until a real host backend supplies independently verifiable isolation.
