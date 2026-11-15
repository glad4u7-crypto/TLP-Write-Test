# APAA S07 — P03 Browser Security Policy Core

**Checkpoint:** APAA-S07-C01-P03  
**Disposition:** OFFLINE POLICY IMPLEMENTATION ONLY  
**Browser runtime:** NOT IMPLEMENTED / NOT INSTALLED  
**Live network access:** NOT USED

## Implemented components

- `core/browser_security.py` provides HTTPS URL canonicalization, exact-origin allowlist enforcement, injected DNS-answer validation, per-hop redirect validation, and strict immutable browser-job parsing.
- `tests/test_browser_security.py` provides deterministic offline regression fixtures for URL parsing, IDNA, ports, userinfo, protocol confusion, localhost/private/reserved IPs, exact-origin bypass attempts, mixed DNS answers, resolver failure, redirect escapes, job schema, action allowlisting, expiry, resource caps, and absence of implicit DNS/network calls.
- Only the closed read-only action identifiers in the P01 contract are accepted: `navigate_exact_origin`, `read_visible_text`, `read_page_title`, `read_link_metadata`, and `capture_transient_screenshot`.
- Generic click/fill/type/submit, JavaScript/eval, download/upload, clipboard, shell, payment, trading and unknown actions are rejected.

## Security behavior

1. HTTPS is mandatory. Non-HTTP(S) protocols, userinfo, control characters, backslashes, malformed authorities, invalid ports and malformed hostnames are rejected.
2. DNS hostnames are normalized to lowercase ASCII IDNA form. IP literals must be globally routable; localhost, private, link-local, loopback, reserved, multicast and other non-global literals are denied.
3. Origin matching is exact across scheme, normalized hostname and effective port. No wildcard, suffix, substring or implicit subdomain matching exists.
4. Every redirect target is resolved and passed through the same destination/origin checks. A redirect to a different origin is denied unless that exact origin was already explicitly allowlisted.
5. DNS answer validation is deterministic and injectable. All returned addresses must be globally routable; empty, malformed, mixed public/private and resolver-error cases fail closed.
6. Job envelopes use a closed field set. Unknown/missing fields, unknown actions, invalid IDs, expired/overlong expiry, duplicate origins and out-of-range resource limits are rejected.
7. Validation performs no DNS lookup, HTTP request, browser launch or filesystem operation. Tests can supply deterministic resolver fixtures.

## Important deployment limitation

Offline DNS-answer validation is **not** a network security boundary. A future worker must use a fail-closed egress proxy/firewall that resolves and validates every destination at connection time, pins the validated address for the connection, rechecks every redirect, blocks private/reserved/metadata ranges, and prevents direct worker egress. This is required to address DNS rebinding and time-of-check/time-of-use races. No such proxy, firewall, worker isolation or packet-level evidence is included in P03.

The module is policy groundwork only. It is not registered with `ExecutionGateway`, does not create a browser handler, does not authorize browser execution, and must not be interpreted as permission to browse arbitrary sites.

## Verification scope

- Run the complete existing pytest suite and both existing CI workflows on the exact final commit.
- No new CI workflow is added.
- A CI pass validates code and deterministic offline tests only; it does not prove live network egress enforcement, container isolation, browser behavior or Android device usability.

## Unchanged safety boundaries

- Free-only default; no paid APIs, providers, API keys or charges.
- Auto-Run OFF; default permission remains Ask First.
- No payment, purchase, checkout, trading, investment orders or money movement.
- No credential, cookie, token, browser profile, CDP, shell, arbitrary filesystem or native device access.
- PR #5 remains Open + Draft + unmerged. No merge or deployment.
