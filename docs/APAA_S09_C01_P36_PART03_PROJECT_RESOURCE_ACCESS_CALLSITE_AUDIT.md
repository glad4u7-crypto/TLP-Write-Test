# APAA S09 C01 P36 Part 03 — Project and Resource Access Callsite Audit

Status: IMPLEMENTATION AUDIT RECORDED; CI PENDING; COLLABORATOR ACCESS NOT ENABLED.

## Scope

Audited the current Streamlit project entry point, persistent project registry, project access control, project action gateway wiring, and tenant-scoped memory/knowledge/checkpoint callsites. This is a source-level repository audit, not a live two-user OIDC/browser qualification.

## Verified current UI boundaries

- Authenticated project listing uses `registry.list_projects_for_owner(principal)`.
- Authenticated project selection/read uses `registry.get_for_owner(project_id, principal)`.
- The project selector is populated from the owner-only project list. Its display formatter uses the same tenant-scoped registry lookup.
- The project action gateway is constructed server-side with the current authenticated principal and session scope; task text does not receive the gateway or approval authority.
- Memory, knowledge, conversation, preferences and checkpoint operations pass the authenticated `TenantKey`; the SQLite queries shown in `core/memory.py` scope reads and writes by issuer + subject.
- The UI does not call collaborator ACL listing/lookup APIs. Collaborator access is therefore not enabled by this audit.

## Defect found and corrected

The new ACL regression test exposed that a registry instantiated for a grantee could reach owner mutation methods with the internal mutation capability and receive `KeyError` rather than an explicit authorization denial. The tenant-scoped SQL prevented the write, but the authorization contract was incomplete and the test correctly failed.

Correction:
- Added `ProjectAccessControl.is_owner(project_id, principal)`, which checks the exact issuer + subject pair against the immutable project owner row.
- `PersistentProjectRegistry.update_for_owner` and `delete_for_owner` now require this exact owner predicate when ACL is configured, before performing owner-tenant mutation.
- Added direct tests for the exact owner predicate.
- Existing collaborator update/delete regression now expects and receives `AuthorizationDenied`.

Relevant commits:
- `e52143f72c83eb51aeda371ec29cac58c5055901` — exact owner predicate.
- `8c3115fb20192ce1b2215ca5995084c2fb7b9387` — mutation boundary enforcement.
- `314a66cefd27afdc05c912b9aa5aa044c3805c6d` — owner predicate regression test.

## Remaining security gates

1. The ACL primitive is not wired into the UI, API routes, action gateway, file/resource retrieval or every project-linked memory/checkpoint operation. Do not enable collaborator access.
2. Owner grant/revoke controller/UI and durable grant/revoke audit events are not implemented.
3. A future collaborator must not receive task execution, mutation, secrets, invitations, browser or worker capability from a read grant.
4. Project-linked checkpoints need an explicit server-side project ownership/ACL check at save and retrieval boundaries before any collaborator sharing is enabled; a tenant key alone is not a project ACL.
5. Local prototype mode still has authentication disabled by default and must not be exposed publicly.
6. Live OIDC, two-user browser tests, revocation across sessions/devices and Android/PC real-device tests remain outstanding.

## CI result at time of writing

The preceding head `8c5f645f45017b6fda71f70429036e61589d0c9e` failed the Agent Foundation and Python Demo test jobs: `1 failed, 1094 passed, 8 skipped`. The failing test was `test_collaborator_cannot_update_or_delete_owned_project`; the cause was the missing explicit owner predicate described above. P20 and P23 workflows passed on that earlier head.

The correction commits above advanced the PR head to `314a66cefd27afdc05c912b9aa5aa044c3805c6d`. At the time of this report, no PR-triggered workflow runs or combined statuses had yet surfaced for that exact head. Its CI status is therefore **PENDING**, not PASS.

## Release posture

C01 remains OPEN / NOT COMPLETE. PR #11 remains Draft/Open/Unmerged. No collaborator access is activated. Auto-Run remains OFF; browser/worker remain disabled; no paid services, payment, host mutation, firewall change, deployment, merge or C02 start is authorized.
