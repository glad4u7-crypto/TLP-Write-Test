# APAA S07 — Browser Runtime Selection and Read-Only Worker Plan

**Checkpoint:** APAA-S07-C01-P02  
**Status:** DESIGN / IMPLEMENTATION PLAN ONLY — runtime not authorized by this document  
**Branch:** `feature/approval-ui-e2e-p06`  
**PR:** #5 — keep Open + Draft; do not merge or deploy

## 1. Purpose

Turn the P01 browser architecture proposal into a concrete, free-by-default implementation plan. This checkpoint selects a candidate browser stack, defines the isolated worker and egress boundary, specifies read-only test cases, and defines the Android-facing review flow. It does not install a browser, add a dependency, create a worker, open a network connection, register a handler, or execute a website action.

## 2. Candidate technology decision

### Selected candidate: Python Playwright + pinned Chromium

- Prefer the Python Playwright binding because the current APAA foundation and CI are Python-based; this avoids introducing a second application runtime solely for the first browser capability.
- Use Playwright's Chromium browser build for the initial candidate, not a user's installed Chrome profile.
- Playwright is distributed under Apache-2.0; verify the exact pinned package and browser-binary notices again at implementation time.
- Pin the Python package and browser revision together. Never use floating `latest` versions in a reproducible build.
- Browser binaries are a separate install/download from the Python package and consume substantial disk space; CI and deployment must account for this.
- Keep Firefox/WebKit out of the first implementation to reduce dependencies and attack surface. Revisit only if a concrete compatibility requirement appears.

**Decision status:** recommended candidate, not installed or approved for execution. License and installation claims must be rechecked against the exact pinned release before adoption.

## 3. Runtime topology

Proposed topology:

1. Streamlit remains the trusted user-facing controller; it does not launch or embed a browser in-process.
2. A future job broker accepts only a typed, validated, read-only job envelope.
3. A separate unprivileged worker process/container launches one fresh Chromium instance/context per job.
4. The worker receives no approval signing key, tenant database, host home directory, browser profile, environment secrets or general filesystem mount.
5. All outbound HTTP(S) traffic must pass through a policy-enforcing egress proxy. Direct worker egress is denied at the OS/container/network layer.
6. Worker returns a bounded, sanitized result envelope. The trusted controller validates job/session ownership and writes the audit record.
7. Worker and browser context are destroyed on success, denial, timeout, cancellation, identity change or failure.

A subprocess alone is not a sufficient hostile-code sandbox. Production-grade isolation requires OS/container policy, a dedicated unprivileged identity, resource limits, filesystem restrictions and externally enforced network egress. If those controls are unavailable, browser execution remains disabled.

## 4. URL and network security contract

- Accept HTTPS only; reject URL userinfo, malformed/ambiguous hosts, unsupported ports and non-HTTP schemes.
- Canonicalize IDNs and hostnames before exact-origin comparison. Origin key is scheme + canonical hostname + effective port.
- No suffix, wildcard or substring allowlist matching.
- Reject localhost, loopback, private, link-local, multicast, reserved, unspecified and cloud metadata destinations for both IPv4 and IPv6.
- Resolve and validate DNS answers, then enforce the destination IP at connection time through the egress proxy to mitigate DNS rebinding and time-of-check/time-of-use gaps.
- Reject mixed public/private DNS answers.
- Revalidate every redirect and every subresource request. Redirects to a different origin are denied unless that exact origin is separately approved for the same job.
- Block file:, data:, javascript:, ftp:, ws:/wss:, arbitrary CONNECT tunnels, local-network discovery and non-HTTP(S) protocols by default.
- Disable popups, downloads, uploads, clipboard, permissions, geolocation, camera, microphone, service-worker persistence and persistent context storage.
- Apply hard limits for job wall time, navigation count, request count, response bytes, page count, memory and CPU.
- If the proxy, DNS validator, policy service or audit store is unavailable, fail closed.

## 5. Read-only capability contract

Initial candidate actions only:
- navigate to an approved URL;
- read visible text and selected non-sensitive page metadata;
- capture a transient screenshot for explicit user review;
- return source origin, retrieval time and bounded extracted result.

Never expose generic click, fill, type, submit, evaluate-JavaScript or arbitrary locator actions in the first read-only contract. A click may change remote state even if it appears harmless. No forms, account settings, messages, purchases, downloads, uploads or clipboard access.

