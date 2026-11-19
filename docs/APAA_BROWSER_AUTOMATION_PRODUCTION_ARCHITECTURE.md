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


## 8. Component contracts and ownership boundaries

The following contracts are normative. An implementation that cannot satisfy a contract must fail closed and must not be substituted by a test fake in a production configuration.

| Component | Owns | May do | Must never do |
|---|---|---|---|
| Owner/API boundary | authenticated Owner and session identity | accept task, show approval, cancel, display result | expose anonymous/public dispatch or infer approval |
| Planner | typed proposal | decompose intent into bounded steps | mint approvals, select secrets, bypass policy |
| Policy/approval service | policy decision and approval receipt | bind Owner, tenant, session, origin, action, expiry and canonical fingerprint | trust page instructions or reuse a receipt |
| Evidence collector | fresh page/target evidence | inspect visible metadata and redact | infer hidden values or authorize actions |
| Browser controller | typed browser operations | navigate, inspect, execute an approved operation | arbitrary code evaluation, shell, raw CDP, unrestricted launch flags |
| Worker adapter | one job's worker lifecycle | provision, attest, start after gate, terminate and destroy | construct synthetic host evidence or start before attestation |
| Runtime provider | observed OCI process/container facts | read runtime identity and effective settings | accept worker-reported values as host truth |
| Network provider | observed namespace and effective firewall | collect exact nftables JSON and namespace identity | mutate host networking during evidence collection |
| Attestor | signed, fresh, challenge-bound evidence | verify and sign approved schema | reuse challenge, accept stale evidence, self-authorize a runtime |
| Recovery/audit | durable lifecycle and evidence record | record idempotency, cancellation, uncertainty and cleanup | silently retry uncertain non-idempotent work |
| Release controller | capability enablement decision | keep capability disabled until gates pass | treat CI or documentation as host/device acceptance |

### 8.1 Typed job envelope

Every dispatched job must be represented by a versioned, canonical, bounded envelope. The minimum logical fields are:

- `schema_version`, unique `job_id`, unique `session_id`, Owner subject, tenant/project identity and creation time.
- Absolute deadline, cancellation identity and idempotency key.
- Explicit origin allowlist and navigation policy; redirects must be re-evaluated.
- Ordered typed steps with capability, target evidence reference, risk class and expected postcondition.
- Data classification and redaction policy; no passwords, payment data, cookies or reusable secrets.
- Approval reference(s) bound to the canonical job fingerprint, exact origin and action scope.
- Immutable worker image digest, UID/GID, namespace, mount, resource, seccomp and proxy endpoint requirements.
- Result schema and evidence references; no arbitrary executable payload or browser script.

Canonicalization must reject unknown fields, duplicate keys, non-finite numbers, ambiguous URL encodings, invalid Unicode, oversized collections and unsupported schema versions. A hash is an identity binding, not proof that the underlying evidence is trustworthy.

### 8.2 Capability and approval matrix

| Capability | Default | Required checks |
|---|---|---|
| Open an allowlisted HTTPS origin | Ask First until policy explicitly classifies it low risk | normalized URL, scheme/host/port, DNS/SSRF policy, redirect re-check |
| Read visible page metadata | Read-only and bounded | current page evidence, output cap, redaction |
| Click a visible control | Ask First | fresh locator evidence, exact origin, action-specific approval |
| Fill a non-secret field | Ask First | field classification, exact target evidence, bounded value handling |
| Submit a form | Deny unless explicitly supported and separately approved | preview of exact form/action, origin, idempotency and postcondition |
| Upload/download | Deny by default | separately designed quarantine, file type/size policy and explicit approval; not enabled by this architecture |
| Login, credential extraction, password manager access | Deny | out of scope |
| Payment, checkout, purchase, trading, money movement | Deny | permanently out of scope for this project |
| Arbitrary JavaScript, shell, CDP or extension installation | Deny | out of scope |

A user approval is not a blanket permission. Approval must be checked immediately before the relevant action and consumed exactly once. A changed origin, target, action, payload fingerprint or page-state evidence invalidates the receipt.

### 8.3 Worker lifecycle state machine

Normative states:

`PROPOSED → POLICY_CHECKED → AWAITING_APPROVAL → APPROVED → PROVISIONING → ATTESTING → READY → RUNNING → TERMINATING → DESTROYING → SUCCEEDED | FAILED | UNKNOWN | CLEANUP_FAILED`

Rules:

1. State transitions are persisted before externally visible side effects wherever possible.
2. Only `READY` may transition to `RUNNING`; only after fresh signed attestation passes.
3. `UNKNOWN` is mandatory when the system cannot prove whether a non-idempotent browser action occurred.
4. `CLEANUP_FAILED` overrides a nominal task success. No success response is emitted until process exit and ephemeral storage deletion are confirmed.
5. Restart recovery must reconcile durable state with independently observed runtime identity. It must not recreate or replay an uncertain action.
6. Cancellation is monotonic. A cancelled job cannot return to an executable state.
7. Every state transition carries a timestamp, actor/component, job fingerprint and redacted evidence digest.

### 8.4 Evidence and attestation envelope

The signed evidence must bind at minimum:

- schema version, key ID, unique 256-bit challenge and collection timestamp;
- job/session identity and canonical launch-spec digest;
- immutable image digest, runtime/container identity and effective UID/GID;
- PID plus process-start identity, namespace identities, cgroup membership and effective resource limits;
- read-only root/mount policy, capability set, no-new-privileges and active seccomp profile identity;
- exact IPv4/IPv6 network policy, exact proxy endpoint pins, effective nftables ruleset digest and namespace inode;
- inspector/provider identity and signature.

