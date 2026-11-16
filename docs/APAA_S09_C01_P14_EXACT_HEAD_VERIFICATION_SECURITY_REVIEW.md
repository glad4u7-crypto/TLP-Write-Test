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

## Safety boundary

No host firewall, namespace, container, runtime, or network configuration was changed. No browser was launched and no public website was accessed. No credentials, API keys, paid provider, payment, purchase, trading, money movement, Auto-Run, merge, deployment, or production enablement occurred.

**Decision:** P14's CI-verification subtask has a verified PASS at the stated commit. P14 as a whole is **NOT operationally accepted**. Live browsing remains disabled.
