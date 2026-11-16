# APAA S09 C01 P36 Part 07 — Revocation, Session Transition and Multi-User Regression

Status: AUTOMATED REGRESSION IMPLEMENTED; live OIDC multi-user E2E remains external.

## Covered in repository tests

- Two independent session-state objects retain separate identity-bound drafts.
- Switching the identity in one session clears its pending identity-bound state without affecting the other session.
- Same-subject identities from different issuers remain distinct.
- A grant is immediately denied after revocation by an already-constructed ACL reader and by a reconstructed store/ACL instance.
- Grant → revoke → regrant → revoke produces four distinct append-only audit events in order.
- Logout and subsequent identity switch cannot reuse a pre-logout approval receipt.
- Existing tests cover immutable access-event update/delete rejection and project registry revocation behavior.

## Not claimed

These are deterministic repository tests, not a live two-user OIDC provider test. They do not prove cross-device cookie/session invalidation, provider logout propagation, real browser storage isolation or concurrent production database behavior. Those require an owner-controlled OIDC test environment and independent test accounts.

## Test file

`tests/test_project_access_session_regression.py`

The exact-head CI run must complete before this part is marked CI-verified.
