# Execution Gateway: Security Boundary (Prototype)

## What is implemented

- `ExecutionGateway` dispatches only explicitly registered handlers.
- The handler registry is empty by default.
- Every dispatch is checked by `authorize_action` before a handler is called.
- Unknown, financial, payment, paid-provider, shell, and arbitrary code-execution
  action identifiers are rejected by the current action registry.
- Mutations require either an exact Auto-Run allowlist entry or a one-time
  approval receipt bound to the action and canonical payload digest.
- Approval receipts are HMAC-signed, expire after a short interval, and cannot
  be replayed after successful consumption.
- The gateway itself contains no shell, browser, network, device, or provider
  adapter.

## Critical approval trust boundary

The `ApprovalAuthority` is a trusted application capability. Only the UI
controller may call `issue(..., confirmed_by_user=True)`, and only after the
user reviews the complete action, target, and payload and explicitly confirms.

Never:
- expose `ApprovalAuthority`, its `issue` method, or the raw gateway to the
  planner/model or untrusted task content;
- pass model-generated text or ordinary user text as user confirmation;
- treat a generic "yes", session flag, or stale approval as authorization for
  a different action or payload.

The receipt is bound to the exact action and payload digest, has a short expiry,
and is single-use. The HMAC protects receipt integrity inside the trusted
application process; it does not replace application-layer access control.

## Not yet implemented / not enabled

- No real file, email, browser, shell, network, or device handlers are wired.
- The Streamlit UI does not call the gateway or issue approval receipts.
- No persistent audit log or production capability-isolation layer exists.
- No production sandbox or path-confinement layer exists for file operations.

## Release gate

Do not register real-world or irreversible handlers until UI approval wiring,
audit logging, capability isolation, sandboxing, and negative integration tests
are implemented and reviewed. Payment and purchase actions remain prohibited.
Paid/external providers remain disabled.
