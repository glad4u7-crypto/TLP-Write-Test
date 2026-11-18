# APAA-S09-C01-P11 — Pinned-IP Connector

**Status:** Implementation and deterministic tests committed; execution evidence remains pending.  
**Parent:** P10 redirect-aware egress architecture  
**Branch:** feature/apaa-s09-c01-p01-browser-launch  
**Decision:** The connector is a narrow TCP primitive for a trusted egress-proxy process. It does not enable browser browsing or close the P09 release blockers by itself.

## 1. Files added

- `core/pinned_ip_connector.py`
- `tests/test_pinned_ip_connector.py`

The existing `EgressDestinationAuthorizer` remains responsible for URL policy, allowlist checks, controlled resolution, and rejection of empty, invalid, or mixed public/private answer sets. The new connector accepts the resulting `EgressTarget`, iterates only its canonical public numeric pins, and passes numeric IP literals—not hostnames—to the injected dialer.

## 2. Connector behavior

- Uses IPv4 or IPv6 socket family based on the selected numeric pin.
- The production dialer creates a TCP socket and connects to the numeric IP literal directly. It does not call a hostname resolver or use `create_connection((hostname, port))`.
- Applies a bounded connection timeout (default 5 seconds; configurable up to 60 seconds).
- Checks the connected socket's peer IP **and port** against the selected pin and authorized target port.
- Closes a socket if peer inspection fails or the peer does not match.
- May try another already-authorized pin after an ordinary TCP connection error; it never resolves the hostname again during this process.
- Returns the original logical hostname alongside the socket and selected pin. A future TLS layer must use that original hostname for SNI and certificate hostname verification; this module does not perform TLS and must not disable certificate checks.
- Has no automatic installation, global resolver mutation, or direct browser integration.

## 3. Trust boundary and limitations

The connector is intended to run inside the trusted proxy process. Python callers must obtain `EgressTarget` from `EgressDestinationAuthorizer`; the connector is not a substitute for authorization and a freely constructible Python dataclass is not a cryptographic capability. Untrusted task code must never be allowed to construct targets or call the dialer directly.

This commit does **not** implement the mandatory proxy, OS/container network guard, CONNECT authorization, TLS wrapping, browser wiring, or direct-egress denial. It does not prove real Playwright redirect behavior. No public network connection is made by the tests.

## 4. Deterministic test coverage authored

- IPv4 numeric-pin dial and peer verification.
- IPv6 numeric-pin dial.
- Exactly one resolver call during authorization and no second hostname resolution during dial.
- Peer-IP mismatch closes the socket and fails closed.
- Peer-inspection failure closes the socket and fails closed.
- Ordinary connection failures exhaust only the already-authorized pin list.
- Forged private pin and empty pin list are rejected before dialing.

The test suite uses injected fake sockets and a fake dialer. These tests are authored but **have not been executed in this work session**; no passing-test or CI claim is made.

## 5. Acceptance status

- [x] Isolated numeric-IP connector added.
- [x] IPv4/IPv6 handling added.
- [x] Socket peer IP and port verification added.
- [x] Connection timeout and close-on-failure behavior added.
- [x] Deterministic offline tests authored.
- [ ] Exact-head test execution and CI evidence.
- [ ] Mandatory proxy implementation and browser wiring (P12).
- [ ] OS/container network guard and bypass-denial proof (P12).
- [ ] Real-browser redirect and TLS tests (P13).
- [ ] Independent security review (P14).

## 6. Final P11 decision

**P11 code and test artifacts are committed; verification is pending.** SEC-01, SEC-02 and SEC-03 remain open until the proxy, network guard, real-browser tests, and exact-head review are complete. Live browsing remains disabled. No credentials, login, form submission, downloads, purchases, payments, trading, money movement, paid services, Auto-Run, firewall changes, or deployment are enabled. Android/Termux remains unqualified and denied.
