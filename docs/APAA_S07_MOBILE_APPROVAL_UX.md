# APAA S07 — Proposed Mobile Approval and Review UX

**Checkpoint:** APAA-S07-C01-P01  
**Status:** UX DESIGN ONLY — NO BROWSER ACTIONS ENABLED  
**Target:** Android phone browser / mobile ChatGPT-style command surface; no native device control implied.

## 1. User journey

1. User submits a task in the Task Workspace.
2. Planner produces a structured proposal and names the exact website origin(s).
3. Policy Gate checks origin, action type, destination and risk category.
4. If unclear or outside policy, the UI asks a clarification or displays a blocked reason.
5. For a future read-only job, show a compact review summary: site, what will be read, expected output, data limits and expiry.
6. For a future eligible mutation, show a separate confirmation screen with exact site, action, target, changed fields/values, expected consequence and whether the action is reversible.
7. User explicitly confirms that one action only. The approval expires quickly and cannot approve the next step.
8. Browser worker runs in an isolated ephemeral context; progress and cancellation remain visible.
9. Result screen shows source origin, completion state, extracted information, limitations and whether any step was skipped.
10. Context is destroyed and the user receives a concise audit summary.

This is a proposed flow only. S07 does not implement these screens.

## 2. Mobile review card requirements

Every review card should show:
- website name and canonical origin (not only a logo or page title);
- action type and exact target;
- read-only vs state-changing classification;
- fields/data to be read or changed;
- expected effect and known reversibility;
- number of steps and per-step approval requirement;
- expiry countdown and cancellation control;
- explicit blocked items and reason.

Avoid tiny controls, hidden secondary actions, ambiguous color-only warnings and approval buttons adjacent to navigation controls. Use clear text labels and adequate touch targets.

## 3. Approval interaction rules

- No preselected confirmation checkbox or default-positive button.
- No approval inferred from typing a task, opening a page, scrolling, or tapping "Continue".
- The final control must name the action, e.g. "Approve this one change", not generic "OK".
- One approval covers one exact action and payload only.
- Any changed origin, target, field, value, page state or action requires a new review.
- Cancel, Back, timeout, logout or identity change invalidates the pending approval.
- Never ask users to paste passwords, cookies, API keys or recovery codes into APAA.
- Authentication, if required by a site, must use a separately reviewed user-controlled flow; no browser credential import.

## 4. Accessibility and error states

- Screen-reader labels for origin, action, risk, approval and status.
- Support large text and narrow screens without horizontal scrolling.
- Distinguish READY, NEEDS_CLARIFICATION, BLOCKED, WAITING_FOR_APPROVAL, RUNNING, CANCELLED, FAILED and COMPLETED.
- If the UI cannot render the exact target and effect clearly, do not offer the approval control.
- On stale state or ambiguous target, return to review instead of attempting the action.
- If audit or worker isolation status is unavailable, display blocked and do not dispatch.

## 5. Android boundary

- Mobile browser usability is a UI target only.
- No ADB, accessibility service, screen scraping, key injection, app-to-app control or device takeover is implied.
- The user may access a future APAA web UI from Android; the browser worker would run in the isolated server-side environment, not on the phone.
- Native Android app, offline operation and physical-device support require separate product and security review.
