# APAA S00-C02 — Requirements

**Roadmap:** APAA Master Roadmap v1.0  
**Subject:** S00 — Project Foundation  
**Chapter:** C02 — Requirements  
**Working branch:** `apaa-s00-c02-requirements`  
**Status:** IN PROGRESS — P01 specification draft; P02 and P03 not started.  
**Baseline commit:** `e4d6a15847c883b0dec8e370b5b18b3844509763`

> This document is a requirements baseline, not evidence that every capability is implemented or production-ready. A requirement becomes VERIFIED only after its acceptance checks have been run and recorded against an exact commit.

## Product intent

APAA (Personal AI Automation Agent) is an owner-controlled, Android-first agent for carrying out explicitly requested digital tasks across authorized websites, web apps and supported services. It is an execution system, not a general-purpose chatbot. It must explain what it can do, request the right permission, perform only the authorized scope, and report evidence and failures honestly.

## Non-negotiable product constraints

1. Android-first user experience; Android device is the primary control surface.
2. Single Owner / private-by-default. No public signup or public access by default.
3. Permission default is **Ask First**. Auto-Run is OFF by default.
4. No payment, purchase, checkout, subscription purchase, trading, money movement or financial transaction actions.
5. No paid API, paid provider or chargeable service in the current development baseline. Any future provider must be disabled until separately reviewed and explicitly enabled by the Owner.
6. Read-only actions may run only inside the Owner-authorized scope. Write, edit, upload, delete, publish, send, submit, account/security changes and other consequential actions require a fresh, specific approval before the side effect.
7. No PR merge, deployment, main-branch modification, production activation, host firewall mutation or security-control weakening without explicit authorization.
8. Fail closed when identity, permission, target, policy, network boundary, execution result or audit integrity is uncertain.
9. Never represent a planned, mocked, skipped or CI-only capability as physically or operationally verified.
10. Every roadmap Part has its own checkpoint, tests/evidence and explicit status. Incomplete work must not be marked Completed.

---

# C2-P01 — Functional Requirements

**Checkpoint:** APAA-S00-C02-P01  
**Status:** SPECIFICATION DRAFT — implementation and acceptance evidence pending.

## FR-001 — Owner identity and private access
- APAA shall recognize one configured primary Owner.
- Unauthenticated users shall not access private projects, memories, files, tools or execution controls.
- Additional people, if ever supported, shall require explicit Owner invitation and scoped authorization.
- The Owner shall be able to revoke an authorization; revocation must block subsequent protected actions.

**Acceptance:** unauthenticated access denied; non-owner denied by default; authorized identity can be revoked; tests cover stale/revoked sessions.

## FR-002 — Natural-language task intake
- Accept a task instruction from the Android-first interface.
- Convert the instruction into a bounded task plan containing target, action, scope, expected result and risk class.
- Ask one focused clarification when an essential target or constraint is missing.
- Do not silently broaden the requested task.

**Acceptance:** representative instructions produce a reviewable plan; ambiguous target is clarified; out-of-scope action is rejected.

## FR-003 — Permission and approval
- Apply Ask First by default.
- Classify actions as read-only, reversible write, destructive, externally visible, account/security-sensitive or prohibited.
- Require fresh, explicit, action-specific approval for any consequential side effect.
- Bind approval to the Owner, session, target, exact action/request and expiry; reject replay, mismatch, stale, revoked or uncertain approval.
- Approval for one action must not authorize a different action or a broader task.

**Acceptance:** approval-boundary tests demonstrate allow/deny, expiry, replay, cross-session/Owner mismatch and request-tampering rejection.

## FR-004 — Authorized web research and information collection
- Visit only explicitly authorized sites/origins.
- Search, filter, extract and compare information within the granted scope.
- Preserve source references and distinguish observed facts, derived analysis and uncertainty.
- Respect site access controls and stop when authorization or policy is unclear.

**Acceptance:** tests verify allowed-origin enforcement, redirect/subresource handling, source capture and rejection of disallowed destinations.

## FR-005 — Browser and web-app task execution
- Support only registered, policy-checked browser capabilities.
- Use isolated, bounded browser sessions with deterministic cleanup.
- Keep browser/worker dispatch disabled until approval-to-dispatch binding and real isolation qualification pass.
- Never bypass a failed security gate to complete a task.

