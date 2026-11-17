# APAA P74 Action 10 — Controlled Live Browsing Integration

**Status:** Controller and test coverage committed; CI and host-runtime acceptance pending.  
**Checkpoint:** `APAA-P74-ACTION-10-CONTROLLED-LIVE-BROWSING`  
**Branch:** `feature/apaa-s09-c01-p01-browser-launch`

## Objective

Provide the first application-level live-browsing execution boundary without enabling unrestricted public browsing. The controller accepts a short-lived, closed-schema read-only browser job, launches Chromium only through the signed runtime/firewall attestation gate, and returns bounded page information.

## Delivered code

- `core/live_browsing.py` — `LiveBrowsingController` and immutable `LiveBrowsingResult`.
- `tests/test_live_browsing.py` — policy, audit, byte-limit, request-method, cross-origin redirect, lifecycle and failure-path tests.
- Extended `tests/test_chromium_tls_integration.py` with a real Chromium end-to-end test against a local HTTPS fixture through a restricted CONNECT proxy.
- Extended `.github/workflows/apaa-security-ci.yml` with separate controller and real-Chromium live-browsing steps.

## Enforced behavior

1. Closed-schema job validation, a short expiry window and bounded runtime/response size.
2. Exact HTTPS origin allowlist; every browser request is revalidated.
3. Only GET and HEAD requests; mutation methods are blocked.
4. Cross-origin redirects, subresources and other origin escapes are aborted.
5. Maximum 250 requests per job.
6. Downloads remain disabled; service workers remain blocked by the attested launcher; unexpected popup pages are closed.
7. Supported actions are limited to exact-origin navigation, visible text, page title, same-origin link metadata and a transient screenshot.
8. Required acceptance audit must persist before browser launch; URL and page content are excluded from audit events.
9. Browser context/session is closed after success or failure.
10. Chromium TLS certificate and hostname verification remain enabled.

## Test boundaries

The real-Chromium test uses a generated test CA, an isolated temporary NSS trust store, a local HTTPS fixture and a CONNECT proxy that permits only the exact test hostname and fixture port. The test injects the local fixture session at the launch boundary so it can validate the actual Chromium navigation/controller path without pretending that a production host/container adapter exists.

The test is not permission to browse arbitrary public websites and does not prove the production worker's firewall or DNS/IP pinning.

## Not enabled / outstanding

- No default host/container worker adapter exists; production launch remains blocked by the attested runtime gate.
- The controller is not yet registered as an executable UI action in the Streamlit app.
- No public-origin allowlist has been provisioned.
- No live user browsing, authenticated sessions, cookies, form submission, downloads, purchases, payments, trading, money movement, paid APIs, Auto-Run, deployment or PR merge is enabled.
- The proxy must enforce connection-time DNS resolution, pinned-IP dialing, TLS SNI/hostname verification and proxy-only worker egress.
- Redirect, WebSocket/WSS, iframe, popup, subresource and DNS-rebinding behavior still require a full browser integration matrix at the actual isolated worker boundary.
- The previous Action 09 Chromium TLS CI must also be green; no test is accepted from source inspection alone.

## Acceptance checklist

- [x] Read-only controller authored behind the signed runtime launch function.
- [x] Exact-origin request guard and GET/HEAD-only policy.
- [x] Required audit-before-launch and bounded result handling.
- [x] Unit tests authored for policy and lifecycle.
- [x] Real Chromium local-fixture integration test authored.
- [x] CI includes separate live-browsing test steps.
- [ ] Latest exact-head CI passes all TLS, controller, real-Chromium and remaining security tests.
- [ ] Production host/container adapter is implemented and independently reviewed.
- [ ] Actual worker firewall/proxy-only egress and pinned-IP behavior are proven.
- [ ] UI integration receives explicit action-specific user approval and passes end-to-end review.

**Decision:** Controlled live-browsing code exists, but production live browsing remains **DISABLED** until the outstanding isolation and CI evidence is complete.