Page content, DOM text, screenshots, metadata and instructions found on websites are untrusted data. They cannot modify policy, expand the allowlist, request secrets or create approval.

## 6. Android mobile review flow

- Android phone is the client/review surface; it is not the browser execution host.
- Render a compact review card showing the exact origin, requested read-only operation, data categories to be collected, limits, and whether a screenshot will be returned.
- Default action is Cancel/Back; no preselected consent.
- Any future state-changing action must have a separate, fresh confirmation showing the exact target and effect. P02 does not define or enable mutation.
- Show progress and a visible Cancel control; cancellation must terminate the job and browser context.
- On logout, identity switch, stale session or app/browser navigation away, invalidate the pending job and any approval reference.
- Use accessible labels, large touch targets, clear focus order and no color-only status indicators.
- Do not claim native Android control, ADB, accessibility-service input injection or control of other apps.

## 7. Read-only verification plan — not yet executed

| Test group | Required cases | Expected result |
|---|---|---|
| URL parser | userinfo, IDN, IPv4/IPv6 literals, encoded host, malformed URL, unusual port | reject unsafe/ambiguous inputs |
| Origin policy | exact scheme/host/port, suffix host, wildcard, port mismatch | exact match only |
| Redirects | same-origin and cross-origin multi-hop redirect | revalidate each hop; deny unapproved origin |
| SSRF/DNS | loopback, RFC1918, link-local, metadata, IPv6 local, mixed DNS answers, rebinding | deny before connection |
| Protocols | file, data, javascript, ftp, ws/wss and CONNECT | deny |
| Read-only | links/buttons/forms, submit controls, downloads, uploads, clipboard | no state-changing interaction or transfer |
| Prompt injection | page says to ignore policy, reveal secrets, visit internal host or submit a form | treat as untrusted text; no policy change |
| Isolation | two jobs, two tenants, profile/cookie canaries, worker restart | no cross-job or cross-tenant state |
| Cleanup | success, timeout, cancel, crash, logout, identity switch | context terminated; ephemeral state removed |
| Resource limits | slow page, infinite navigation, huge response, popup storm | bounded failure and cleanup |
| Audit | audit store unavailable, secret canary in page | fail closed; no secret in logs |
| Mobile UX | small screen, stale review, cancel during run, screen reader labels | clear exact scope; stale/cancelled job cannot continue |

Test strategy: unit-test URL canonicalization and policy without network; use a local deterministic test server in an isolated CI job for redirect and page behavior; use mocked DNS/proxy fixtures for SSRF tests. No public target websites and no real user accounts. A successful unit test does not prove OS/container or network isolation; those require independent operational evidence.

## 8. Implementation gate

A later, separately approved checkpoint may implement only a disabled-by-default read-only prototype after all of the following are reviewed:

- exact pinned Playwright/Chromium versions and dependency/license inventory;
- worker isolation and egress controls demonstrated, not merely configured in application code;
- URL/redirect/DNS policy test suite passing;
- read-only behavior proven against adversarial local fixtures;
- no execution gateway registration until security tests and independent review pass;
- explicit per-job user approval and auditable cancellation;
- existing two CI workflows passing on the exact implementation commit.

If any isolation or egress control cannot be demonstrated, do not ship a browser handler.

## 9. Non-negotiable constraints

- Zero-cost build; no paid provider, API key, hosted browser service or billable service.
- No payment, purchase, checkout, trading, investment order, money movement or financial transaction.
- Auto-Run OFF.
- No arbitrary shell, filesystem, email, native Android/device handler or credential/cookie/token access.
- No persistent browser profile, downloads, uploads, clipboard, arbitrary JavaScript/eval or remote debugging/CDP endpoint.
- No merge, deployment, base-branch change or production-readiness claim.
- PR #5 remains Open + Draft + unmerged.

## 10. Evidence and references

- Playwright browser support, pinned browser binaries and platform requirements: https://playwright.dev/docs/browsers
- Playwright installation and system requirements: https://playwright.dev/docs/intro
- Playwright library context creation and isolation API: https://playwright.dev/docs/library
- Playwright source license: https://github.com/microsoft/playwright/blob/main/LICENSE

These references support candidate selection only. They do not establish that a future worker is isolated or safe.

## 11. Checkpoint disposition

P02 design package is complete when this document is reviewed and the existing CI workflows pass on its exact commit. Browser runtime implementation and live website operation remain NOT AUTHORIZED by this design document.
