# APAA S07 — Browser Automation Architecture and Threat Model

**Checkpoint:** APAA-S07-C01-P01  
**Status:** DESIGN PROPOSAL COMPLETE — IMPLEMENTATION NOT AUTHORIZED  
**User request:** Proceed with architecture, threat model and permission-boundary work (2026-11-15)  
**Branch:** `feature/approval-ui-e2e-p06`  
**PR:** #5 — Open, Draft, unmerged

## 1. Objective

Design a safe, free-by-default browser automation capability for future APAA development, with explicit trust boundaries, isolated execution, origin restrictions, action-specific approval and adversarial verification requirements.

## 2. Deliverables in this checkpoint

1. `docs/APAA_S07_BROWSER_AUTOMATION_ARCHITECTURE.md` — proposed component and isolation architecture.
2. `docs/APAA_S07_BROWSER_THREAT_MODEL.md` — threat catalogue, STRIDE analysis, mitigations and residual risks.
3. `docs/APAA_S07_PERMISSION_MATRIX.md` — default-deny capability permissions and prohibited actions.
4. `docs/APAA_S07_VERIFICATION_MATRIX.md` — future test and operational evidence requirements.
5. `docs/APAA_S07_BROWSER_ACTION_CONTRACT.md` — typed job/action/result contract proposal and approval binding.
6. `docs/APAA_S07_MOBILE_APPROVAL_UX.md` — Android-friendly review, one-action approval, cancellation and accessibility flow.
7. Update `docs/ARCHITECTURE.md` with a clear proposal-only boundary.
8. Reconcile S06 scope and matrix status with the final exact-head CI already verified at `8d2ff3c1c7007b2a23b01164d5862bf6fc09391d`.

## 3. Scope

- Architecture and documentation only.
- Use existing planner, ApprovalAuthority, ExecutionGateway and session-security boundaries as design references.
- Specify exact-origin allowlisting, redirect/DNS/SSRF controls, ephemeral browser contexts, isolated worker, constrained egress, action-specific approval, audit and cancellation.
- Define read-only, mutation and prohibited capability tiers.
- Define prompt-injection, credential, tenant-isolation, worker-compromise and audit threats.
- Define future test evidence; do not claim tests that have not run.

## 4. Explicit exclusions

- No browser automation library, browser binary, driver or dependency added.
- No browser session, network request, CDP endpoint, browser handler or ExecutionGateway registration.
- No shell, ADB, filesystem, email, native Android or device-control handler.
- No downloads, uploads, clipboard, password/cookie/token access or persistent browser profile.
- No Auto-Run, background job, scheduler, queue or retry loop.
- No payment, purchase, checkout, trading, investment order, money movement or financial action.
- No paid API/provider, API key or billable service.
- No merge, deployment, PR promotion or base-branch change.

## 5. Acceptance criteria

- Architecture clearly separates trusted UI/approval from untrusted planner, page content and isolated worker.
- All browser navigation and requests are constrained by exact-origin allowlist and revalidated redirects/DNS.
- Worker has no default-profile, host-secret, broad filesystem or unrestricted network access.
- Mutation approval binds exact origin, action, target, payload, identity, session and job, with short expiry and one-time use.
- Prompt injection and web content cannot grant authority or override policy.
- Prohibited financial and purchase actions remain denied regardless of approval.
- Verification matrix labels all browser controls DESIGN, not PASS.
- Proposed typed browser job contract rejects unknown actions and binds approval to exact job, origin, action, target, payload and session.
- Mobile review UX makes origin and exact effect visible; no blanket approval or inferred consent.
- Existing CI workflows pass on the exact final documentation commit.
- PR remains Draft and unmerged.

## 6. Gate after this checkpoint

A separate implementation scope and explicit user approval are required before adding any browser runtime, dependency, handler or execution capability. S07 design completion is not permission to operate websites.
