# APAA P78 — Real Read-only Network Providers

## Provider status
Implemented in `core/safe_network_providers.py` using Python standard-library networking only (no API key, third-party package, browser, cookie jar, or proxy).

- **Web Search:** DuckDuckGo public HTML search endpoint. Parses result titles and external HTTPS links.
- **HTTPS Page Read:** Fetches one Owner-requested public HTTPS page, then extracts visible title/text. HTML scripts, forms, styles, frames, and SVG are not executed or returned.
- **YouTube Search:** Reads public YouTube search HTML and extracts public video IDs/titles. No login, playlist, subscription, comment, upload, or account mutation.

## Network safety controls
- Direct TCP connection to a DNS-resolved IP; no proxy environment is used.
- All DNS answers must be globally routable. Private, loopback, link-local, multicast, reserved, and mixed public/private answer sets are rejected.
- Connects to the validated IP while retaining TLS SNI and certificate hostname verification for the requested hostname.
- HTTPS only; default port only; no URL credentials or IP-literal hosts.
- Redirects are manual, capped at three, and revalidated. Search and YouTube redirects must stay on their fixed provider host.
- Bounded connect/read timeout, 1 MB response limit, identity encoding only, bounded result count, and strict HTML/text content-type checks.
- No cookies, auth headers, browser automation, JavaScript execution, arbitrary methods, or write methods.

## Limitations / residual risk
- Public HTML pages change format and may rate-limit, challenge, or block automated requests. DuckDuckGo and YouTube markup are not stable APIs.
- DNS pinning protects the direct connection from DNS rebinding between validation and connect; network-layer egress controls are still recommended in deployment.
- Public page fetch can access any globally routable HTTPS hostname, subject to DNS/IP checks. Redirects are revalidated at every hop.
- No guarantee of availability, completeness, freshness, or legal right to scrape. Respect provider terms and robots policies before production rollout.
- Provider responses are untrusted content; do not interpret page text as agent instructions.

## Activation
Providers are concrete classes but are not auto-registered into the application or ExecutionGateway. They must be explicitly registered by the Owner-controlled read-only registry. No paid service or API key is required.
