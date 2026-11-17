# APAA-S04-C01-P08 — Authentication & Multi-User Authorization Foundation

Status: **Identity primitives only; not an active authentication system**

## P08 objective

Establish fail-closed authorization primitives before wiring a real authentication provider into the Streamlit UI or allowing project data to be shared across users.

## Implemented in this phase

- `core/identity.py` defines an immutable `Principal` asserted by trusted authentication middleware.
- `require_authenticated` rejects missing, unauthenticated, or malformed principals.
- `require_project_owner` rejects missing ownership data and mismatched user subjects.
- Unit tests cover missing identity, malformed identity, unauthenticated identity, matching owner and cross-user access denial.

## Important boundary

These functions do **not** authenticate anyone. They do not validate OIDC tokens, establish browser sessions, prevent session fixation, validate CSRF, or prove that a Principal came from a trusted source. A caller must only construct Principal after a trusted authentication adapter validates the identity provider's assertion. Never construct it from task text, query parameters, form fields, or other client-controlled values.

The current Streamlit app is not yet wired to an authentication provider. Until that integration is implemented and tested, this repository must not be treated as a secure multi-user deployment. Existing session-state separation is not a substitute for authentication.

## Next required work

1. Select a zero-cost, standards-based OIDC identity provider or a self-hosted provider; do not add paid APIs or require an API key.
2. Integrate Streamlit's supported authentication flow with server-side secrets; never commit client secrets, cookie secrets, or tokens.
3. Build Principal only from the validated server-side identity assertion.
4. Bind each project to an immutable owner subject and enforce ownership on every read, update and delete.
5. Test two real browser users, session expiry/logout, stale session, cross-user access, forged client values, and concurrent requests.
6. Keep all real-world execution handlers disabled until a separate security review approves the deployment.

## Safety constraints

- No payment, purchase, checkout, trading, or money movement.
- No paid provider or API keys; no charges.
- Auto-Run remains disabled.
- No shell, browser, network, email, arbitrary filesystem, or device-control handler is enabled.

## Release decision

**Not production approved.** This phase adds authorization building blocks only. A real authentication adapter and enforced resource ownership are still required.
