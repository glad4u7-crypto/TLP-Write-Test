# APAA-S09-C01-P14 — Exact-Head Verification & Security Review

**Checkpoint:** P14  
**Branch:** feature/apaa-s09-c01-p01-browser-launch  
**Status:** Verification preparation and adversarial test expansion committed; acceptance remains BLOCKED pending an actual CI run and independent operational evidence.

## Work completed in this checkpoint

- Expanded \`tests/test_attested_browser_runtime.py\` with adversarial cases:
  - untrusted signing key;
  - modified signature;
  - mismatched approved proxy IP allowlist;
  - invalid evidence freshness policy.
- Retained the prior positive path and fail-closed tests for missing adapter, challenge mismatch, modified firewall evidence, stale evidence and worker-adapter exception.
- Inspected the repository's CI workflow and dependency manifest:
  - Python 3.12;
  - dependencies installed from \`requirements.txt\`;
  - workflow command is \`python -m pytest -q\`;
  - workflow is configured for push to this feature branch, pull requests, and manual dispatch.
- Inspected the gate and evidence verifier source. The verifier checks Ed25519 signature authenticity, exact challenge equality, launch-spec/runtime binding, evidence freshness, and exact proxy-only firewall allowlist before the adapter is called.

## Verification results

| Check | Result |
|---|---|
| Source files exist on target branch | PASS |
| P14 adversarial tests committed | PASS |
| CI workflow configuration inspected | PASS |
| Requirements manifest inspected | PASS |
| Python test suite executed in this environment | NOT RUN |
| Exact-head GitHub Actions result confirmed | NOT AVAILABLE |
| Independent host/container adapter review | NOT DONE |
| Live kernel firewall / namespace verification | NOT DONE |
| Real-browser proxy integration tests | NOT RUN |
| Direct TCP, DNS, UDP/QUIC bypass proof | NOT DONE |

No CI PASS is claimed. The GitHub workflow/status API currently provides no workflow run or status record for the inspected head. A commit existing on GitHub is not evidence that tests passed.

## Security findings / outstanding design obligations

1. **No trusted worker adapter exists in this repository slice.** The gate accepts a callback; the callback is privileged and must be separately implemented, threat-modelled and reviewed.
2. **Challenge replay protection is external.** The caller/control plane must issue cryptographically random challenges, bind them to a job and consume each challenge exactly once. The verifier itself is stateless.
3. **Key lifecycle is external.** Provision trusted public keys out of band; protect private keys, rotate/revoke keys and audit key use.
4. **Attestation is a snapshot.** The signed pre-start evidence does not prove the runtime remains isolated after worker start. Continuous monitoring or a post-start independent attestation is needed.
5. **P12 topology mismatch remains unresolved.** Do not widen the loopback proxy bind address to make the worker connect. A reviewed worker/proxy network design must specify namespace placement, listener binding, routing and firewall rules.
6. **Kernel enforcement is not proven by unit tests.** Actual namespace identity, nftables ruleset, route table, resolver behavior and socket-level bypass tests must be observed from the worker boundary.
7. **Browser behavior remains unqualified.** Integration coverage must include redirects, subresources, iframes, popups, WebSocket/WSS, service workers, downloads, DNS rebinding, proxy failure and TLS certificate validation.
8. **Android/Termux is not qualified.** Do not assume the Linux container/firewall design is available on Android.

## Required P14 acceptance sequence

- [ ] Obtain a completed GitHub Actions run for the exact latest branch head and inspect all job steps/logs.
- [ ] Fix any failures, rerun and record the resulting commit SHA and run URL.
- [ ] Independently review the host/container adapter and its threat model.
- [ ] Resolve P12 proxy/worker topology without exposing a broad listener.
- [ ] Run controlled integration tests from inside the actual worker network namespace.
- [ ] Prove default-deny egress and that only the approved proxy endpoint is reachable; test TCP, UDP, QUIC, DNS and alternate routes.
- [ ] Verify browser requests cannot bypass proxy through redirects, WebSockets, service workers or auxiliary processes.
- [ ] Record evidence, reviewer, environment, test versions and exact commit.
- [ ] Obtain explicit owner approval before enabling any live browser capability.

## Safety and scope

No host firewall, namespace, container, runtime or network configuration was changed. No browser was launched and no website was accessed. No credentials, API keys, paid services, payment, purchase, trading, money movement, Auto-Run, merge, deployment or production enablement occurred.

**Decision:** P14 is not accepted yet. The P14 code/test preparation is committed, but exact-head CI, independent review and operational isolation proof remain mandatory. Keep live browsing disabled.
