# APAA-S09-C01-P12 — Mandatory CONNECT Proxy (Implementation Slice 1)

**Status:** Loopback-only HTTPS CONNECT proxy and offline policy tests committed; browser wiring and OS/container network enforcement remain incomplete.  
**Parent:** P10 redirect-aware egress architecture; P11 pinned-IP connector  
**Branch:** feature/apaa-s09-c01-p01-browser-launch  
**Decision:** This is an implementation slice, not approval for live browsing or a claim that the mandatory egress boundary is operational.

## 1. Files added

- `core/egress_proxy.py`
- `tests/test_egress_proxy.py`

## 2. Implemented behavior

- Accepts only HTTP/1.1 CONNECT requests.
- Parses hostname and explicit port, including bracketed IPv6 authorities.
- Rejects malformed authorities, credentials, paths, unsupported methods/protocol versions, oversized/incomplete headers, and unexpected bytes after the header.
- Defaults to HTTPS destination port 443 only; additional ports require explicit policy configuration.
- Re-authorizes each new CONNECT destination through `EgressDestinationAuthorizer`.
- Opens upstream TCP only through `PinnedIPConnector`, which dials a numeric public IP and verifies peer IP and port.
- Returns a generic tunnel-established response only after the pinned upstream connection succeeds; otherwise fails closed with a generic gateway error.
- Relays opaque TLS bytes without TLS interception or custom certificate trust.
- Server factory binds only to a numeric loopback address. It creates but does not start the server; starting it remains an explicit caller action.

## 3. Security boundaries and remaining gaps

This proxy is not yet an operational mandatory boundary:

- The browser launcher is not yet wired to this proxy.
- No OS/container firewall or network namespace rule has been installed or proven.
- Browser direct TCP, direct DNS, UDP/QUIC, alternate proxy routes, and background traffic are therefore **not** proven blocked.
- No no-direct-fallback test at the operating-system boundary exists.
- No WebSocket/WSS, popup, iframe, subresource, or background-browser integration tests have been run.
- CONNECT-only mode intentionally does not support plain HTTP absolute-form requests.
- Loopback binding limits remote LAN exposure but is not authentication or a substitute for process isolation; other local processes may be able to connect.
- Proxy server startup, shutdown, concurrency, socket relay under load, and real-browser behavior still require controlled local tests.
- The proxy does not record an audit trail yet. No secrets or page content are intentionally logged.

The HTTPS redirect property depends on every new destination requiring a new CONNECT tunnel. Same-host requests within an established tunnel remain inside that authorized hostname/port tunnel. The proxy does not inspect encrypted redirect headers.

## 4. Offline tests authored

- Hostname and IPv6 CONNECT parsing.
- Reject non-CONNECT methods, missing ports, unapproved ports, userinfo, path injection, invalid ports, HTTP/1.0, and trailing data.
- Explicit custom-port allow policy.
- Reject non-loopback bind addresses.
- Confirm construction does not implicitly start a listening server.

Tests use no live destination and no real browser. They were authored but **not executed in this session**. No CI run or passing-test claim is made.

## 5. Acceptance status

- [x] CONNECT request parser and strict method gate.
- [x] Default HTTPS port restriction.
- [x] Authorization + pinned-IP connector integration in proxy code.
- [x] Loopback-only server factory.
- [x] Offline parser/configuration tests authored.
- [ ] Execute tests and resolve any failures on exact branch head.
- [ ] Browser launcher configured to use mandatory proxy.
- [ ] OS/container guard blocks direct TCP, DNS, UDP/QUIC, and alternate bypass.
- [ ] Proxy outage proven to fail closed with no direct fallback.
- [ ] WebSocket/WSS, popup, iframe, subresource, and background traffic integration coverage.
- [ ] Controlled real-browser tests and independent review.

## 6. Final P12 slice decision

**P12 is in progress, not complete.** This commit provides the first CONNECT proxy implementation slice only. SEC-01 and SEC-03 remain open; SEC-02 has a pinned-IP connector implementation but still needs integration and evidence. Live browsing remains disabled. Do not launch this proxy for general use or expose it beyond loopback. No firewall mutation, deployment, credentials, login, form submission, downloads, payment, purchase, trading, money movement, paid services, Auto-Run, or Android/Termux qualification is authorized.
