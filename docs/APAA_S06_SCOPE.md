# APAA S06 — Structured Task Workspace and Plan Review

**Checkpoint:** APAA-S06-C01-P01  
**Status:** IMPLEMENTATION IN PROGRESS  
**Approval:** User instructed to begin S06 on 2026-11-15  
**Branch:** `feature/approval-ui-e2e-p06`  
**PR:** #5 — remains Draft and unmerged

## 1. Objective

Connect the S05 deterministic structured planning contract to the existing Streamlit Task Workspace. Make plan states and step boundaries understandable and reviewable on mobile-sized browser screens without introducing execution authority or external side effects.

## 2. Approved implementation scope

1. Replace the Task Workspace's legacy free-form `AIBrain.respond()` rendering with `create_structured_plan(Task(...))`.
2. Render READY plans with plan ID, schema version, stable step IDs, purpose, category and expected output.
3. Render NEEDS_CLARIFICATION questions and allow the user to add context and request a revised plan.
4. Render BLOCKED state and safety notes without creating steps.
5. Visibly distinguish proposed mutations and state that each requires separate action-specific human approval.
6. Keep the Task Workspace read-only: no receipt issuance, execution gateway call, handler dispatch or external action.
7. Clear plan and clarification drafts on identity change, logout and authentication loss.
8. Add Streamlit AppTest coverage for all plan states, clarification re-planning, mutation labelling and session cleanup.
9. Update architecture and user-facing project documentation.

## 3. Explicit exclusions

- No task execution, browser/device control, shell, email, arbitrary filesystem/network handler or connector integration.
- No plan persistence, scheduler, queue, retry loop or autonomous background run.
- No Auto-Run enablement; default remains OFF.
- No payment, purchase, checkout, trading, investment execution, money movement or financial transaction.
- No paid provider, API key, external AI call or billable service.
- No merge, deployment, branch protection modification or base-branch change.
- Native Android application and real-device verification are not claimed by this Streamlit UI work.

## 4. Acceptance criteria

- READY plans show all ordered steps and safety boundary.
- NEEDS_CLARIFICATION plans show questions; user-supplied clarification produces a fresh deterministic plan while retaining original task text.
- BLOCKED plans show safety notes and no steps.
- Proposed mutation is clearly labelled as a proposal requiring separate human approval; no approval receipt is created.
- Task Workspace interaction creates no execution audit events.
- Plan-related session state is removed at identity boundaries.
- Existing two CI workflows pass on the exact final S06 commit.
- PR remains Draft and unmerged.

## 5. Known constraints

- S05 intent classification remains conservative and lexical; S06 UI does not upgrade it to semantic policy enforcement.
- Current Streamlit layout has not been verified on a physical Android device.
- S04 operational blockers BY-01 through BY-07 remain independently blocked.

**Next checkpoint:** APAA-S06-C01-P02 — run focused AppTest and full CI, inspect failures, fix them, then verify exact-head CI and update the S06 verification matrix.
