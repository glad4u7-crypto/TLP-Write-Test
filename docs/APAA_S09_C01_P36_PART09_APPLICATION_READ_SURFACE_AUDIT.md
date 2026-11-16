# APAA S09-C01 — Application Read-Surface Audit (Part 09)

## Scope
Audit the current Streamlit application read paths before enabling collaborator access. This is a code-path inventory, not a production or live-identity qualification.

## Verified application boundaries
- Authenticated project listing uses `registry.list_projects_for_owner(principal)`.
- Authenticated project detail uses `registry.get_for_owner(project_id, principal)`; authorization denial is converted to no visible project.
- The project selector is populated from the owner-filtered list. Its display formatter reads the selected project name from the same owner-scoped registry.
- The project summary panel obtains its project through `visible_project`, so it remains owner-only.
- Persistent memory UI is shown only for an authenticated Principal. Memory, knowledge, search, conversation, preference, and checkpoint reads are passed a tenant derived from the validated issuer + subject identity.
- Checkpoint recovery uses `OwnerProjectCheckpointAccess.latest_checkpoint`, which rechecks that the project belongs to the authenticated tenant before returning a checkpoint.
- Local prototype mode filters projects to the explicit `local-prototype` owner marker and does not expose authenticated persistent memory.

## Existing ACL primitives
- `PersistentProjectRegistry.list_projects_for_principal` and `get_for_principal` provide explicit ACL-filtered reads and fail closed if ACL is not configured.
- These collaborator read methods recheck active grants; the existing regression test verifies reads disappear after revocation.
- `ProjectAccessControl` stores owner-controlled read grants and audit events; `OwnerProjectAccessController` restricts grant/revoke/list operations to the exact owner identity.

## Blocking finding — do not enable collaborators yet
The application currently wires authenticated project listing and detail to owner-only methods, and checkpoint association/recovery is owner-only. The collaborator-aware registry methods are not wired into the application UI. This is safe (no accidental collaborator exposure), but it means the collaborator feature is not yet available end-to-end.

Do not add a grant UI or claim collaborator access is operational until:
1. Every project-associated read surface is enumerated and routed through a single authenticated ACL boundary.
2. Checkpoint policy is explicitly decided (remain owner-only or gain a separately tested read-only collaborator path).
3. Memory/knowledge/conversation/preferences are explicitly kept tenant-private unless a separate sharing model is designed and tested.
4. All mutation and execution routes remain owner-only and cannot be reached through read grants.
5. Tests cover direct resource IDs, list/detail parity, revocation immediately removing reads, identity switching, and unauthorized/missing ACL fail-closed behavior.
6. UI and browser tests verify the same boundaries without treating viewport emulation as physical Android testing.

## Next implementation sequence
- Keep collaborator grants disabled in the UI.
- Build an application-level read facade that is constructed from the validated Principal and the durable ACL store.
- Route project list/detail reads through that facade, with owner and explicitly granted reader behavior.
- Keep project checkpoints and personal memory tenant-private in this phase.
- Add app-level tests for each read surface and negative mutation/execution attempts before exposing any owner grant control.

## Evidence and limitations
- Exact reviewed branch: `feature/apaa-s09-c01-p16-oci-lifecycle`.
- Reviewed application commit before this audit: `163cdacdc234aa92737a06f21245cebac44359ae`.
- At that exact head, all six configured GitHub Actions checks completed successfully, including Python tests, demo tests, disposable rootless Podman lifecycle, Podman executor/attestation plumbing, Linux egress namespace qualification, and Android/PC Chromium browser verification.
- Browser verification is automated Chromium viewport coverage only. It is not a physical Android-device test.
- No live private OIDC deployment, two-real-user external qualification, production host qualification, or independent security review is claimed.
- PR #11 remains Draft/Open/Unmerged. No deployment, merge, paid provider, API key, payment, Auto-Run, browser automation, or worker activation is authorized by this audit.
