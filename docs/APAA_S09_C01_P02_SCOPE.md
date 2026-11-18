# APAA-S09-C01-P02 — Website Navigation

**Status:** Core navigation-policy and controller implementation present; latest branch CI not verified.
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
- [x] Playwright navigation controller with request-route enforcement and cleanup.
- [x] Context-level route mode and integration regression coverage.
- [ ] Full repository CI successful on the latest branch head.
- [ ] Real browser navigation qualification inside a separately attested and isolated worker.
- [ ] Android/Termux qualification; desktop CI is not Android evidence.

## Current status

P02 implementation is present in the branch and has focused test coverage. The scope is not marked fully verified until latest-head CI is observed. No public-site browsing is enabled by this document. Browser/Worker dispatch remains disabled; Auto-Run remains OFF.