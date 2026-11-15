# APAA-S09-C01-P10 — Redirect-Aware Egress Architecture

**Status:** Design baseline committed; implementation and verification are separate gates.  
**Parent:** P09 security audit  
**Branch:** feature/apaa-s09-c01-p01-browser-launch  
**Decision:** Adopt a mandatory, separately enforced outbound proxy/egress gateway as the security boundary. Keep live browsing disabled until P11–P14 are complete and reviewed.

## 1. P10 objective

Resolve the architectural blockers identified by P09:

- SEC-01: do not assume Playwright route callbacks intercept every redirect hop.
- SEC-02: do not treat DNS validation data as proof that the browser connected to the validated IP.
- SEC-03: prevent browser traffic from bypassing the egress boundary.

P10 defines the architecture only. It does not implement a proxy, open sockets, change firewall rules, install software, launch a browser, or enable live browsing.

## 2. Chosen architecture

**Browser → OS/container network guard → mandatory egress proxy → validated pinned-IP dialer → Internet destination**

The browser must have no direct outbound network path. The proxy is the only permitted egress path. This restriction must be enforced outside the browser process (for example, by a dedicated container/network namespace policy or a host firewall policy applied by an authorized operator). A Playwright route callback is defense in depth, not the network security boundary.

### Components

1. **Browser adapter**
   - Uses an ephemeral browser context and a configured explicit proxy.
   - Retains the existing hostname allowlist and context-level Playwright routing as an additional early-denial layer.
   - Disables downloads by default, blocks service workers, and does not enable persistent profiles.
   - Disables direct UDP/QUIC paths where supported; the network guard independently blocks all browser egress except the proxy.

2. **Egress proxy**
   - Accepts browser proxy requests only from the isolated browser runtime.
   - Supports only explicitly approved HTTP proxy methods and destination ports.
   - Rejects malformed authorities, credentials, unsupported schemes, localhost, IP literals unless explicitly allowlisted, and destinations outside the configured hostname allowlist.
   - For plain HTTP, validates every absolute-form request target and every subsequent request.
   - For HTTPS, handles CONNECT authority authorization before establishing a tunnel. The browser performs end-to-end TLS to the destination through the tunnel; the proxy does not intercept or weaken certificate verification.

3. **Pinned-IP dialer**
   - Resolves the authorized hostname once per new outbound connection using a controlled resolver.
   - Rejects the whole resolution result if any returned address is invalid or non-global; rejects empty answers.
   - Dials a selected validated IP literal directly, never re-resolving the hostname during that connection attempt.
   - Verifies the actual socket peer address after connect against the selected pin.
   - Keeps the original hostname as the logical destination. For HTTPS CONNECT, the browser retains the original hostname for TLS SNI and certificate hostname verification through the tunnel.
   - Repeats authorization and pinning for every new destination connection. Never accepts a caller-supplied arbitrary IP as a substitute for an authorized hostname.

4. **Network guard**
   - Allows the browser runtime to reach only the proxy address and required local runtime services.
   - Denies direct TCP egress, direct DNS egress, UDP/QUIC, and alternate proxy bypass routes.
   - Allows the proxy process to reach only approved destination ports.
   - Must be tested from the actual runtime boundary, not inferred from configuration text.

5. **Audit log**
   - Records timestamp, normalized hostname, port, policy decision, selected IP pin, peer-IP verification result, and a correlation ID.
   - Does not record passwords, cookies, authorization headers, page contents, form values, or full sensitive query strings.
   - Fails closed if required audit evidence cannot be recorded, subject to a documented bounded local logging policy.

## 3. Redirect behavior and security boundary

### HTTPS

For HTTPS, the proxy authorizes the CONNECT hostname and port, resolves and pins the destination, and opens the TCP tunnel to that pinned IP. TLS remains end-to-end between the browser and origin.

When an HTTPS response redirects to a different hostname, the browser must establish a new CONNECT tunnel; the proxy independently authorizes and pins that new destination. A same-host redirect remains within the already authorized hostname/port tunnel and does not introduce a new network destination. A changed port requires a new authorized tunnel.

