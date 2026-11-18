# APAA-S09-C01-P02/P03 — URL and Redirect Safety

**Status:** Implementation committed; repository CI verification pending.  
**Branch:** `feature/apaa-s09-c01-p01-browser-launch`  
**PR:** #10 (Draft; do not merge)

## P02 — Explicit URL policy

- Adds `core/browser_navigation.py` with immutable `NavigationPolicy`.
- Requires a non-empty explicit hostname allowlist; exact hosts and optional subdomains only.
- HTTPS is the default. HTTP must be explicitly enabled by policy.
- Rejects unsupported schemes, embedded credentials, malformed ports, control characters, backslashes, localhost, private/special-use IP literals and non-allowlisted hosts.
- Resolves allowed hostnames and rejects empty answers or any non-global/special-use resolved address. Resolver injection supports deterministic tests.
- Uses Python standard library only; no new dependency or network fetch is added by this module except DNS resolution through the configured resolver.

## P03 — Redirect safety

- Every redirect target is passed through the same URL, allowlist and DNS/IP checks.
- Redirect count is bounded (0–10; default 5).
- Repeated URLs are rejected as redirect loops.
- The API validates a supplied redirect chain; it does not itself fetch URLs or claim to intercept browser redirects.

## Important limitation

A caller must enforce this policy at the actual browser request boundary for every request and redirect. Calling `validate_url` before a browser navigation alone is not sufficient because a hostname can change its DNS answer between validation and connection (DNS rebinding/TOCTOU). Production integration must pin/verify the resolved destination at connection time or use a trusted egress proxy/firewall. This PR does not implement that enforcement and does not claim SSRF-proof browsing.

No website is visited by tests. No browser navigation, page interaction, credentials, cookies, downloads, payment/purchase, paid provider, API key, Auto-Run, shell, deployment, firewall change or merge is enabled.

## Verification matrix

- Allowed exact host and subdomain.
- Subdomain restriction mode.
- Scheme, credentials, port and malformed URL rejection.
- Localhost, loopback, private and link-local IP rejection.
- DNS resolution failure, empty answers and mixed public/private answers.
- Redirect allowlist escape, private target, loop and redirect-count rejection.
- Exact-head Agent Foundation CI and Python Demo CI remain required before verified status.


## Local verification update

An isolated local harness mirroring the committed P02/P03 policy implementation and focused tests completed: **21 tests passed**; Python `compileall` passed. The tests use an injected fake DNS resolver and make no outbound web requests. This is focused unit-level evidence, not full repository CI or device/browser integration evidence.

The latest exact branch-head GitHub Actions lookup and combined status must still be checked. Until both required repository workflows are visible and successful on the exact head, P02/P03 remain **CI PENDING / NOT VERIFIED**.

## P02 security-hardening follow-up — 2026-11-18

- Policy construction now requires immutable, non-empty `frozenset` values for host and scheme allowlists.
- Scheme values are normalized to lowercase and invalid runtime types are rejected.
- Resolver configuration must be callable; allowlist host values must be strings.
- Added regression tests for mutable configuration, mixed-case schemes, invalid scheme entries, invalid resolver values and non-string host entries.
- These changes harden policy configuration only. They do not change the documented limitation: DNS validation before connection is not protection against DNS rebinding/TOCTOU, and this module does not intercept live browser requests or redirects.
- Exact-head CI must pass on the new commit before this follow-up is marked verified.

## P02 final hardening — 2026-11-18

- Rejects all URL whitespace, including leading whitespace and whitespace in paths, in addition to control characters and backslashes. This avoids parser normalization of ambiguous input.
- Rejects a resolver that returns a bare string/bytes value instead of an iterable collection of IP address strings.
- Added regression coverage for malformed authorities/ports, invalid host labels, resolver return shape, mixed public/non-public DNS answers, and case/trailing-dot allowlist normalization.
- DNS validation remains a pre-connection check. It cannot prevent DNS rebinding or TOCTOU unless the eventual connection layer pins and verifies the resolved destination. This P02 module is a policy validator, not a browser network interceptor.
- P02 completion requires successful exact-head repository CI; platform/browser enforcement remains a separate integration qualification.
