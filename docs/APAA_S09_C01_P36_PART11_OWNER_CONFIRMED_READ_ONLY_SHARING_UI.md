# APAA S09-C01 — Owner-Confirmed Read-Only Project Sharing UI (Part 11)

## Implemented
The authenticated application now has an owner-controlled sharing panel, shown only when:
- the session has a validated authenticated Principal;
- the owner has explicitly configured the trusted OIDC issuer allowlist; and
- the owner has at least one project they own.

The panel:
- Lists only the exact owner's projects.
- Offers only same-issuer identities that previously signed in and explicitly opted into directory discovery.
- Uses an opaque directory ID as the selection value; the browser never supplies issuer or subject.
- Resolves the selected opaque ID server-side to a Principal and rechecks owner authority before granting.
- Requires a separate confirmation checkbox and submit action for each grant.
- Grants only the existing project read permission through `OwnerProjectAccessController`.
- Lists active grants and allows the owner to revoke one after a separate confirmation.
- Uses a provider display-name claim only as a sanitized display label. Email is never used as an identity key or displayed by this feature.
- Uses a short hash fingerprint as the fallback label for existing grants with no available display label; raw issuer and subject are not shown in the UI.

## Revocation and privacy behavior
- Revocation is persisted through the durable ACL and is checked on every project list/detail read.
- Turning off directory discoverability prevents new selection/resolution but does not silently revoke existing project grants.
- The owner can still identify an existing active same-issuer grantee for revocation after that grantee opts out of new discovery.
- Foreign-issuer or otherwise unlabeled existing grants remain revocable through an opaque fingerprint fallback.
- Directory visibility consent does not grant project access. A grant requires a separate owner confirmation.

## Permission boundaries
A read grant exposes only project metadata via the ACL-aware project list/detail boundary. It does not grant:
- project edits or deletion;
- approvals, task dispatch, or execution;
- file/resource access;
- personal memory or knowledge;
- conversation history or preferences;
- task checkpoint access.

Checkpoint project selection and checkpoint save/recovery remain owner-only. Personal memory remains tenant-private. No public invitation endpoint, email identity matching, client-controlled issuer/subject, or generic role/permission grant was added.

## Verification
- Added owner-only display-label behavior tests, including the case where a grantee opts out after an existing grant.
- Added application wiring regression checks for explicit grant/revoke confirmation and opaque directory selection.
- At implementation code head `43c05132a3ba23253d514f8363533a826bdde21c`, all six configured GitHub Actions checks completed successfully: foundation tests, demo, Android/PC Chromium browser verification, disposable Linux egress namespace qualification, real Podman executor/attestation-gate plumbing, and disposable rootless Podman lifecycle.
- The foundation suite reported `1,135 passed, 9 skipped`; the Android/PC Chromium smoke suite reported `9 passed`.
- These are CI and automated browser viewport results, not physical Android-device, live OIDC, or production-host qualification.
- Automated browser viewport verification does not substitute for a physical Android-device test.
- Live OIDC/two-user qualification, physical Android testing, owner-host worker qualification, and independent security review remain outstanding.

## Safety locks
PR #11 remains Draft/Open/Unmerged. No deployment, merge, paid provider, API key, payment, Auto-Run, browser automation, worker activation, or S09-C02 work is authorized by this implementation.