**Acceptance:** unit/contract tests plus disposable-host qualification; no production enablement based on mocks or loopback tests alone.

## FR-006 — Supported service workflows
- Discover and use only explicitly connected/supported services.
- For YouTube discovery, list relevant videos with source links; playlist changes require a specific approval and must be supported by an authorized integration.
- Unsupported workflows must be reported as unsupported rather than simulated as completed.

**Acceptance:** service-specific tests verify permission scope, correct target and honest unsupported-state reporting.

## FR-007 — Task lifecycle and recovery
- Track task states such as planned, awaiting approval, approved, running, succeeded, failed, cancelled and interrupted.
- Persist durable action history and approval correlation without storing unnecessary secrets or sensitive page payloads.
- On restart, treat uncertain in-flight work as interrupted; never automatically replay a side-effecting action.
- Permit safe inspection and explicit Owner-directed recovery.

**Acceptance:** restart, duplicate-ID, tamper, concurrency, cancellation and ambiguous-recovery tests pass.

## FR-008 — Audit and user-visible result
- Record who requested an action, what was authorized, what was attempted, timestamps, outcome and sanitized evidence.
- Never log passwords, access tokens, session cookies or unnecessary personal data.
- Report partial success, failure, skipped gates and unverified outcomes distinctly.
- Provide an auditable explanation of why an action was blocked.

**Acceptance:** audit integrity and redaction tests pass; UI result matches persisted action state.

## FR-009 — Project memory and checkpoints
- Keep project-specific context, decisions and roadmap checkpoints separated by project.
- Allow the Owner to resume from the last verified checkpoint.
- Preserve the distinction between planned, implemented, CI-verified, device-verified and independently reviewed work.

**Acceptance:** restart/resume tests recover the correct project and checkpoint without promoting incomplete work.

## FR-010 — Owner control and safe stop
- Provide controls to cancel a task, revoke authorization and disable automation.
- Stop before any unapproved consequential action.
- Cleanup temporary browser contexts, files and workers after completion, failure or cancellation.

**Acceptance:** cancellation/revocation race tests and cleanup tests show no post-revocation side effect.

## FR-011 — Android-first operation
- Provide an Android-usable Owner control interface.
- Clearly show task plan, approval prompt, current state, result and audit history on a phone-sized display.
- Do not assume Android can host a supported isolated Chromium worker; client control and execution worker are separate capabilities.
- Physical-device compatibility must be separately tested on the intended Android/Termux environment.

**Acceptance:** responsive Android-sized UI tests plus physical handset acceptance; emulation is not physical-device evidence.

## FR-012 — Testing and truthful capability reporting
- Each feature must have deterministic automated tests appropriate to its risk.
- Security boundaries require adversarial tests and exact-head CI.
- Device, host, external service and production claims require corresponding real-environment evidence.
- A skipped manual safety gate is not a test failure, but it is not a qualification pass either.

**Acceptance:** each checkpoint records exact commit, test command/workflow, result, skipped gates and remaining risks.

## FR-013 — Prohibited actions
APAA shall not perform payments, purchases, checkout, money transfers, trading, financial account transactions, credential theft, unauthorized access, destructive activity outside approved scope, or attempts to bypass security controls.

**Acceptance:** prohibited-action policy tests reject these requests before tool execution or side effects.

---

## P01 completion gate

P01 may be marked **VERIFIED** only when:
- The Owner-facing functional scope is reviewed and accepted.
- Each FR has a traceable implementation/test mapping or is explicitly recorded as planned/not implemented.
- Prohibited actions and approval boundaries have negative tests.
- No requirement contradicts the Android-first, Owner-first, Ask First and no-payment constraints.
- The exact document/code commit and verification evidence are recorded.

## Deferred in this chapter

- **C2-P02:** Non-functional Requirements — not started.
- **C2-P03:** User Commands and Expected Results — not started.

## Current checkpoint

`APAA-S00-C02-P01` — Functional Requirements specification drafted; review, traceability and acceptance evidence pending.
