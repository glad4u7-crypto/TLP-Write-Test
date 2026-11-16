# APAA S09 C01 P36 Part 07 — Explicit Trusted Directory Privacy Consent

Status: IMPLEMENTED IN REPOSITORY; EXACT-HEAD CI PENDING; COLLABORATOR ACCESS REMAINS DISABLED.

## Delivered

- Added `SQLiteTrustedIdentityDirectory.is_discoverable()`, which reads the current visibility preference only for a server-authenticated Principal from an explicitly allowlisted OIDC issuer.
- Added an authenticated Streamlit privacy form for identities enrolled through the optional `trusted_identity_issuers` allowlist.
- Visibility is off by default. The user must explicitly submit the form to opt in or out.
- The UI explains that discoverability only allows same-issuer project owners to find the identity in the private directory. It does not grant project access, share projects, or enable collaborator visibility.
- No email, user-entered issuer/subject, invitation endpoint, public directory, or automatic access grant is introduced.
- Added tests for private-by-default status, explicit opt-in/out transitions and rejection of an unallowlisted issuer.

## Security boundary

- The directory UI is rendered only when the current authenticated Principal has been enrolled under the explicit issuer allowlist.
- Owner identity selection and grant confirmation UI are not yet enabled.
- The existing owner-only project listing remains unchanged.
- Existing project ACL grants remain dormant in the application because collaborator read paths are not exposed.
- Do not enable collaborator access until every applicable project read boundary enforces the ACL and immediate revocation has been verified in live two-user OIDC sessions.

## Verification

Implementation commits:
- Discoverability status lookup: `0f1ba9712b773b2a74badd5d79dcc85e8d7ad371`
- Discoverability tests: `be40dff77d2079810b791660aa372bff6d97f2b0`
- Authenticated privacy UI: `c169ec3a3dde8a26c86ca6fc09dd6d31826768da`

The exact-head CI for the latest implementation must complete successfully before this part is marked CI-verified. A missing workflow result is PENDING, not PASS.

## Release locks

PR #11 remains Draft/Open/Unmerged. Auto-Run OFF. Browser and worker disabled. No paid providers, API keys, payments, deployment, host mutation, firewall changes or C02 start. Physical Android and live OIDC testing remain owner-side requirements.