The verifier must enforce key validity, challenge one-time consumption, freshness window, schema strictness, exact spec equality and replay rejection. Evidence from a worker process itself is not independent host evidence. The current collector's caller-owned challenge responsibility and externally provisioned signing key are explicit integration obligations, not completed operational key management.

### 8.5 Network policy contract and known implementation gap

The desired network policy is default-DROP for both address families. Only TCP to the exact pinned proxy address set and port is allowed from the worker. DNS resolution occurs at the proxy; worker DNS, direct TCP/UDP, QUIC/UDP 443, alternate routes and proxy-outage fallback are blocked. IPv6 neighbour discovery, if required for the chosen namespace topology, must be limited to the exact reviewed link-local control traffic and must not become general egress.

The host-inspector parser must validate the complete effective ruleset, not just the existence of an allow rule:
- exactly the intended table and base chains, hook/type/priority and default policies;
- all rules, sets, maps, verdict maps, jumps, chains and interface selectors, rejecting unknown constructs;
- IPv4 and IPv6 destination matches for every configured proxy pin;
- exact TCP protocol and port, with no broad accept rule or alternate chain;
- explicitly enumerated and bounded loopback/NDP exceptions only;
- no unreviewed NAT, redirect, masquerade or forwarding path that changes the effective policy.

**Observed gap (2026-11-19):** `core/browser_nftables.py` currently recognizes an IPv4 `ip daddr` match, TCP and an exact proxy port in its narrow output-rule grammar. It does not yet demonstrate equivalent IPv6 `ip6 daddr` validation or full dual-stack policy equivalence. Therefore the dual-stack network attestation contract is **not implemented/qualified** by this parser today. Do not treat its signed envelope as proof of dual-stack containment until the parser, fixtures and real-host evidence are extended and reviewed.

### 8.6 Browser action and evidence contract

- Navigation returns normalized final URL, redirect chain, response status and origin evidence; each redirect is policy checked before following.
- Inspection returns only bounded visible text/metadata and stable locator candidates. It never returns hidden inputs, password values, arbitrary attributes, cookies or local storage.
- Interaction consumes a fresh locator token bound to page generation, frame, origin, role/name or equivalent stable identity, and action type. Stale evidence causes re-inspection, not blind retry.
- Every mutation records precondition, approved action fingerprint, execution outcome and postcondition evidence.
- Ambiguous outcomes are UNKNOWN; the controller must not repeat clicks/submits based on a timeout alone.
- Popups, frames, service workers, WebSockets and subresource requests are within the network threat model even when the top-level page is allowlisted.

### 8.7 Recovery, retention and privacy

The durable audit record stores only the minimum necessary task metadata, redacted evidence, state transitions, hashes and cleanup status. It must not store browser profiles, cookies, passwords, payment data or full page dumps by default. Retention and deletion periods must be explicit configuration owned by the Owner. Backup/restore must preserve replay ledgers and audit integrity without restoring live approvals or reusable session credentials. Restore invalidates all in-flight approvals and challenges.

### 8.8 Deployment profiles

- **Development/test:** fake backend allowed only through explicit test injection; never labelled production or host-qualified.
- **Disposable Linux qualification:** concrete Podman backend and independently observed runtime; synthetic test data only; no personal browser profile.
- **Android client:** Android is an Owner interface/control plane unless a separately supported and qualified browser-host design is approved. Current runtime guard intentionally fails closed; this document does not promise Chromium execution on Android/Termux.
- **Production:** unavailable until independent review, operational key custody, backup/restore, real-host and network qualification, and Owner acceptance all pass.

## 9. Architecture decision records

- **ADR-001 — Owner-first authorization:** accepted. No anonymous/public access by default; sensitive actions require fresh Ask First approval; Auto-Run remains OFF.
- **ADR-002 — Ephemeral isolated worker:** accepted as target. One job per ephemeral non-root worker; immutable image identity; no personal profile or host secrets.
- **ADR-003 — Proxy-only egress:** accepted as target. Dual-stack default-DROP and exact pinned proxy only. Implementation evidence remains incomplete.
- **ADR-004 — Independent host attestation:** accepted as target. Runtime and firewall evidence must be observed independently and signed against a one-time challenge. Operational key custody and production provider remain open.
- **ADR-005 — Typed browser capabilities:** accepted. Navigation, inspection and mutation are distinct capabilities; no arbitrary code or shell surface.
- **ADR-006 — Fail closed on uncertainty:** accepted. Unknown action outcome, stale evidence, attestation failure or unconfirmed cleanup cannot be reported as success.
- **ADR-007 — Android separation:** accepted. Android client support does not imply Android browser-host support; no platform guard bypass.
- **ADR-008 — No financial actions:** accepted and non-configurable for this project. Payment, purchase, checkout, trading and money movement are prohibited.

## 10. Architecture completion checklist

Architecture/design documentation is considered complete only when each decision has an owner, contract, failure behavior and verification artifact. This document now defines those target contracts. The implementation is **not** thereby complete. Remaining implementation/design validation includes dual-stack nftables grammar and fixtures, concrete production backend composition, runtime-provider contract, authenticated worker control channel, key lifecycle and exact WorkerLaunchSpec-to-OCI mapping for mounts/proxy/resources. These are tracked as software integration blockers, followed by external disposable-host and Owner acceptance gates.
