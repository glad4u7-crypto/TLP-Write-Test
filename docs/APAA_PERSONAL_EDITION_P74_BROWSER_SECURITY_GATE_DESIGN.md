# APAA Personal Edition — Browser Security Gate Design

**Checkpoint:** APAA-PERSONAL-P74  
**Status:** Security design and acceptance contract; browser execution remains DISABLED.

## Current safe disposition
The Personal Edition registers no Browser or Worker execution handler. This is intentional. Do not add a browser handler or expose browser controls until every mandatory gate below has an implementation, automated regression tests, and independent review. UI approval alone is not a security boundary.

## Required architecture
A future browser adapter must be isolated behind one policy-enforcing gateway. The planner/UI may submit intent but must not perform network I/O. The gateway owns the browser context, network policy, cancellation and audit lifecycle.

Required sequence:
1. Parse and canonicalize the requested URL.
2. Validate scheme, hostname, port and exact origin against an owner-configured allowlist.
3. Resolve and validate every destination address; reject loopback, private, link-local, multicast, reserved and otherwise non-public ranges.
4. Pin the validated destination and defend against DNS rebinding.
5. Create an isolated per-task context with no inherited owner cookies, credentials, extensions or profile state.
6. Revalidate every navigation and redirect before following.
7. Enforce network egress restrictions outside the browser process as well as in application policy.
8. Keep downloads/uploads disabled until size, MIME, path and content controls exist.
9. Support hard timeouts, cancellation, resource quotas and deterministic cleanup.
10. Persist metadata-only audit intent before dispatch; audit failure blocks dispatch.

## Mandatory security gates
| Gate | Required evidence | Failure disposition |
|---|---|---|
| Exact origin allowlist | Canonical origin parser; exact-match tests; no wildcard suffix confusion | Deny |
| URL parser safety | Reject userinfo, malformed IDN, ambiguous IP forms, unsupported schemes and unexpected ports | Deny |
| Redirect revalidation | Validate each redirect target; cap redirect count; reject downgrade | Stop |
| DNS rebinding | Validate at connection time, pin vetted address, test changing DNS answers | Deny |
| SSRF/private network | Reject IPv4/IPv6 loopback, RFC1918, link-local, ULA, multicast, reserved and metadata targets | Deny |
| TLS | Verify certificates and hostnames; no insecure bypass | Abort |
| Session isolation | New context per task; no cross-task cookies, storage or cache | Abort |
| Authentication | No credential scraping or implicit login; secrets require a separately approved vault design | Deny |
| Action scope | Typed, bounded actions; no arbitrary script execution | Deny |
| Upload/download | Disabled until path, size, MIME and content controls exist | Deny |
| Egress enforcement | Host/container/network policy prevents bypassing app checks | Deny |
| Cancellation/quotas | Hard deadline, request/page/resource caps and cleanup | Abort |
| Audit | Intent before dispatch; metadata-only outcome; audit outage blocks action | Deny |
| Prohibited actions | Payment, purchase, checkout, trading, investment order, money movement and paid-provider actions denied before approval | Deny |

## URL and address policy
- Allow HTTPS by default. HTTP remains denied unless a separately reviewed local-only profile is designed.
- Reject URL userinfo, control characters, backslashes, ambiguous numeric hosts, unsupported schemes and IPv6 zone identifiers.
- Canonicalize IDNs before allowlist comparison.
- Compare normalized scheme, hostname and effective port tuples; never use substring or naive suffix matching.
- Reject non-global-unicast destinations, including IPv4-mapped IPv6 forms.
- Revalidate after every redirect and DNS change. Never permit access to metadata endpoints, localhost, private LAN devices or APAA control-plane endpoints.

## Approval and audit contract
Every browser task needs a human-readable preview of origin, action type, target and data-flow. Approval binds canonical request digest, owner tenant, session, expiry and one-time nonce. Any changed URL, form payload, upload or action requires fresh approval. Auto-Run remains OFF.

Audit excludes page content, passwords, cookies, tokens, form values and file contents. Store only action identifiers, safe normalized origin, correlation ID, policy decision, reason code, timestamps and outcome. Audit intent failure blocks network dispatch.

## Release gate
Browser execution stays DISABLED until all gates have implementation and tests; the browser process is sandboxed; network egress is restricted outside the application; tests cover redirects, DNS rebinding, IPv4/IPv6 edge cases, metadata IPs, session leakage, cancellation and audit failure; independent review signs off the exact tested commit; and the owner explicitly approves enabling it.

This is a design contract, not evidence that a browser runtime exists or is safe. No Browser or Worker handler is enabled.


## P74 implementation progress — policy layer

The repository now contains an offline browser policy module at `core/browser_security.py`. It is deliberately not wired to a browser process or registered as an ExecutionGateway handler.

Implemented policy primitives:
- Canonical HTTPS URL parsing, IDNA hostname normalization, strict authority/port parsing and rejection of credentials, control characters, backslashes, unsupported schemes and ambiguous numeric IP spellings.
- Exact normalized origin matching; no wildcard or suffix matching.
- Blocking of private, loopback, link-local, multicast, reserved and non-public IP literals, plus local-use/reserved DNS suffixes.
- Strict DNS answer validation that rejects an entire mixed public/private answer set.
- `validate_live_destination`, which requires an injected trusted resolver for DNS names and returns the complete validated address set as `PinnedDestination`. A future connector must connect only to those returned addresses and must not resolve again.
- `validate_redirect_chain`, which revalidates every hop, pins every hop's DNS answer set, enforces a bounded hop count and rejects loops.
- Closed-schema, short-lived, bounded, read-only browser job envelopes; arbitrary script, click, form, upload, download, shell and financial action types remain rejected.

Regression tests were added for reserved suffixes, mandatory live DNS resolution, public-address pinning, mixed-answer rejection, per-hop redirect re-resolution, redirect loops and hop limits.

**Important limitation:** the policy module cannot enforce socket-level DNS pinning, TLS hostname verification, egress firewall rules, browser sandboxing or process isolation by itself. Those remain mandatory before any real browser adapter can be implemented or enabled. Offline `validate_destination` remains useful for deterministic tests; live code must call `validate_live_destination` and pass the returned pinned addresses into a separately reviewed connector.
