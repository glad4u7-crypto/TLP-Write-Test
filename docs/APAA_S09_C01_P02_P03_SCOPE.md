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
