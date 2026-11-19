# APAA Browser Automation — Production Architecture and Trust Boundaries

**Roadmap:** APAA → S09 Browser Automation → C01 Browser Foundation  
**Status:** Architecture specification / implementation map. This document is not a production-readiness claim or authorization to enable Browser/Worker.

## 1. System objective

APAA accepts an Owner's natural-language task, converts it into a bounded action plan, obtains the required authorization, executes only through a policy-controlled browser worker, and returns evidence-backed results. The browser is an execution tool, not an authority source. A page, DOM node, downloaded document, or website instruction can never grant APAA permission or override Owner policy.

## 2. Trust domains

1. **Owner interface and identity** — authenticated Owner session, explicit task submission, approval prompts, cancellation and result display. No anonymous/public access by default.
2. **Planner / task orchestrator** — translates intent into a typed, bounded job. It may propose actions but cannot create approvals or dispatch privileged work.
3. **Policy and authorization boundary** — checks Owner identity, session/tenant binding, allowed origin, action class, risk limits, expiry, replay protection and explicit approval. Ask First is the default for sensitive actions. Auto-Run stays OFF.
4. **Evidence and locator boundary** — captures fresh page/origin/element evidence, redacts sensitive values and binds any action to the exact job and page state. Page content is untrusted input.
5. **Browser controller** — owns browser lifecycle and typed operations. It must not expose arbitrary shell, arbitrary Playwright evaluation, persistent profiles, raw CDP, downloads, or unrestricted launch arguments.
6. **Isolated worker backend** — provisions one ephemeral non-root worker per job using immutable image identity, dedicated namespaces, read-only root, no capabilities, seccomp, no-new-privileges and bounded CPU/RAM/PIDs. The controller must not treat a test fake or local Chromium process as this boundary.
7. **Runtime observer and attestor** — obtains fresh observations from the actual runtime and network namespace, validates them against the immutable launch specification, signs the evidence, consumes a one-time challenge and rejects stale/replayed/mismatched evidence.
8. **Network boundary and proxy** — worker egress is default-DROP for IPv4 and IPv6. Only the exact pinned proxy endpoint is allowed. DNS resolution and destination pinning occur at the proxy; browser traffic retains end-to-end TLS/SNI/certificate validation. Direct TCP, DNS, UDP/QUIC, alternate-route and proxy-outage fallback must fail.
9. **Recovery, audit and result boundary** — persists job lifecycle, idempotency/replay state, cancellation, crash/timeout/orphan outcomes and redacted audit evidence. Unknown execution outcome is not reported as success; cleanup must be confirmed.
10. **Owner acceptance / release control** — independent review, evidence-bundle review, backup/restore drill and explicit Owner acceptance precede any narrowly scoped capability enablement.

## 3. Authorized execution sequence

```mermaid
sequenceDiagram
    participant O as Owner
    participant P as Planner
    participant G as Policy / Approval Gate
    participant E as Evidence + Locator
    participant C as Browser Controller
    participant W as Isolated Worker Backend
    participant A as Attestor / Runtime Observer
    participant N as Pinned Proxy + Egress
    participant R as Recovery + Audit

    O->>P: Natural-language task
    P->>G: Typed bounded job proposal
    G->>G: Owner/session/origin/action/risk/replay checks
    G-->>O: Ask First approval when required
    O->>G: Fresh explicit approval
    G->>E: Request fresh page/element evidence
    E->>C: Validated target + origin evidence
    C->>W: Provision ephemeral worker from immutable spec
    W->>A: Runtime handle for independent observation
    A->>A: Verify runtime, namespace, cgroup, seccomp, nftables, proxy pins
    A-->>C: Signed fresh one-time attestation
    C->>W: Start browser only after attestation passes
    W->>N: Browser traffic through pinned proxy only
    N-->>W: Allowed HTTPS response; TLS remains browser-verified
    C->>G: Re-check approval + evidence before each sensitive action
    C->>R: Persist transitions and redacted evidence
    W->>R: Confirm process exit and ephemeral storage cleanup
    R-->>O: Evidence-backed result or explicit failure/unknown outcome
```

## 4. Mandatory invariants

