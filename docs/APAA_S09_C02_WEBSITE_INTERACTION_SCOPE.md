# APAA-S09-C02 — Website Interaction

**Status:** IMPLEMENTATION IN PROGRESS — offline intent validators and adversarial tests added; exact-head CI pending.  
**Checkpoint family:** `APAA-S09-C02-P01`, `APAA-S09-C02-P02`, `APAA-S09-C02-P03`  
**Repository:** `glad4u7-crypto/TLP-Write-Test`  
**Branch:** `feature/apaa-s09-c02-website-interaction`  
**Base:** S09-C01 Action History & Recovery branch, commit `445e2bfa92d89984b620110ae15bc6a0244b4ac7`.

## 1. Objective

Define a bounded, owner-authorized website interaction layer for:
- P01: Click and Form Filling.
- P02: Search and Filtering.
- P03: Multi-page Navigation.

This chapter must use the existing BrowserJob, exact-origin policy, approval correlation, recovery ledger and isolated-worker contracts. It must not create a second permission system or bypass the existing fail-closed dispatch boundary.

## 2. Dependency and release gate

S09-C01 is **not complete or security-approved for live browsing**. The current evidence includes a failed disposable-host Chromium qualification caused by an FD ownership violation, and production approval-receipt consumption is not connected to the production BrowserExecutionCoordinator. Android physical-device qualification and independent security review are also outstanding.

Therefore this C02 branch is allowed to add offline schemas, deterministic validators, unit tests, documentation and mock-only planning. It must NOT launch Chromium, connect to a live website, submit a form, click a live control, dispatch a worker, or enable public/live browsing until all C01 release gates are passed and explicitly accepted by the Owner.

## 3. Non-negotiable safety rules

- Owner-first, private by default; no public signup or unauthorised users.
- Default permission is **Ask First**. Every mutating action needs a fresh, exact, one-time approval bound to Owner, session, tenant, job and canonical action payload.
- Read-only inspection is limited to an explicitly approved HTTPS origin and bounded page/result sizes.
- Clicks are not assumed read-only. Any click that may submit, purchase, publish, send, delete, change account settings, or trigger an external side effect is classified as mutation and blocked absent exact approval.
- Form filling is draft-only by default. No submit/confirm/send action is included in a fill operation.
- Payment, purchase, checkout, subscription, trading, money movement and financial transactions are permanently out of scope.
- No password, OTP, recovery code, payment data, API key or other secret may be collected, stored in action history, or emitted in logs.
- No Auto-Run, blind retries, replay after uncertain outcomes, arbitrary JavaScript, eval/exec, shell, extension installation, downloads, uploads, or persistent browser profile.
- Redirects and every network destination must remain under the C01 enforced egress boundary. Page-level routing alone is not treated as a network sandbox.
- Browser/Worker dispatch remains disabled until C01 qualification and Owner acceptance.

## 4. Part breakdown

### P01 — Click and Form Filling

**Checkpoint:** `APAA-S09-C02-P01`

Planned capabilities:
- Represent a click as a typed intent, not arbitrary selector/script execution.
- Require a bounded locator strategy and uniqueness check; ambiguous or stale targets fail closed.
- Capture a minimal, sanitized preview of the target and intended effect before approval.
- Separate field fill from submit. Filling a form never submits it.
- Validate field type, length, allowed values and page-origin binding.
- Require a fresh exact approval for any submit-like or side-effecting click; permanently reject prohibited financial actions.
- Detect navigation or DOM changes between preview and execution; invalidate stale approval rather than guessing.

Acceptance tests:
- Reject unknown action types, arbitrary scripts, malformed selectors, unbounded text and cross-origin targets.
- Reject ambiguous/multiple matches and stale target references.
- Prove fill-only never invokes submit/click.
- Prove mutation approval is bound to exact canonical target + value/action + Owner/session/tenant/job and is one-time.
- Prove expired, replayed, revoked, mismatched and cross-session approvals fail closed.
- Prove payment/purchase/checkout/send/delete/publish actions are blocked.

### P02 — Search and Filtering

**Checkpoint:** `APAA-S09-C02-P02`

