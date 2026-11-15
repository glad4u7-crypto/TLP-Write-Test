# Execution Gateway: Security Boundary (Prototype)

## What is implemented

- `ExecutionGateway` dispatches only explicitly registered handlers.
- The handler registry is empty by default.
- Every dispatch is checked by `authorize_action` before a handler is called.
- Unknown, financial, payment, paid-provider, shell, and arbitrary code-execution
  action identifiers are rejected by the current action registry.
- Mutations require either an exact Auto-Run allowlist entry configured when the
  trusted gateway is constructed, or a one-time approval receipt bound to the
  action and canonical payload digest.
- Task execution requests cannot provide or modify the Auto-Run allowlist; it is
  fixed in trusted application configuration and empty by default.
- Approval receipts are HMAC-signed, expire after a short interval, and cannot
  be replayed after successful consumption.
- The gateway itself contains no shell, browser, network, device, or provider
  adapter.
- The gateway records payload-free in-memory audit events for allowed and denied
  dispatch attempts; events intentionally omit payload values and secrets.
- When a `JsonlAuditLog` is configured, the gateway persists an authorization
  intent before invoking a handler and blocks the handler if that write fails.
  It then persists a completion/failure event. If completion persistence fails
  after a side effect, the result explicitly reports that manual review is needed.

## Critical approval trust boundary

The `ApprovalAuthority` is a trusted application capability. The Streamlit UI constructs a server-side `ApprovalAuthority` and
`ExecutionGateway` in session state. The controller module only builds the
gateway; it cannot issue approvals. The UI issues a short-lived receipt only
inside the explicit Confirm-button branch, after rendering the exact project
name and description, then submits that receipt to the gateway. The receipt
issuer is an in-process capability, not an authentication mechanism.

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
- The Streamlit Project Manager uses a two-step review/confirm flow. Only its Confirm-button event issues the one-time receipt; the project gateway builder cannot approve its own request.
- This is an in-process prototype boundary, not a hardened multi-user authentication boundary.
- The Streamlit session gateway is configured with local JSONL persistence at `.apaa_audit/execution.jsonl`; it provides a SHA-256 hash chain. The hash chain is not tamper-proof against an attacker who can rewrite the file and recompute hashes.
- The JSONL writer uses a process-local lock only. Concurrent writers across multiple processes/hosts need a transactional or centralized audit backend before production.
- No production capability-isolation layer exists.
- `ProjectRegistry.create` and `delete` require an internal in-process capability; ordinary direct calls are rejected and the trusted project controller passes the capability only through the approval-gated handler.
- This capability prevents accidental bypasses but is not isolation against arbitrary Python code executing inside the same process.
- No production sandbox or path-confinement layer exists for file operations.

## Release gate

Do not register real-world or irreversible handlers until UI approval wiring,
audit logging, capability isolation, sandboxing, and negative integration tests
are implemented and reviewed. Payment and purchase actions remain prohibited.
Paid/external providers remain disabled.
