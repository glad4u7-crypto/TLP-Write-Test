# APAA S07 — Browser Automation Architecture Proposal

**Checkpoint:** APAA-S07-C01-P01  
**Status:** DESIGN PROPOSAL ONLY — NOT IMPLEMENTED  
**Authorization:** User requested the S07 architecture and threat-model work on 2026-11-15. This authorizes design/documentation only.  
**Branch:** `feature/approval-ui-e2e-p06`  
**PR:** #5 — Open, Draft, unmerged

## 1. Purpose and boundary

Define a safe, zero-cost-by-default architecture for a future browser automation capability that can inspect approved websites and perform narrowly scoped user-authorized interactions. This document does not add browser dependencies, handlers, browser sessions, network access, device control or execution capability.

The current application remains a Streamlit web prototype. A future browser runner must be a separately isolated service/process; it must not be embedded as an unrestricted capability in the Streamlit process.

## 2. Proposed component model

```text
User (explicit request)
        |
        v
Task Workspace / trusted UI
        |
        v
Structured Planner (untrusted plan proposal)
        |
        v
Policy Gate + URL/Action Validator
        |                         \
        | deny / clarify            | narrowly allowed request
        v                           v
Read-only result              Approval Broker (trusted UI only)
                                      |
                                      v
                             Browser Job Broker
                                      |
                                      v
                       Isolated ephemeral browser worker
                                      |
                          constrained egress proxy
                                      |
                               approved origins
                                      |
                                      v
                           redacted result + audit
```

Every arrow is a proposed interface, not a current runtime connection.

### 2.1 Task Workspace and planner

- User instructions, planner output, page text, DOM attributes, screenshots, downloaded metadata and website-provided instructions are untrusted data.
- Planner output is a proposal only. It cannot issue approvals, select arbitrary handlers, override policy or directly invoke a browser.
- A plan must identify the requested origin(s), read-only vs mutation intent, expected data, and each proposed browser action in typed fields.
- Ambiguous targets or actions require clarification; uncertain policy classification must deny or ask rather than infer permission.

### 2.2 Policy Gate

- Enforce a server-side, deny-by-default action policy independent of model/planner output.
- Canonicalize and validate URL scheme, hostname, port, IDN representation, redirects and resolved IP addresses.
- Allow only HTTPS origins explicitly approved for the task. Exact-origin matching means scheme + canonical hostname + effective port; no suffix/wildcard host matching.
- Reject URL credentials, unsupported schemes, malformed/ambiguous hosts, IP literals unless separately reviewed, localhost, loopback, link-local, private, multicast, reserved and metadata-service destinations.
- Revalidate every redirect and every navigation/request. DNS rebinding and mixed public/private DNS answers must fail closed.
- Deny cross-origin navigation, popups and subresource requests unless explicitly permitted by a separately reviewed policy.
- Never rely on UI hiding or client-side checks as the security boundary.

### 2.3 Approval Broker

- Approval is performed only by trusted application UI/controller code, never by page content, planner output or browser worker.
- Any future mutating action requires a fresh, action-specific confirmation showing the exact origin, action, target, relevant field/value summary and expected effect.
- The approval token must bind the exact canonical action, exact origin, exact target and payload digest, user/tenant, session, job ID, expiry and one-time nonce.
- Any change to the page state, destination, target, action or payload invalidates the approval and requires a new preview/confirmation.
- Short expiry, atomic single-use consumption, replay rejection and durable intent audit are mandatory.
- No blanket approval for a site, session, workflow or future actions. Auto-Run remains OFF and empty.

### 2.4 Browser Job Broker and isolated worker

- Run one job per fresh ephemeral browser context/profile. Never attach to the user's normal browser profile or import its cookies, passwords, extensions or history.
- Separate worker process/container and unprivileged OS identity; no host home-directory mounts, Docker socket, SSH agent, cloud credentials, secrets directory or broad filesystem access.
- No externally reachable Chrome DevTools Protocol (CDP), remote debugging port or browser-control endpoint.
- Worker receives only a short-lived, narrowly scoped job capability. It cannot access ApprovalAuthority, signing secrets, tenant database or unrestricted audit storage.
- Enforce CPU, memory, wall-clock, navigation, request-count and response-size limits.
- Terminate the context and erase ephemeral storage at job completion, cancellation, timeout or identity change.

