# APAA-S08-C04 — Execution Safety

## P01 — Pre-execution validation
- Validate action identifier, payload mapping, canonical JSON serializability and bounded payload size.
- Reject unknown actions and payment, purchase, checkout, trading, money movement, paid-provider and external-provider identifiers through the central fail-closed policy.
- Validation is read-only and never invokes handlers.

## P02 — Permission check before every action
- Accept only an explicitly injected handler registry.
- Read-only allowlisted actions may proceed after validation.
- Mutations require a fresh, single-use approval receipt bound to exact action and canonical payload; durable deployments can additionally bind tenant and session scope through ApprovalAuthority.
- No Auto-Run path is exposed. A receipt is never inferred from task text or a boolean.

## P03 — Execution audit
- Persist an execution-intent event before dispatch; audit failure blocks the handler.
- Persist completion or failure after dispatch.
- If completion audit fails after a handler may have caused a side effect, return manual-review-required rather than claiming success.
- Audit events are payload-free.

## Verification
The dedicated test module covers validation, prohibited actions, exact approval, replay rejection, audit-before-dispatch, handler failure and completion-audit failure.

## Scope limits
This is a Python safety boundary, not a hostile-code sandbox. No real-world handlers, browser/device automation, network adapter, payment capability, paid provider, deployment, or native Android runtime is enabled. Production still requires independent review and real-device/live-auth evidence.