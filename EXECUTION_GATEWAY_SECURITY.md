# Execution Gateway: Security Boundary (Prototype)

## What is implemented

- `ExecutionGateway` dispatches only explicitly registered handlers.
- The handler registry is empty by default.
- Every dispatch is checked by `authorize_action` before a handler is called.
- Unknown, financial, payment, paid-provider, shell, and arbitrary code-execution
  action identifiers are rejected by the current action registry.
- A mutation is denied unless the exact action is approved or it is present in
  an explicitly supplied Auto-Run allowlist.
- The gateway itself contains no shell, browser, network, device, or provider
  adapter.

## Critical approval trust boundary

The current `approved_action` argument is an internal policy signal, **not a
cryptographic proof of user consent**. It must only be supplied by a trusted
application approval controller after the user has reviewed and confirmed the
specific action and its payload.

Never:
- pass model-generated text or ordinary user text directly as `approved_action`;
- expose an approval setter or the raw gateway to the planner/model;
- treat a generic "yes", session flag, or stale approval as authorization for
  a different action or payload.

Before enabling real handlers, implement a trusted approval controller that
binds approval to the exact action, target, payload digest, expiry, and a
one-time request identifier. The UI must show the complete effect before
issuing that approval.

## Not yet implemented / not enabled

- No real file, email, browser, shell, network, or device handlers are wired.
- No persistent approval store, one-time approval receipt, or audit log exists.
- No production sandbox or path-confinement layer exists for file operations.
- The Streamlit UI does not call this gateway.

## Release gate

Do not register real-world or irreversible handlers until the approval
controller, payload-bound approval, audit logging, capability isolation,
and negative integration tests are implemented and reviewed. Payment and
purchase actions remain prohibited. Paid/external providers remain disabled.
