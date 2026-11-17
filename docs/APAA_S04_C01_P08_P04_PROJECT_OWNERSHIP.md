# APAA-S04-C01-P08-P04 — Project Ownership Enforcement

Status: **Owner-scoped registry and UI enforcement committed; current-head CI pending**

## Implemented

- Projects now carry an immutable `owner_subject` value at creation.
- The trusted project gateway captures the server-validated Principal subject; the client payload is strictly limited to `name` and `description`.
- The UI passes the authenticated Principal to the gateway and rebuilds the gateway when the signed-in subject changes.
- Authenticated users see only projects matching their subject.
- User-facing project lookup checks ownership and safely handles stale/foreign selected IDs.
- Registry methods provide owner-scoped list, read, update, and delete checks.
- Tests cover owner assignment, payload owner spoofing, owner list/read/update/delete, and non-owner denial.

## Important limitations

- Project registry remains in-memory and currently scoped to a Streamlit session. This is not a persistent multi-tenant database.
- The UI currently exposes project creation and viewing; update/delete APIs are guarded and unit-tested but no UI controls are exposed yet.
- Existing projects created before owner assignment may have `owner_subject=None`; they are intentionally invisible to authenticated users until a controlled migration/ownership recovery process exists.
- Streamlit session-state separation and OIDC identity mapping still need live two-browser verification with an actual configured provider.
- The in-process mutation capability is not a boundary against arbitrary Python execution in the app process.
- Do not deploy publicly until OIDC configuration, secure secrets, real browser isolation, persistence, and production authorization review are complete.

## Safety constraints

No payment, purchase, trading, paid provider, API key, shell, arbitrary network, browser automation, email, filesystem, or device-control execution is enabled. Auto-Run remains disabled.

## Release decision

**Not production approved.** Continue local prototype testing only.
