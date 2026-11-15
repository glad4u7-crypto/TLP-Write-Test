# APAA-S09-C01 — Separate Security Review

**Review type:** Static design/code review only  
**Review status:** BLOCKED — not approved for live browsing  
**Reviewed branch:** `feature/apaa-s09-c01-p01-browser-launch`  
**Reviewed scope:** P01 browser launch, P02 URL policy, P03 redirect-chain validation, P04 page-route integration, P05 egress authorization contract, P06 context-route integration and service-worker blocking

## Positive controls observed

- Browser launch uses a fresh non-persistent context, disables downloads, and blocks service workers.
- Launch configuration is bounded and does not expose arbitrary executable paths or launch arguments.
- URL policy requires an explicit hostname allowlist and defaults to HTTPS.
- URL validation rejects credentials, unsupported schemes, localhost, private/special-use IPs and non-allowlisted hosts.
- Redirect-chain helper bounds hops and rejects loops.
- P04 validates the initial URL and page-routed requests. P06 adds a context-level route path when both context and page are supplied; legacy page-only construction remains page-scoped.
- P04 removes its temporary route in a `finally` block.
- The reviewed modules do not themselves install packages, visit websites, perform login, submit forms, or initiate payments.

## Blocking findings

### SEC-01 — DNS rebinding / TOCTOU remains possible

**Severity:** High  
**Evidence:** `NavigationPolicy.validate_url` resolves and checks addresses before Playwright opens the connection. The browser performs its own resolution/connection later; the validated address is not pinned to the socket.  
**Required remediation:** Enforce destination IP policy at connection time using a trusted egress proxy or equivalent network boundary that resolves, validates and connects atomically. Revalidate every redirect and subresource at that boundary.

### SEC-02 — Playwright routing is not a complete network boundary

**Severity:** High  
**Evidence:** P04 uses `page.route("**/*", ...)`. This does not establish controls for all context/browser traffic, service-worker traffic, WebSockets, browser background traffic or traffic outside the page.  
**Required remediation:** Implement and independently test a trusted transport-level egress boundary that governs actual connections, WebSockets, redirects and subresources. Keep service workers blocked unless a separately reviewed design is approved.

### SEC-03 — No exact-head CI evidence

**Severity:** Medium  
**Evidence:** Workflow lookup for the P06 scope-document commit returned no workflow runs. No exact-head passing test result was available during this review.  
**Required remediation:** Run the repository's required test workflows on the final branch head and retain their run IDs and passing job results.

### SEC-04 — Android/Termux runtime is not qualified

**Severity:** Medium  
**Evidence:** P07 adds conservative Android/Termux detection and blocks the Playwright launch path on detected Android runtimes. No physical-device test evidence exists; non-Android hosts also require local Playwright/browser validation.  
**Required remediation:** Keep Android browser automation disabled until a controlled, non-production device compatibility test and independent security review are completed. Python-only functionality may be evaluated separately.

## Decision

**Do not enable live browsing or untrusted-site access.** P01–P07 are implementation artifacts with unit tests authored, but no exact-head passing CI evidence or operational transport-level egress boundary exists. The browser control chapter is not security-approved and must not be described as production-ready.

No firewall, proxy, device permission, deployment, live website, authenticated browser profile, Auto-Run, payment/purchase, paid API or PR merge was changed or used by this review.