- Owner identity, project/tenant and session are bound to each job and approval.
- An approval is fresh, one-time, action-specific, origin-specific and tied to a canonical job fingerprint. It cannot be replayed for another job.
- Navigation, DOM inspection and interaction are distinct capabilities. Read-only inspection never implies permission to click, fill, submit, upload or download.
- Website text, DOM attributes, accessibility labels, screenshots and network responses are untrusted data, not instructions.
- No persistent personal browser profile, cookies, credentials, password extraction or production-account testing.
- No payment, purchase, checkout, trading, money movement or paid provider/API provisioning.
- No arbitrary shell, host firewall mutation on a personal device, or automatic device permission/settings changes.
- No direct worker egress, DNS/UDP/QUIC fallback, broad proxy listener, or weakened sandbox as a workaround.
- Cancellation and cleanup are part of the job result. Failure to confirm termination/deletion is a failed cleanup state.
- Browser/Worker dispatch stays disabled until all external and Owner gates pass.

## 5. Current implementation map

| Layer | Repository evidence | Current status |
|---|---|---|
| Owner / application identity | Personal Runtime, Owner-bound browser approval boundary | Foundation exists; production UI/release acceptance remains separate |
| Planner / policy / approval | Browser control, offline intent/evidence and action-history components | Partial; offline evidence does not authorize live execution |
| Browser launch | `core/browser_launch.py` | Bounded launch/fresh context; local launch is not OS isolation |
| Navigation / request policy | `core/browser_navigation.py`, `core/safe_navigation.py` | Policy components/tests exist; full live hostile-traffic qualification remains |
| Read-only inspection | `core/live_browsing.py`, DOM inspector | Controller-side cap and inspection foundations exist; fresh live evidence integration remains gated |
| Recovery / audit | `core/browser_recovery.py`, audit components | Durable lifecycle/idempotency foundations exist; end-to-end worker recovery needs qualification |
| OCI primitives | `core/oci_runtime_backend.py`, namespace, cgroup, nftables and proxy provisioners | Provisioning primitives and disposable-host harness exist |
| Production worker backend | `core/browser_worker_adapter.py` defines an injected backend protocol | **Incomplete:** no independently qualified production backend is selected/wired |
| Runtime observer / attestation | `core/oci_runtime_observer.py`, `core/linux_browser_host_inspector.py`, `core/browser_nftables.py` | Components exist; exact production provider/schema/host integration remains |
| Key/challenge lifecycle | `core/attestation_keyring.py`, `core/attestation_challenge_ledger.py` | Local keyring and durable challenge ledger code exist; deployment custody/rotation/restore proof remains |
| Chromium runtime | P74 disposable OCI Chromium | **FAILED / NO-GO:** FD ownership violation reproduced; exact FD/call site/root cause unresolved |
| Network containment | Dual-stack nftables and pinned proxy components | Code/tests exist; actual worker qualification is not accepted |
| Android | `core/runtime_support.py`, P07 compatibility record | Browser launch intentionally fails closed on Android/Termux; no physical device qualification |
| Release | Independent review, evidence bundle, backup/restore and Owner acceptance | **Not complete** |

## 6. Failure semantics

- Missing or stale Owner approval → reject before dispatch.
- Missing/mismatched attestation, namespace, image, cgroup, seccomp, firewall or proxy pin → do not start browser.
- Direct-egress probe succeeds or packet capture sees non-proxy worker traffic → qualification failure / NO-GO.
- Browser crash, ambiguous action result, cancellation timeout or unconfirmed cleanup → persist explicit failed/unknown state; never silently retry a non-idempotent action.
- Evidence redaction or audit-integrity failure → do not return a success result.
- Unsupported Android runtime → fail closed; do not bypass the platform guard.

## 7. Release gates (must be independently evidenced)

1. Resolve Chromium FD failure using an instrumented binary matching the exact runtime build; identify the actual FD, operation, PID/TID and causal source path.
2. Add a Chromium-native deterministic regression and pass repeated cold-start tests.
3. Wire a real production `IsolatedWorkerBackend` and trusted runtime observation provider to the immutable `WorkerLaunchSpec`.
4. Verify host-inspector schema against actual dual-stack nftables output and complete attestor key custody, rotation, freshness and durable replay protection.
5. Pass disposable-host Chromium, hostile-network, TLS, crash, timeout, orphan, restart and cleanup qualification with reviewed artifacts.
6. Complete independent security review, Owner backup/restore drill and explicit Owner acceptance.
7. Only then consider a narrowly scoped enablement; no enablement is implied by this architecture document.

**Current decision:** Browser/Worker DISABLED, Auto-Run OFF, Ask First, no merge/deployment/production activation. This architecture is the target design; the implementation map above is the honest current state.