Planned capabilities:
- Bounded search text and structured filter expressions; no arbitrary code or selector evaluation.
- Explicit origin and page binding.
- Result caps, pagination caps, timeouts and output-size limits.
- Read-only result extraction with sensitive-field redaction.
- Search submission must be classified by the site's semantics; any side effect or state change requires approval or is blocked.

Acceptance tests:
- Reject excessive query length, unsupported operators, unbounded result counts and unsafe selectors.
- Enforce exact-origin checks and bounded pagination.
- Verify deterministic normalization and redaction.
- Verify no hidden form submission or mutation is triggered by a read-only search plan.

### P03 — Multi-page Navigation

**Checkpoint:** `APAA-S09-C02-P03`

Planned capabilities:
- Finite, ordered navigation plan with strict maximum steps and per-step deadline.
- Every destination validated independently against exact approved origins and the C01 egress gateway.
- Re-authorize every redirect, popup, frame and new tab; unsupported surfaces fail closed.
- Maintain an explicit page/session lineage; never carry cookies or profile state across jobs.
- Stop on unexpected origin, ambiguous state, timeout, challenge/login wall or changed page identity.
- No automatic retry after a step may have caused an external side effect.

Acceptance tests:
- Reject loops, excessive steps, unapproved origins, redirect escape, popup/frame escape and stale page lineage.
- Verify deterministic stop-on-first-failure and cancellation.
- Verify no replay of uncertain steps after restart.
- Verify each page transition is bounded and recorded without sensitive page content.

## 5. Shared typed interaction contract — initial offline implementation

The implementation should introduce immutable typed intent records with a closed schema. Suggested conceptual fields:
- `interaction_id`, `job_id`, `step_index`
- `origin`, `page_identity`
- `operation` (closed enum)
- `target` (bounded structured locator; no executable selector expressions)
- `value` (bounded non-secret value only where allowed)
- `expected_effect` (read-only / draft-only / mutation)
- `approval_reference` (opaque reference; never an approval secret)
- `expires_at`, `max_runtime_seconds`

The first offline API is implemented in `core/browser_interaction.py` with immutable `ClickIntent`, `FillIntent`, `SearchIntent`, `NavigationPlan` and related records. It exposes validators only; it does not launch a browser, perform I/O, execute selectors, consume approval receipts or dispatch jobs. Clicks are restricted to explicit link navigation; buttons and submit controls are rejected. Form filling is draft-only and rejects secret field types. Search filters and navigation steps are closed-schema and bounded. The API remains a controller-side validation layer and must be reconciled with the existing BrowserJob and approval-correlation interfaces before any executor is considered. Do not expand existing allowlists merely to make tests pass.

## 6. Verification and evidence policy

Each Part requires:
1. focused deterministic unit tests;
2. negative/adversarial tests;
3. full repository suite on the exact code-bearing commit;
4. exact-head CI evidence;
5. a reviewed security diff.

Mock tests prove controller logic only. They do not prove browser, network, OCI, Android or live-site safety. Those require separate controlled qualification after C01 blockers are resolved.

A checkpoint is **VERIFIED** only when its exact-head tests and required review evidence pass. A documentation-only commit does not complete any Part.

## 7. Current status

| Checkpoint | Status | Reason |
|---|---|---|
| C02-P01 | DESIGN STARTED | No interaction implementation yet; C01 live dispatch gate remains closed |
| C02-P02 | PLANNED | Depends on shared interaction contract |
| C02-P03 | PLANNED | Depends on shared interaction contract and C01 redirect/egress qualification |
| C02 overall | BLOCKED FOR LIVE EXECUTION | C01 real-host Chromium/approval/Android/security gates remain open |

## 8. Next engineering sequence

1. Reconcile this design with the existing BrowserJob closed schema, approval receipt and action-history interfaces.
2. Implement P01's offline typed-intent validator only; no browser adapter or dispatch.
3. Add focused positive/negative tests and exact-head CI.
4. Continue P02 and P03 controller-only work after the shared contract is reviewed.
5. Keep live execution disabled until C01 is independently qualified and the Owner explicitly accepts the release gates.

**No PR merge, deployment, default-branch modification, payment, purchase or Auto-Run is authorized by this document.**
