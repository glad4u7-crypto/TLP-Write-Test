# APAA S07 — Browser Automation Threat Model

**Checkpoint:** APAA-S07-C01-P01  
**Status:** DESIGN / THREAT ANALYSIS ONLY — NOT IMPLEMENTED  
**Scope:** Future isolated browser automation; current application has no browser handler.

## 1. Assets to protect

- User identity, tenant boundaries and active session.
- Authentication cookies, access tokens, passwords and account recovery data.
- User task instructions, private content and retrieved page data.
- Approval signing secret, one-time nonces and execution authority.
- Host filesystem, environment variables, network, local services and cloud metadata.
- Integrity of user-approved action, target, payload and destination.
- Audit integrity, availability and incident evidence.

## 2. Adversaries and unsafe inputs

- Malicious or compromised websites and third-party scripts.
- Prompt injection embedded in page text, images, metadata, DOM, PDFs or search results.
- Malicious redirects, open redirects, deceptive links and homograph domains.
- DNS rebinding, malicious DNS responses and SSRF-style URL tricks.
- Cross-site scripting, CSRF, clickjacking and UI redress.
- A compromised browser renderer or vulnerable browser dependency.
- A malicious/buggy planner, stale plan, confused deputy or unauthorized tenant.
- Local co-tenants or processes attempting to read browser data or control the worker.
- Supply-chain compromise of browser binaries, drivers, plugins or dependencies.
- Denial-of-service through huge pages, loops, popups, downloads or resource exhaustion.

## 3. Threat analysis

| ID | Threat / attack path | Impact | Required mitigation | Verification evidence required |
|---|---|---|---|---|
| T01 | Page prompt injection instructs agent to reveal secrets or take another action | data exfiltration / unauthorized action | page text is data only; strict tool boundary; planner cannot approve or dispatch | adversarial page corpus; secret canary non-disclosure tests |
| T02 | Redirect or link leaves approved site | unauthorized origin access | exact-origin allowlist; validate every redirect and navigation | redirect-chain tests across scheme, host and port changes |
| T03 | DNS rebinding or private-IP resolution | SSRF, local service/metadata access | resolve and pin destination at connection; reject private/reserved IPv4/IPv6; proxy enforcement | rebinding and mixed-answer integration tests |
| T04 | URL parser confusion, IDN homograph, userinfo, encoded host | allowlist bypass | canonical parser; reject userinfo, malformed hosts, ambiguous encodings; IDNA normalization | parser fuzzing and adversarial URL suite |
| T05 | CSRF, clickjacking or deceptive page UI | unintended mutation | no state-changing action in read-only tier; action preview; origin and target binding; fresh confirmation | CSRF/clickjacking fixture and mutation approval tests |
| T06 | Approval replay, theft or stale approval | repeated or altered action | one-time nonce, short TTL, payload/origin/target/session/job binding; atomic consume | replay, expiry, payload mutation and concurrent consume tests |
| T07 | Time-of-check/time-of-use page change after approval | approval applied to different action | bind preview state; re-read target and payload immediately before dispatch; invalidate on change | DOM mutation and navigation-after-confirmation tests |
| T08 | Browser worker reads host files, credentials or secrets | account/host compromise | isolated unprivileged worker; no host mounts; no secrets; filesystem/network sandbox | container escape-hardening review and host canary tests |
| T09 | Browser profile/cookie reuse across users or jobs | cross-tenant account access | fresh ephemeral context per job; no default-profile attachment; destroy after use | two-tenant cookie isolation and cleanup tests |
| T10 | Worker or page exfiltrates data through network channels | private data leakage | constrained egress proxy; exact origins; block arbitrary protocols, WebSocket and tunnels | packet-level egress tests and exfiltration fixtures |
| T11 | Malicious download or upload payload | malware, data leak, filesystem compromise | downloads/uploads disabled initially; no local file chooser access | attempts must be denied; no file written or read |
| T12 | Browser remote-debugging endpoint exposed | full browser control | no public CDP/debug port; worker-only private IPC | port scan and network reachability test |
| T13 | Cross-tenant job or result mix-up | confidentiality/integrity breach | tenant-bound job IDs, session-bound capability, server-side ownership checks | concurrent two-tenant isolation tests |
| T14 | Huge pages, infinite loops, popups or resource floods | worker exhaustion | hard CPU/memory/time/page/request/response limits; cancellation | deterministic resource-limit tests |
| T15 | Logs contain tokens, cookies or page data | credential exposure | metadata-only audit, redaction, no raw bodies or secrets | log scanning with canary secrets |
| T16 | Browser dependency or binary compromise | arbitrary code execution | pinned versions, signed provenance where available, dependency audit, update policy | SBOM, provenance and vulnerability review |
| T17 | Worker reports false success or fabricates action result | incorrect user belief | server-derived action lifecycle and evidence; result state distinct from browser text | forged-result and audit consistency tests |
| T18 | Audit backend unavailable before mutation | untracked side effect | fail closed before dispatch if durable intent audit unavailable | audit outage injection test |
| T19 | User instruction conflicts with global prohibited actions | financial or irreversible harm | global denylist outside planner; never override with approval | prohibited-intent and handler registration tests |
| T20 | Authentication expires or identity changes mid-job | cross-user execution | cancel job, revoke capability, destroy context on auth loss/identity change | mid-job logout, expiry and identity-switch tests |

## 4. STRIDE summary

- **Spoofing:** forged origin, tenant, approval or worker result. Mitigate with verified identity, origin canonicalization and server-issued job capabilities.
- **Tampering:** altered page target, payload, plan or approval. Mitigate with immutable action preview, digest binding, revalidation and one-time receipts.
- **Repudiation:** disputed action or missing evidence. Mitigate with metadata-only durable intent/completion audit and correlation IDs.
- **Information disclosure:** cookie, secret, local-file or cross-tenant leakage. Mitigate with ephemeral profiles, process isolation, egress restrictions and redaction.
- **Denial of service:** unbounded navigation, content or worker loops. Mitigate with strict resource/time quotas and cancellation.
- **Elevation of privilege:** prompt injection, arbitrary code, CDP or confused-deputy access. Mitigate with no eval, no CDP exposure, no authority in worker and independent policy gate.

## 5. Residual risks

- Browser engines and operating-system kernels remain complex attack surfaces; containerization is not a complete VM boundary.
- A legitimate approved website may change behavior after review; target revalidation reduces but cannot eliminate semantic ambiguity.
- Authentication state in a live browser is inherently sensitive even when ephemeral.
- Visual and DOM-based automation can misidentify controls; ambiguous/high-impact actions must stop for human review.
- A compromised host administrator can defeat local controls; independent operational controls remain necessary.
- This design does not close S04 operational blockers BY-01…BY-07.

## 6. Mandatory stop conditions

Immediately cancel and destroy the job context if:
- user identity changes, logs out or authentication expires;
- an unapproved origin, redirect, protocol or private destination is encountered;
- policy or approval verification fails;
- the target or payload changes after confirmation;
- durable intent audit cannot be written before a future side effect;
- worker integrity, isolation or egress enforcement is uncertain;
- prohibited financial, purchase, credential-change or irreversible action is requested.

## 7. Verification rule

No threat is considered mitigated merely because a document says so. Every control requires an automated test where feasible and independent deployment evidence for host/network controls. S07 currently has no browser runtime and no browser-control tests; all rows are design requirements, not passes.
