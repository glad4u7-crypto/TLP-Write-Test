# APAA-S09-C01-P14 — Exact-Head Verification & Security Review

**Checkpoint:** P14  
**Branch:** `feature/apaa-s09-c01-p01-browser-launch`  
**Status:** CI verification completed successfully on commit `8215c48429904225d3c65b4f6cbaa48879ca7864`; further adversarial tests are committed on the newer head and their CI is pending. Operational browser isolation remains BLOCKED.

## Work completed

- Added adversarial tests for untrusted signing key, modified signature, mismatched proxy IP allowlist, and invalid freshness policy.
- Fixed the context-level redirect fixture in `tests/test_safe_navigation.py`: route observations are recorded by the actual route owner, including BrowserContext-level routing.
- Added three more fail-closed tests on the subsequent commit:
  - unknown evidence envelope fields;
  - future-dated signed evidence;
  - empty trust store.
- Inspected Python 3.12 CI workflow, dependencies, evidence verifier, and worker launch gate.
- Verified that the worker adapter remains optional and absent by default; invalid evidence must prevent the callback from being invoked.

## Exact-head CI evidence

| Item | Result |
|---|---|
| Verified commit | `8215c48429904225d3c65b4f6cbaa48879ca7864` |
| GitHub Actions run | [Run #9](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43789719325) |
| Run conclusion | **SUCCESS** |
| Test command | `python -m pytest -q` |
| Test result | **908 passed in 11.96s** |
| Python | 3.12.16 |
| Dependencies | Installed from `requirements.txt` |

The subsequent adversarial-test commit is `6a78ba2d3cb3b3fa6221636f629f1b60e1f91297`. Its own exact-head CI result must be checked before treating the expanded suite as verified.

## Security review findings — still open

1. No trusted host/container worker adapter exists in this repository. The gate is orchestration only.
2. Challenge generation, job binding, one-time consumption/replay prevention, and signing-key lifecycle remain external.
3. P12 proxy/worker topology mismatch remains unresolved: the CONNECT proxy harness binds loopback, while the worker profile names an internal proxy endpoint. Do not widen the listener as a workaround.
4. No actual container, namespace, seccomp profile, nftables ruleset, or host firewall was provisioned or inspected in this work.
5. No operational proof exists for blocking direct TCP, direct DNS, UDP/QUIC, alternate routes, or background traffic.
6. Browser-level tests for redirects, subresources, iframes, popups, WebSocket/WSS, service workers, downloads, DNS rebinding, proxy outage, and TLS validation remain unrun against a real isolated worker.
7. Android/Termux remains unqualified and browser launch must remain blocked there.
8. Owner-first access, ask-first actions, and no-payment/no-purchase constraints remain mandatory.

## Acceptance matrix

- [x] P14 adversarial tests committed.
- [x] CI workflow and dependency configuration inspected.
- [x] Exact-head CI success confirmed for commit `8215c48429904225d3c65b4f6cbaa48879ca7864` (908 passed).
- [ ] Exact-head CI success confirmed for expanded test commit `6a78ba2d3cb3b3fa6221636f629f1b60e1f91297`.
- [ ] Independently reviewed host/container adapter and threat model.
- [ ] Reconciled P12 proxy/worker topology without broad listener exposure.
- [ ] Verified actual worker namespaces, seccomp, mounts, resource limits and firewall state.
- [ ] Proved default-deny egress and proxy-only reachability from inside the worker.
- [ ] Tested TCP, DNS, UDP/QUIC, alternate routes and proxy outage with no direct fallback.
- [ ] Completed real-browser integration matrix.
- [ ] Completed Android/Termux qualification or explicitly kept unsupported.
- [ ] Independent security review and explicit owner approval before any live browser enablement.

## Current branch-head CI trigger

The latest PR #10 branch head inspected before this update was `7b7a9cfccec7745a4055e67f888acf541bc5987c`; no pull-request workflow run was returned for that SHA. This documentation-only commit is intended to trigger the branch's existing `push` security workflow so the expanded suite can receive an exact-head CI result. The result must be read from GitHub Actions before this gate is changed to PASS.

## Safety boundary

No host firewall, namespace, container, runtime, or network configuration was changed. No browser was launched and no public website was accessed. No credentials, API keys, paid provider, payment, purchase, trading, money movement, Auto-Run, merge, deployment, or production enablement occurred.


## Browser Security Qualification — execution plan started

This section separates what can be checked in repository CI from what requires a real, independently controlled Linux host. CI tests using fakes or a local test proxy are useful regression evidence, but do not prove OS-level isolation.

### BQ-01 — Runtime/backend trust boundary
- [x] Adapter contract refuses construction without an explicitly injected backend, signing key and trusted inspector key.
- [x] Worker startup is ordered after signed pre-start evidence verification.
- [x] Failure/cancellation paths require process termination and worker/storage destruction.
- [ ] Implement a concrete host/container backend in a separately reviewed environment; no such backend is bundled.
- [ ] Verify backend identity, image digest, namespace identity and effective firewall state from a trusted host-side inspector, not from the browser process.

### BQ-02 — Proxy and pinned destination
- [x] CONNECT parser is bounded and strict; HTTPS port 443 is the default.
- [x] Proxy authorization uses the pinned-IP connector and checks the connected peer.
- [x] Proxy harness refuses non-loopback bind addresses.
- [ ] Resolve the worker endpoint mismatch: proxy harness currently binds loopback, while the worker profile expects `egress-proxy.internal:3128`.
- [ ] Wire browser launch to the mandatory proxy without any direct-network fallback.
- [ ] Run proxy server lifecycle/concurrency/relay tests against the chosen host topology.

### BQ-03 — Default-deny network boundary
- [ ] From inside the real worker, prove only the proxy endpoint is reachable.
- [ ] Prove direct TCP, direct DNS, UDP/QUIC, alternate proxies, IPv4 and IPv6 bypasses are denied.
- [ ] Prove proxy outage causes navigation failure and no direct fallback.
- [ ] Inspect effective network namespace, nftables/firewall and process identity from the host.
- [ ] Repeat the checks for browser background traffic and browser-created child processes.

### BQ-04 — Real browser behavior
- [ ] Controlled HTTPS redirect to an allowed destination and to a denied destination.
- [ ] Cross-host and cross-port redirect re-authorization.
- [ ] Subresource, iframe, popup and WebSocket/WSS destination policy.
- [ ] DNS rebinding / mixed public-private answer rejection.
- [ ] TLS trusted-CA acceptance, hostname mismatch rejection and expired-certificate rejection.
- [ ] Download/service-worker/background network paths remain blocked unless separately approved.
- [ ] Browser process and ephemeral profile are destroyed after success, failure, timeout and cancellation.

### BQ-05 — Release gates
- [ ] Exact-head CI on current PR #10 head `087c64e178f3f217e0163342e443d28741133c5c`.
- [ ] Independent security review of the actual host backend and network boundary.
- [ ] Owner review of evidence and explicit approval before enabling any browser execution.

### Current qualification decision

The repository has an attested worker orchestration contract and a loopback-only CONNECT proxy implementation, but not a production host backend or mandatory OS network boundary. The proxy/worker endpoint mismatch is unresolved. Therefore BQ-01 through BQ-05 remain **IN PROGRESS / BLOCKED** as marked above; browser launch and Worker execution must remain disabled. No host firewall, namespace, container or Android device has been modified by this work.

**Decision:** P14's CI-verification subtask has a verified PASS at the stated commit. P14 as a whole is **NOT operationally accepted**. Live browsing remains disabled.
