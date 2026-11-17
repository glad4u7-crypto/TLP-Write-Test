# APAA BCS-01 — Personal Runtime Browser Security Integration

**Status:** Implementation added; exact-head verification pending. Browser/Worker handler remains DISABLED.

## Scope
BCS-01 connects the existing offline Browser Security policy to the Personal Edition Owner identity, durable ApprovalAuthority and SQLite Action Audit. It does not implement a browser worker, navigation, network access, or Android browser execution.

## Existing modules audited
- `core/browser_security.py`: closed-schema read-only job, canonical HTTPS URL, exact-origin allowlist, public-address/DNS validation and redirect-chain primitives.
- `core/browser_navigation.py`: earlier navigation policy/controller. It performs DNS resolution through an injectable resolver but is not a trusted socket-level egress boundary.
- `core/browser_launch.py`: ephemeral Playwright launch abstraction; no navigation API is exposed by the launch contract.
- `core/browser_runtime.py`: inert worker launch specification and pre-start attestation validation.
- `core/attested_browser_runtime.py`: requires signed isolation evidence and an explicit trusted worker adapter; no default adapter exists.
- `core/personal_auth.py` and app Owner gate: local Owner passphrase authentication, lockout, idle/absolute session expiry and logout invalidation.
- `core/approvals.py`: one-time HMAC receipt bound to action, exact JSON payload, Owner tenant, session scope and expiry; durable nonce consumption is supported.
- `core/execution.py` and `core/sqlite_security_store.py`: permission-gated dispatch and durable payload-free hash-chain Action Audit.

## BCS-01 integration
1. The trusted app controller creates `BrowserControlBoundary` only after its authenticated Owner gate and tenant binding.
2. Every approval request re-checks the active Owner session and requires an explicit Owner confirmation flag from trusted UI code.
3. The request is validated by `validate_browser_job`; the receipt binds the canonical job, Owner tenant and current session.
4. The receipt lifetime is at most 60 seconds and cannot exceed the job expiry.
5. Dispatch revalidates the job and consumes the durable one-time receipt through the existing ExecutionGateway.
6. The gateway has an intentionally empty handler registry. It records a payload-free Action Audit denial stating that no trusted browser handler is registered.
7. The app does not expose a browser action UI or invoke dispatch. No browser/worker adapter is registered.

## Security limits
- Offline URL/DNS validation is not connection-time enforcement. No socket pinning, TLS proxy, browser request interception or OS-level egress isolation is claimed.
- `BrowserControlBoundary` is an in-process trusted-controller boundary, not protection against arbitrary code executing in the same Python process.
- No login credentials, cookies, page contents, form values or file contents enter the approval or audit payload.
- Browser execution, Worker, Auto-Run, paid providers, payments, purchases, trading and money movement remain disabled/prohibited.
- Physical Android qualification and real isolated-worker egress qualification remain separate, deferred gates.

## Acceptance
BCS-01 is not complete until exact-head CI passes, tests demonstrate owner/session/tenant binding, receipt expiry and replay rejection, payload tampering rejection, Action Audit persistence and the absence of registered browser handlers. Browser execution must remain disabled after this checkpoint.
