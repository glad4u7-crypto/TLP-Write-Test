# APAA S09-C01 — Application ACL Read-Facade Wiring (Part 10)

## Implemented
The authenticated Streamlit application now constructs `ProjectAccessControl` over the configured durable `SQLiteProjectStore` and injects it into `PersistentProjectRegistry`.

Application read helpers now use the principal-aware ACL boundary:
- Project listing calls `list_projects_for_principal(principal)`.
- Project detail calls `get_for_principal(project_id, principal)`.
- The project selector formats labels from the already-authorized project list, rather than performing an unguarded secondary lookup by project ID.
- A session holding a pre-ACL registry is rebuilt when the registry has no configured ACL object.

## Deliberately retained owner-only boundaries
- Project creation remains behind the existing approval gateway.
- Project mutation and deletion remain owner-only.
- Checkpoint project selection continues to call `list_projects_for_owner(principal)`; `OwnerProjectCheckpointAccess` rechecks ownership before save/recovery.
- Personal memory, knowledge, conversation history, and preferences remain tenant-private. No sharing model was added for those resources.
- No grant/revoke UI was added. Existing grants, if any, are checked by the durable ACL on every project list/detail read.

## Tests added
`tests/test_app_project_acl_wiring.py` protects:
- ACL construction and injection into the persistent registry.
- Application list/detail use of principal-aware ACL methods.
- Owner-only checkpoint selection.
- Removal of the old unguarded project-name lookup.
- Rebuilding legacy session registries that lack an ACL.

The existing registry tests cover grant filtering, exact issuer+subject matching, fail-closed behavior without ACL, read-only mutation denial, and immediate read denial after revocation.

## Safety and qualification
- This change exposes only project metadata through the ACL-aware project read facade. It does not add access to personal memory, knowledge, conversation history, preferences, checkpoints, mutation, or execution.
- No owner grant/revoke UI is enabled in this part.
- CI for the new exact head must complete before this implementation is called verified.
- Automated Chromium viewport checks are not physical Android testing.
- Live OIDC/two-user qualification, physical Android testing, owner-host worker qualification, and independent security review remain outstanding.
- PR #11 remains Draft/Open/Unmerged. No merge, deployment, paid provider, API key, payment, Auto-Run, browser automation, or worker activation is authorized.
