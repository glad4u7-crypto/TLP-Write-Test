# APAA-S09-C01-P13 — Browser Runtime & Network Isolation Gate

**Implementation status:** P13 code slice committed; exact-head CI and operational host evidence remain pending.  
**Parent architecture:** P10 mandatory proxy + external network guard; P11 pinned-IP connector; P12 CONNECT proxy.  
**Branch:** feature/apaa-s09-c01-p01-browser-launch

## Delivered

- Added \`core/attested_browser_runtime.py\`.
- Added \`tests/test_attested_browser_runtime.py\`.
- Added a fail-closed orchestration gate between the signed inspector and a trusted host/container worker adapter.
- Before invoking the adapter, the gate verifies the Ed25519-signed inspector envelope, out-of-band trusted key, exact one-time challenge supplied by the caller, freshness window, immutable launch-spec digest, worker identity, namespace/runtime attestation, and exact proxy-only nftables egress evidence using the existing P05/P06 validators.
- Missing adapter, invalid/stale/tampered evidence, challenge mismatch, or adapter failure blocks launch. No alternate/direct launch path is provided.
- The adapter receives only the immutable \`WorkerLaunchSpec\` and normalized \`VerifiedInspectorEvidence\`.

## Important boundary

This gate is an authorization/orchestration boundary, **not** a container runtime, firewall manager, browser launcher, or proof that the kernel is enforcing isolation. No default host adapter is supplied. A separately reviewed host/container adapter must actually:
1. create the worker with the exact launch specification and pinned image digest;
2. apply user/PID/network/IPC/UTS/mount namespace isolation, seccomp, read-only root, dropped capabilities, resource limits and ephemeral writable paths;
3. configure the browser to use only the specified proxy;
4. enforce host/container default-deny egress, permitting only the proxy endpoint and blocking direct TCP, direct DNS, UDP/QUIC and alternate routes;
5. collect independent runtime and firewall observations and sign them with an out-of-band provisioned Ed25519 key;
6. keep the browser process inside that worker, not on the APAA host process.

The signed evidence is a snapshot and is time-bounded. It does not continuously attest runtime state after launch. The challenge must be generated and consumed once by an external control plane; this module does not manage challenge replay state or signing-key lifecycle.

## Tests authored

- Valid signed evidence reaches the adapter exactly once.
- No adapter configured blocks launch.
- Challenge mismatch blocks launch before adapter invocation.
- Tampered firewall evidence blocks launch before adapter invocation.
- Stale evidence blocks launch before adapter invocation.
- Adapter failure fails closed without direct/alternate fallback.

Tests are authored but not yet executed on the exact branch head in this checkpoint. CI results must be inspected separately.

## Explicitly not completed / not authorized

- P12 proxy-to-browser worker wiring and endpoint topology reconciliation remain open. The current P12 proxy is loopback-only while the worker profile describes an internal proxy endpoint; do not bridge this by widening a bind address.
- No host/container adapter, runtime, namespace, firewall or nftables rule was created or changed.
- No real browser was launched. No browser tests for redirects, WebSocket/WSS, popups, iframes, subresources, background requests, DNS rebinding, proxy outage or certificate verification were run.
- Direct TCP/DNS/UDP/QUIC bypass is not operationally proven blocked.
- No Android/Termux qualification; browser launch remains blocked there.
- No live browsing, public website, login, form submission, download, payment, purchase, trading, money movement, paid API/provider, API key, Auto-Run, deployment, PR merge or production enablement.

## Acceptance

- [x] Signed-evidence gate added.
- [x] Exact launch-spec and proxy-only firewall evidence validated before adapter call.
- [x] Fail-closed tests authored.
- [ ] Exact-head unit tests and CI pass.
- [ ] Reviewed host/container adapter exists and is independently assessed.
- [ ] Real-browser controlled integration matrix passes.
- [ ] No-direct-egress/DNS/UDP bypass is proven from the actual worker boundary.
- [ ] Independent security review and explicit authorization completed.

**Decision:** P13 implementation slice is committed, but the overall browser runtime/network-isolation checkpoint is **NOT operationally complete**. Live browsing remains disabled. P14 verification and review remain required.
