# APAA S05 — Approved Scope and Implementation Record: Task Intake and Deterministic Planning Contract

**Checkpoint:** APAA-S05-C01-P06  
**Status:** IMPLEMENTED — EXACT-HEAD CI PASS; INDEPENDENT REVIEW COMPLETE  
**Repository:** glad4u7-crypto/TLP-Write-Test  
**Working branch:** feature/approval-ui-e2e-p06  
**Approved by user:** 2026-11-15; approval recorded in this conversation\n**Implementation branch:** feature/approval-ui-e2e-p06

## 1. Purpose and baseline

The current foundation already has a minimal `Task` model, task-status enum, a deterministic `create_plan` function, a provider-neutral brain interface, action authorization, approval receipts, audit logging and a fail-closed execution gateway.

The current planner returns a fixed list of generic strings. It does not yet provide a typed, inspectable plan contract that can be validated, reviewed, safely rejected, or later connected to separately authorized tools. S05 closes this planning-contract gap without enabling execution.

This scope was explicitly approved by the user on 2026-11-15. Approval authorizes this planning-contract work only.

## 2. Approved objective

Define and implement a deterministic, offline **Task Intake and Planning Contract** that converts a user's task description plus explicit constraints into a structured plan suitable for human review.

The S05 deliverable should improve clarity, validation and traceability while remaining a planning-only subsystem.

## 3. Approved in-scope work

### S05-P01 — Requirements and contract
- Define typed plan, step, risk/impact classification, assumptions, missing-information questions, and validation outcomes.
- Distinguish read-only/research steps from proposed mutations without granting permission to perform them.
- Define stable identifiers and deterministic serialization rules where needed for later approval binding.
- Specify empty, ambiguous, contradictory, oversized and unsupported task handling.

### S05-P02 — Task intake validation
- Normalize whitespace and validate task description boundaries without silently changing user intent.
- Preserve user-stated constraints and distinguish explicit facts from planner assumptions.
- Detect missing essential information and return clarification requirements rather than inventing values.
- Reject malformed or unsupported input safely.

### S05-P03 — Deterministic plan generation
- Replace generic string-only planning with typed plan objects while retaining a documented compatibility path if existing callers require it.
- Generate steps that include purpose, action category, expected output, prerequisites, and whether human approval would be required before any future mutation.
- Keep plan generation offline and deterministic; no LLM, network, paid provider, API key or external service.
- Do not infer that a plan step is executable merely because it is present in the plan.

### S05-P04 — Safety and approval boundary
- Treat every generated plan as untrusted proposal data.
- Revalidate action identifiers against the existing fail-closed safety policy.
- Keep payment, purchase, checkout, trading, investment execution, money movement and paid-provider actions prohibited.
- Keep Auto-Run disabled and the allowlist empty.
- Do not issue approval receipts from the planner or from model/task text.
- No handler registration, dispatch, shell, browser, email, network, filesystem or device action is added in S05.

### S05-P05 — Tests and documentation
- Unit tests for deterministic output, stable ordering, validation, ambiguity, contradictory constraints, unsupported actions and safety denials.
- Negative tests proving planning cannot issue approvals, register handlers, dispatch actions or activate providers.
- Regression tests for existing task/planner callers and all existing S04 approval/audit behavior.
- Update architecture and user-facing documentation only after the contract is accepted.

## 4. Explicitly out of scope

- Real browser automation, Android/device control, shell/terminal execution, email sending, messaging, publishing, file mutation, GitHub writes or other external side effects.
- Any payment, purchase, checkout, trading, investing, transfer, withdrawal, deposit or money movement.
- Auto-Run or autonomous execution.
- Activating OpenAI, Gemini, Claude, Anthropic or any external/paid model provider; requesting keys or incurring charges.
- Live OIDC, production deployment, branch-protection administration, backup infrastructure or closure of S04 BY-01…BY-07.
- Native Android application development.
- A new CI workflow; S05 should strengthen and use the two existing CI workflows only.

## 5. Proposed architecture boundary

