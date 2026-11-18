# APAA-S09-C01-P13 — Browser Runtime & Network Isolation Gate

**Implementation status:** Repository-level orchestration and regression checks are committed and CI-verified. Operational host isolation remains blocked.
**Verified branch head:** `56f6b6440df9b9891be1595386b5d7785dfe49e4`
**CI:** [Run #833 — SUCCESS](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/44106225841)

## Delivered and verified in repository CI

- Added `core/attested_browser_runtime.py`.
- Added `tests/test_attested_browser_runtime.py`.
- Added a fail-closed orchestration gate between signed inspector evidence and an explicitly injected trusted host/container worker adapter.
- Before invoking the adapter, the gate verifies the Ed25519-signed inspector envelope, out-of-band trusted key, exact one-time challenge supplied by the caller, freshness window, immutable launch-spec digest, worker identity, namespace/runtime attestation, and exact proxy-only nftables egress evidence.
- Missing adapter, invalid/stale/tampered evidence, challenge mismatch, or adapter failure blocks launch. No alternate/direct launch path is provided.
- CI verifies Python syntax, dependencies, Chromium TLS validation, local restricted-proxy Chromium navigation, worker-adapter contracts, Linux host-inspector contracts, and the remaining security suite.

## CI evidence — exact current head

- Workflow: APAA Security CI, run #833.
- Commit: `56f6b6440df9b9891be1595386b5d7785dfe49e4`.
- Result: **SUCCESS**.
- Chromium trusted-CA acceptance: passed.
- Chromium hostname mismatch rejection: passed.
- Chromium expired-certificate rejection: passed.
- Real Chromium over restricted local proxy: passed.
- Live-browsing controller policy/lifecycle: 9 passed.
- Worker adapter contract: 8 passed.
- Linux host inspector contract: 6 passed.
- Remaining security suite: **1002 passed, 1 deprecation warning**.
- Explicit Python syntax check: passed.

## Important boundary — not operationally proven

This gate is authorization/orchestration, not a production container runtime, firewall manager, browser launcher, or proof that the kernel enforces isolation. No default host adapter is supplied. A separately reviewed host/container adapter must actually:
1. Create the worker with the exact launch specification and pinned image digest.
2. Apply user/PID/network/IPC/UTS/mount namespace isolation, seccomp, read-only root, dropped capabilities, resource limits and ephemeral writable paths.
3. Configure the browser to use only the specified proxy.
4. Enforce host/container default-deny egress, permitting only the proxy endpoint and blocking direct TCP, direct DNS, UDP/QUIC and alternate routes.
5. Collect independent runtime and firewall observations and sign them with an out-of-band provisioned Ed25519 key.
6. Keep the browser process inside that worker, not on the APAA host process.

The signed evidence is a snapshot and time-bounded. It does not continuously attest runtime state after launch. Challenge replay state and signing-key lifecycle must be managed by an external control plane.

## Remaining acceptance gates

- [ ] Implement and independently review a concrete rootless Podman/Docker host adapter and trusted runtime inspector.
- [ ] Resolve P12 proxy-to-worker endpoint mismatch without widening the proxy listener. Current proxy is loopback-only; worker profile names an internal proxy endpoint.
- [ ] Execute on a disposable Linux host and prove direct TCP, direct DNS, UDP/QUIC, IPv4/IPv6 bypass and alternate routes are denied from inside the actual worker.
- [ ] Prove proxy outage has no direct fallback.
- [ ] Run real-worker browser tests for redirects, cross-host/port redirects, subresources, iframes, popups, WebSocket/WSS, service workers, downloads and DNS rebinding.
- [ ] Verify worker destruction after success, failure, timeout, cancellation and host reboot.
- [ ] Independent security review and explicit owner approval before enabling browser execution.

## Safety and release decision

No host firewall, namespace, container, runtime, Android device, or network configuration was changed. No public website was accessed. No credentials, login, form submission, download, payment, purchase, trading, money movement, paid provider, Auto-Run, merge, deployment or production enablement occurred.

**Decision:** Repository-level implementation and CI verification are PASS. Production browser runtime/network isolation is **BLOCKED / NOT ACCEPTED** until the external host, topology, real-worker and independent-review gates above pass. Browser dispatch and live browsing remain disabled.