The proxy does not claim to inspect encrypted HTTP redirect response headers. The security property is that every network destination tunnel is independently authorized and the browser cannot connect directly around the proxy. Browser-side route checks remain useful early-denial defense, but are not relied upon for redirect enforcement.

### HTTP

If HTTP is explicitly enabled in a future policy, the proxy must validate each absolute request URI and each request target before forwarding. The default policy remains HTTPS-only. Cleartext HTTP must not be enabled merely to make a test pass.

### Redirect restrictions

- No redirect may expand the configured host allowlist.
- No redirect may change to a disallowed scheme or port.
- Redirect loops and excessive redirect counts remain bounded at the browser/navigation layer.
- Any failed authorization, DNS lookup, peer-IP verification, proxy connection, or audit requirement aborts the request.
- Redirect behavior must be demonstrated with a controlled test origin and a real supported browser before approval.

## 4. Threat model and required defenses

| Threat | Required control |
|---|---|
| Redirect to an untrusted host | New CONNECT/request authorization at proxy |
| DNS rebinding / DNS TOCTOU | Controlled resolution, literal-IP dial, peer-IP verification |
| Mixed public/private DNS answers | Reject entire answer set |
| Direct browser network bypass | OS/container network guard |
| Direct DNS or QUIC bypass | Network guard denies it |
| WebSocket / WSS | Proxy-only network path; destination authorization; integration tests |
| Popup, iframe, subresource | Same browser proxy and network guard; context routing as defense in depth |
| Browser background traffic | Proxy-only network path; default deny |
| Proxy unavailable | Fail closed; no direct fallback |
| Certificate downgrade / MITM | End-to-end TLS; normal hostname verification; no trust-all certificates |
| Log leakage | Metadata-only audit record and secret redaction |

## 5. Explicit non-goals

- No TLS interception or custom root CA.
- No arbitrary URL or IP access.
- No direct socket access from agent task code.
- No automatic browser downloads or persistent user profile.
- No credentials, login, form submission, payments, purchases, trading, money movement, or checkout.
- No paid API/provider, API key, or charge.
- No Auto-Run or unattended browsing.
- No automatic installation, firewall mutation, deployment, or production enablement.
- Android/Termux remains denied until a separate physical-device qualification.

## 6. Implementation sequence

### P11 — Pinned-IP connector
Implement a small isolated connector with deterministic injected resolver/socket tests. Required tests: public IPv4/IPv6 pins, mixed public/private DNS rejection, empty/invalid DNS, resolver failure, peer mismatch, connection failure, and no second hostname resolution between authorization and dial.

### P12 — Mandatory proxy and network boundary
Implement proxy authorization and wire the browser to it. Add tests for CONNECT allow/deny, port restrictions, proxy outage, no direct fallback, HTTP request target validation (if HTTP is supported), WebSocket/WSS, popup, iframe, and background requests. Prove that the runtime cannot reach the Internet directly.

### P13 — Real-browser security tests
Use a controlled local test environment only. Test cross-host redirects, same-host redirects, changed-port redirects, disallowed redirects, subresources, popups, WebSocket/WSS, DNS rebinding simulation, proxy outage, and certificate verification. No public websites or real user accounts.

### P14 — Exact-head verification and security review
Run all unit/integration tests on the exact branch head, retain CI evidence, review logs for secret leakage, and conduct an independent security review. Live browsing remains disabled unless every blocker is closed.

## 7. P10 acceptance criteria

- [x] Redirect and DNS enforcement design selected.
- [x] Security boundary explicitly placed outside Playwright page routing.
- [x] HTTPS CONNECT / end-to-end TLS behavior documented.
- [x] Pinned-IP dial and peer verification requirements specified.
- [x] Direct egress, DNS and UDP/QUIC bypass controls specified.
- [x] P11–P14 implementation and verification sequence defined.
- [ ] Proxy implemented.
- [ ] Pinned-IP connector implemented.
- [ ] Network guard operationally enforced.
- [ ] Real-browser tests pass.
- [ ] Exact-head CI and independent review complete.

## 8. Final P10 decision

**P10 design is complete. P10 does not close SEC-01, SEC-02 or SEC-03.** Those findings remain open until the implementation and evidence gates are satisfied. C01 remains restricted to development/testing; live browsing is not authorized.