`User task + explicit constraints`
→ `Task intake validator`
→ `Deterministic planner`
→ `Typed proposed plan`
→ `Safety classification / validation`
→ `Human-readable review output`

The flow ends at review output. It does not connect to the execution gateway in S05. Any future execution integration must be a separately scoped checkpoint with explicit permission design, handler threat model, sandbox requirements, approval UX, audit requirements and negative tests.

## 6. Acceptance criteria for S05 implementation

S05 may be marked implementation-complete only when all of the following are evidenced:

1. The plan schema is typed, documented and versioned.
2. Identical inputs produce identical plan content, excluding explicitly documented timestamps or generated identifiers.
3. Missing essential inputs are surfaced as questions; the planner does not invent answers.
4. Contradictory, malformed, unsupported and prohibited requests fail closed or produce a clearly blocked plan.
5. Every proposed mutation is labelled as requiring separate action-specific human approval; no approval is issued.
6. Planner code cannot register or dispatch an execution handler.
7. Provider/network use remains absent from the default path.
8. Regression and negative tests pass.
9. Agent Foundation CI and Python Demo CI both pass on the exact final commit, with every job and step inspected.
10. PR #5 remains Draft and unmerged unless the user separately authorizes a different state.

## 7. Dependencies and known constraints

- Existing `core/models.py`, `core/planner.py`, `core/safety.py`, `core/execution.py`, `core/approvals.py` and current tests are the implementation baseline.
- S04 production blockers remain unchanged and must not be treated as closed by S05.
- The current UI is a Streamlit web prototype, not a native Android app.
- The project remains zero-cost and offline by default.
- No third CI workflow should be created for duplicate test coverage.

## 8. Approval gate and next sequence

This document is a proposal, not authorization to implement S05. The next decision is to approve, amend or reject this scope. Once approved, the work sequence should be:
- S05-C01-P02: finalize plan schema and threat boundary.
- S05-C01-P03: implement intake validation and deterministic typed planner.
- S05-C01-P04: add positive, negative and regression tests.
- S05-C01-P05: inspect security implications, update docs, run both existing CIs on the exact final head, and record evidence.

Until scope approval, do not change runtime code or enable any new capability.

## 9. Implementation record\n\n### Implemented and verified in this work batch\n- Added `IntakeResult`, `PlanStep`, `TaskPlan`, `PlanStatus` and `StepCategory` typed contract objects.\n- Added deterministic task intake validation: text-only input, empty/control-character rejection, 4,000-character bound and whitespace normalization.\n- Added deterministic plan IDs and stable four-step planning output.\n- Added clarification responses for a small, explicit set of deictic/underspecified requests.\n- Added conservative blocked-plan handling for detected prohibited financial/trading/purchase/provider intent.\n- Added mutation-proposal labelling; a plan cannot issue an approval receipt or dispatch an action.\n- Preserved the legacy `create_plan` four-string API for compatibility.\n- Added focused contract tests for determinism, serialization, input validation, clarification, blocked intents and mutation labelling.\n\n### Verification status\n- Code and tests committed to the feature branch.\n- Agent Foundation CI #622 / run `43706514203`: completed / success; dependency install, pip-audit, compileall, foundation tests and post steps all succeeded.\n- Python Demo CI #713 / run `43706514142`: completed / success; dependency install, full test suite, demo smoke test and post steps all succeeded.\n- Both workflows were verified against exact pre-documentation implementation head `4c23c28620793bd0d7009fad6f9f1477bf822611`; final documentation-only head must be re-run through both existing workflows before closure.\n\n## 10. Carried-forward non-negotiable safety constraints

- Zero-cost/offline default; no paid provider, API key or billable service.
- Auto-Run OFF; approval must remain explicit and action-specific.
- No real-world execution handlers.
- Payment, purchase, checkout, trading and money movement prohibited.
- PR #5 Open + Draft; no merge, deployment or base-branch change.
- S04 production/release status remains NOT APPROVED until BY-01…BY-07 have independently verifiable acceptance evidence.
