# APAA S09 C01 P36 — Owner-Controlled Access Grant Primitive

Status: IMPLEMENTED AS A PERSISTENCE/AUTHORIZATION PRIMITIVE; NOT YET INTEGRATED INTO PROJECT RESOURCE ROUTING.

## Scope delivered

- Adds `core/project_access.py` with durable read-grant records in the existing private project SQLite database.
- A grant requires an authenticated owner Principal whose exact issuer + subject matches the project's stored owner.
- The grantee is bound to the exact issuer + subject pair; matching only a subject or only an issuer is insufficient.
- Access is owner-only until an explicit grant exists.
- Revocation is persisted and checked by each subsequent `has_access` call.
- Only the owner may grant, revoke, or list grant records.
- Owner self-grant/self-revocation is rejected; owner access remains inherent.
- Re-grant reactivates the unique grant record instead of creating duplicate rows.
- Revoked records remain available to the owner for review.
- Added focused tests for explicit grant, immediate revocation, forged/colliding identities, non-owner attempts, owner self-revocation, missing projects, persistence/reopen and re-grant.

## Important boundary / known incomplete work

This commit does NOT yet make shared projects visible or usable in the application. Existing `PersistentProjectRegistry` continues to enforce owner-only access. The new primitive must be integrated into every server-side read boundary before any collaborator access is enabled. It must not be treated as a UI-only gate.

Still required before enabling collaboration:
1. Integrate authorization into persistent registry and every project/action/resource lookup, with owner-write and explicit collaborator-read semantics.
2. Add session/cache invalidation or authorization re-check on every request so a revoked grantee cannot use stale project state.
3. Add owner-only UI for selecting a validated identity and granting/revoking access; never accept email/display-name as the authorization key.
4. Add durable security audit events for grant/revoke, without storing tokens or secrets.
5. Add tests proving collaborators cannot mutate, delete, invite onward, or access unrelated projects; include concurrency and stale-session scenarios.
6. Run exact-head CI and review the changed code on GitHub.
7. Perform live two-identity OIDC and Android-device qualification separately; neither is implied by CI.

## Safety posture

- No public/anonymous access is introduced.
- No invitation-by-email or self-registration is introduced.
- No deployment, merge, main-branch change, payment, paid provider, browser worker, or Auto-Run activation is authorized.
- PR #11 remains Draft/Open/Unmerged.
- C01 remains OPEN / NOT COMPLETE until its outstanding real-host and identity gates pass.

## Commits

- P35 audit: `ea0553785eee9e7a4a1f7edccde1c685d62e46e2`
- P36 access primitive: `957513b3ca094bf48fbde21afacf047045162705`
- P36 focused tests: `2e1fe21f17d4cd26080c37e1f11b84d193fde69b`
