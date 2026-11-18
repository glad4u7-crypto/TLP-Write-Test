# APAA-S09-C01-P02 — Website Navigation

**Status:** Implementation present and exact-head repository CI verified PASS on 2026-11-18; real isolated-worker and Android qualification remain pending.
**Branch:** `feature/apaa-s09-c01-p01-browser-launch`
**PR:** #10 (Draft; unmerged)

## Scope

Provide an explicit, bounded, fail-closed way for the browser controller to navigate to an Owner-authorized HTTPS destination. This part does not authorize arbitrary sites or mutating website actions.

## Implemented repository components

- `core/browser_navigation.py`: immutable `NavigationPolicy`, hostname/scheme allowlists, URL normalization, private/special-use address rejection, resolver injection, and redirect-chain validation.
- `core/safe_navigation.py`: bounded Playwright `goto` controller; installs a temporary request route, validates initial and routed request URLs, aborts blocked requests, and removes the route in `finally`.
- `tests/test_browser_navigation.py`, `tests/test_safe_navigation.py`, and `tests/test_s09_c01_integration.py`: policy, redirect, cleanup, context-level route and fail-closed regression cases.

## Security limitations

- DNS is resolved and checked before the browser connection; this does not pin the actual socket destination and does not eliminate DNS rebinding/TOCTOU by itself.
- Page-only routing is narrower than BrowserContext routing. Use context-level routing for subresources and additional pages; even that is not an OS firewall or complete browser-process egress boundary.
- WebSocket, browser background traffic, DNS and non-Playwright traffic require independently enforced host/proxy/firewall controls.
- Tests use fakes/injected resolvers; they do not visit live websites or qualify a production browser runtime.

## Acceptance checklist

- [x] URL allowlist, HTTPS defaults, host normalization and malformed URL rejection.
- [x] Private/special-use IP and unsafe DNS-answer rejection.
- [x] Bounded redirect validation and loop rejection.
- [x] Browser controller enforces the configured redirect-hop limit against navigation requests and aborts over-limit hops.
- [x] Playwright navigation controller with request-route enforcement and cleanup.
- [x] Context-level route mode and integration regression coverage.
- [ ] Full repository CI successful on the latest branch head.
- [ ] Real browser navigation qualification inside a separately attested and isolated worker.
- [ ] Android/Termux qualification; desktop CI is not Android evidence.

## Current status

P02 implementation is present in the branch and has focused test coverage, including a controller-level redirect-hop-limit regression case. The scope is not marked fully verified until latest-head CI is observed and the tests execute successfully. No public-site browsing is enabled by this document. Browser/Worker dispatch remains disabled; Auto-Run remains OFF.

## Exact-head CI verification — 2026-11-18

- GitHub Actions APAA Security CI run **#1417** completed with conclusion **SUCCESS**.
- Verified PR #10 branch head: `3c019ff048bee4e69f0d7ce23f9a8bc5e82fea85`.
- The workflow's Python security test job passed, including Python syntax, Chromium TLS acceptance/rejection, live-browsing controller policy/lifecycle, real Chromium through the restricted local proxy, production worker-adapter attestation/lifecycle contract, Linux host-inspector procfs/nftables snapshot contract, and the remaining security test suite.
- P02 source and focused tests present at this exact head: `core/browser_navigation.py`, `core/safe_navigation.py`, `tests/test_browser_navigation.py`, and `tests/test_safe_navigation.py`.
- This verifies repository CI and test contracts at the exact commit. It does **not** prove navigation inside a genuinely provisioned production-isolated worker, connection-time DNS pinning, complete browser-process egress containment, or Android/Termux compatibility.

## Current completion decision

- [x] Navigation policy and bounded browser navigation controller implemented.
- [x] Exact-head repository CI successful on the current branch head.
- [ ] Independently attested production worker and host network boundary qualification.
- [ ] Physical Android/Termux qualification.
- [ ] End-to-end live navigation qualification in the approved isolated runtime.

**P02 status: IMPLEMENTATION + CI VERIFIED; FINAL RUNTIME QUALIFICATION PENDING.** Browser/Worker dispatch remains disabled and Auto-Run remains OFF. No merge, deployment, public-site browsing, or production-readiness claim is authorized by this verification.
