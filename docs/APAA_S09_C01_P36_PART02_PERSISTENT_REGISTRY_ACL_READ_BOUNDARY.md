# APAA S09 C01 P36 Part 02 — Persistent Registry ACL Read Boundary

Status: IMPLEMENTED IN THE REGISTRY API; NOT ENABLED IN THE EXISTING UI OR GLOBAL APP WIRING.

## Delivered

- `SQLiteProjectStore.list_all_for_access_filter` and `get_by_id_for_access_filter` expose candidate records only to trusted server-side callers; they are not authorization decisions.
- `PersistentProjectRegistry` accepts an optional `ProjectAccessControl`.
- New `list_projects_for_principal` and `get_for_principal` APIs require an authenticated Principal and a configured ACL.
- Every call checks current owner/grant state through `ProjectAccessControl.has_access`; no collaborator result is cached. A revoke therefore denies the next registry read.
- Returned Project objects now carry the actual stored owner issuer and subject, not the registry tenant's identity.
- Existing owner APIs and owner-only update/delete predicates remain unchanged.
- If ACL is not configured, collaborator-facing read APIs fail closed.
- New tests cover explicit grant, no-default-access, exact grantee filtering, immediate revoke, read-only enforcement and missing-ACL denial.

## Security boundary / remaining work

- The existing Streamlit application wiring has not been switched to the ACL-aware registry. No collaborator is enabled by this commit.
- Every app/API/project/action/file/resource lookup must be audited and routed through the principal-aware read boundary before shared project display is enabled.
- Owner grant/revoke UI and durable grant/revoke audit events remain outstanding.
- Collaborator read access must not imply permission to execute tasks, mutate projects, access secrets, invite others, or use browser/worker functionality.
- The old trusted internal methods `get`, `list_projects`, and `get_by_id_for_internal_use` must remain internal-only and be removed from untrusted request paths.
- Session identity transitions and revocation must be checked at every request boundary; no cached project object or capability may bypass current ACL state.

## Safety

No public access, email invitation, self-registration, deployment, merge, payment, paid API, Auto-Run, browser or worker activation. PR #11 remains Draft/Open/Unmerged. C01 remains OPEN / NOT COMPLETE.