### 2.5 Network egress proxy

- Browser worker has no direct unrestricted network egress. All requests pass through a policy-enforcing proxy/firewall.
- Re-check hostname resolution and destination IP at connection time; block private, loopback, link-local, reserved and metadata endpoints, including IPv4 and IPv6 forms.
- Revalidate redirects, DNS answers, ports and schemes for every hop/request.
- Block non-HTTP(S) protocols, WebSocket by default, arbitrary CONNECT tunnels, local-network discovery and service access.
- Egress allowlists are exact-origin and job-scoped, expire with the job, and are not user-editable from page content.

### 2.6 Browser interaction surface

Proposed initial capability tiers:

1. **Tier R — Read-only:** navigate approved pages, extract visible text and metadata, capture transient screenshot for user review. No form submission, upload, download, clipboard or state-changing click.
2. **Tier M — Explicit mutation:** only a future separately approved allowlist of low-risk, reversible actions. Exact action preview and fresh confirmation are mandatory.
3. **Tier X — Prohibited:** payments, purchases, checkout, trading, investment orders, money movement, credential changes, security settings, account deletion, legal acceptance, sending messages/emails, and any financial transaction. These are outside APAA's permitted action scope.

S07 does not enable any tier. Tier R is the only candidate for a future first implementation, after design review and acceptance tests.

### 2.7 Results and audit

- Return only the minimum requested data; label source origin and retrieval time.
- Treat page content as untrusted evidence, not instructions.
- Do not persist page screenshots, cookies, DOM snapshots or raw form contents by default.
- Audit only necessary metadata: job ID, tenant/principal fingerprint, approved origin, action category, policy decision, approval reference, timestamps, result code and failure reason code.
- Never log passwords, cookies, access tokens, raw page bodies, full form values or sensitive query strings.
- If intent audit cannot be durably written before a future side effect, block that action. If completion audit fails after an action, surface an explicit manual-review state.

## 3. Trust boundaries

| Boundary | Trusted side | Untrusted side | Required control |
|---|---|---|---|
| User request | authenticated user identity | free-form task text | typed intake, clarification |
| Planner | trusted planner code | generated plan fields | independent policy validation |
| Web origin | approved origin registry | website content/DOM | exact-origin allowlist |
| Approval | trusted UI/controller | planner/page/worker | action-bound one-time receipt |
| Browser worker | constrained runtime | page scripts and resources | process/container isolation |
| Network | egress policy proxy | DNS, redirects, remote hosts | per-request destination enforcement |
| Audit | trusted audit writer | worker-supplied claims | server-derived metadata, durable intent |

## 4. Integration with current code

- `core.planner` remains deterministic and has no execution authority.
- `ApprovalAuthority` is a trusted application capability and must never be passed into planner, page context or browser worker.
- `ExecutionGateway` dispatches only explicitly registered handlers; a future browser handler must not be registered until the separate implementation gate is approved and all isolation tests pass.
- Existing tenant/session binding and durable nonce/audit mechanics are useful foundations but do not provide browser or OS process isolation.
- The current Streamlit process is not a security sandbox.

## 5. Required pre-implementation decisions

1. Select an isolated worker/container runtime compatible with the free-build constraint.
2. Define origin allowlist ownership and user-visible approval flow.
3. Select browser engine only after license, maintenance, supply-chain and Android-client compatibility review.
4. Decide supported authentication handoff without importing browser credentials or storing passwords.
5. Define deployment topology, egress firewall and operational ownership.
6. Decide what minimum result metadata may be retained and for how long.

No tool/library choice is made in this proposal.

## 6. Explicit non-goals

- No native Android device control, accessibility service, ADB, screen capture or input injection.
- No arbitrary JavaScript/eval, shell, local file browsing or direct API calls.
- No persistent browser profile, password vault, cookie import/export or credential scraping.
- No downloads or uploads in the initial design.
- No background/recurring browser jobs, scheduler, queue or retry loop.
- No paid API/provider, API key or billable service.
- No payment, purchase, checkout, trading, money movement or financial actions.
- No implementation, handler registration, deployment, merge or PR promotion.

## 7. Decision

**S07-C01-P01 delivers a design proposal only.** A separate explicit user approval and a reviewed implementation scope are required before any browser capability is coded or enabled.
