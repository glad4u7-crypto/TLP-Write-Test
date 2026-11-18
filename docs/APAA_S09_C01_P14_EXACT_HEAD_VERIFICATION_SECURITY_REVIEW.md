# APAA-S09-C01-P14 — Exact-Head Verification & Security Review

**Branch:** `feature/apaa-s09-c01-p01-browser-launch`
**Latest verified CI head:** `56f6b6440df9b9891be1595386b5d7785dfe49e4`
**CI:** [APAA Security CI run #833 — SUCCESS](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/44106225841)
**PR:** [#10 — Draft/Open/Unmerged](https://github.com/glad4u7-crypto/TLP-Write-Test/pull/10)

## Exact-head CI evidence

| Item | Result |
|---|---|
| Verified commit | `56f6b6440df9b9891be1595386b5d7785dfe49e4` |
| GitHub Actions run | [Run #833](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/44106225841) |
| Run conclusion | **SUCCESS** |
| Python | 3.12 |
| Dependencies | Installed from `requirements.txt`; Chromium certificate tooling installed |
| Python syntax | `python -m compileall -q app.py core tests` — PASS |
| Chromium TLS trusted CA | PASS |
| Chromium TLS hostname mismatch | PASS |
| Chromium TLS expired certificate | PASS |
| Restricted-proxy real Chromium test | PASS |
| Live browsing controller policy/lifecycle | 9 passed |
| Worker adapter contract | 8 passed |
| Linux host inspector contract | 6 passed |
| Remaining security suite | **1002 passed, 1 deprecation warning** |

The exact-head CI result verifies repository code and test contracts. It is not operational proof of host/container isolation.

## Work completed

- Added adversarial tests for untrusted signing key, modified signature, mismatched proxy IP allowlist, and invalid freshness policy.
- Fixed the context-level redirect fixture in `tests/test_safe_navigation.py`.
- Added fail-closed tests for unknown evidence envelope fields, future-dated signed evidence and empty trust store.
- Added Chromium TLS integration coverage for trusted CA acceptance, hostname mismatch rejection and expired certificate rejection.
- Added real Chromium navigation through a restricted local CONNECT proxy.
- Added explicit Python syntax validation and verified it in CI.
- Added two-phase OCI worker lifecycle orchestration with mandatory injected command/evidence ports.
- Updated P13/P15.2 documentation with exact-head CI evidence and remaining operational acceptance gates.

## Security review findings — still open

1. No reviewed, concrete trusted host/container worker adapter exists in this repository. Current OCI lifecycle is orchestration behind injected ports.
2. Challenge generation, job binding, one-time consumption/replay prevention and signing-key lifecycle remain external.
3. P12 proxy/worker topology mismatch remains unresolved: the CONNECT proxy harness binds loopback, while the worker profile names an internal proxy endpoint. Do not widen the listener as a workaround.
4. No actual container, namespace, seccomp profile, nftables ruleset or host firewall was provisioned or independently inspected.
5. No operational proof exists for blocking direct TCP, direct DNS, UDP/QUIC, IPv4/IPv6 bypasses or alternate routes.
6. The controlled local Chromium tests do not cover a real isolated worker's full redirects, subresources, iframes, popups, WebSocket/WSS, service workers, downloads, DNS rebinding and proxy-outage matrix.
7. Android/Termux remains unqualified; browser launch must remain blocked there.
8. Owner-first access, ask-first actions and no-payment/no-purchase constraints remain mandatory.

## Acceptance matrix

- [x] Exact-head CI success at `56f6b6440df9b9891be1595386b5d7785dfe49e4`.
- [x] Python syntax, dependency and Chromium certificate tooling checks pass.
- [x] Three separate real Chromium TLS acceptance tests pass.
- [x] Real Chromium restricted-local-proxy navigation passes.
- [x] Remaining repository security suite passes: 1002 tests.
- [x] Worker adapter and Linux host inspector contract tests pass.
- [ ] Reviewed host/container adapter and trusted runtime inspector implemented.
- [ ] P12 proxy/worker topology reconciled without broad listener exposure.
- [ ] Actual worker namespaces, seccomp, mounts, resource limits and firewall state verified.
- [ ] Default-deny egress and proxy-only reachability proven from inside the worker.
- [ ] TCP, DNS, UDP/QUIC, alternate routes, IPv4/IPv6 and proxy-outage behavior tested without direct fallback.
- [ ] Full real-browser integration matrix passed against the isolated worker.
- [ ] Android/Termux qualification completed or remains explicitly unsupported.
- [ ] Independent security review and explicit owner approval before any live browser enablement.

## Current qualification decision

Repository implementation and exact-head CI are **PASS**. Production browser execution and network isolation remain **BLOCKED / NOT OPERATIONALLY ACCEPTED** because no independently controlled Linux host/runtime has been provisioned and inspected, and the proxy/worker endpoint mismatch is unresolved.

No host firewall, namespace, container, runtime, Android device or network configuration was changed. No public website, login, form submission, download, payment, purchase, trading, money movement, paid API/provider, Auto-Run, merge, deployment or production enablement occurred.

**Release decision:** Keep browser dispatch and live browsing disabled until every unchecked operational gate is independently evidenced and the Owner explicitly approves.


## Verification addendum — 2026-11-18

- Exact branch/PR head: `a4b2c5be9f9b5563eff1912ad85a9ae95985f2ae`.
- GitHub Actions APAA Security CI run #1406 completed with conclusion **SUCCESS**: https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/44250466439
- The run completed Python syntax validation, Chromium TLS trusted-CA/hostname-mismatch/expired-certificate checks, live-browsing controller lifecycle tests, real Chromium through the restricted local proxy, worker-adapter contract tests, Linux host-inspector contract tests, and the remaining security suite.
- This verifies the exact repository head and CI test contracts only. It does not satisfy the operational acceptance gates below.
- PR #10 remains Draft/Open/Unmerged. Browser/Worker remain disabled; no runtime, host firewall, namespace, container, Android device, or deployment was changed.
