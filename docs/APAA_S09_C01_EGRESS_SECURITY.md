# APAA S09-C01 — Browser Egress Security

## Current implementation boundary

The current branch contains URL policy validation, DNS resolution checks,
a pinned-IP TCP connector, and a loopback-only HTTP CONNECT proxy.

The proxy is an **egress component**, not a complete browser sandbox. It does
not itself force Chromium/Playwright to use the proxy and cannot prevent a
browser process from opening direct sockets. A production deployment must
place the browser in an OS/container network namespace or firewall policy
that denies direct outbound traffic and permits only the proxy endpoint.

## Security invariants

1. Only explicitly allowlisted hostnames are authorized.
2. URL credentials, malformed authorities, localhost, and non-public IPs are denied.
3. Every DNS answer must be globally routable; mixed public/private answers fail closed.
4. The connector receives numeric IP literals only and verifies the connected peer.
5. CONNECT is the only supported proxy method; default destination port is 443.
6. The proxy binds only to a numeric loopback address.
7. Redirects must be re-authorized hop by hop by the navigation policy.
8. TLS must retain the original hostname for SNI and certificate verification.
9. Browser direct egress isolation is a deployment requirement and remains unverified.

## CI

GitHub Actions runs the repository pytest suite on pushes to this feature branch,
pull requests, and manual dispatch. A green CI result is required before calling
this chapter security-verified.

## Not yet complete

- Wire the proxy into the actual browser launch/runtime.
- Enforce OS/container-level deny-by-default egress.
- Verify TLS SNI and certificate hostname validation in the browser adapter.
- Test redirect handling in the live browser.
- Run integration tests in the deployed Streamlit environment.
- Document and test permission boundaries for user-supplied browser tasks.

No production security certification is implied by unit tests alone.
