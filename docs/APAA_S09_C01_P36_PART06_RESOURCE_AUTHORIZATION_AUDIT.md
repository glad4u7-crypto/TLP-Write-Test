# APAA S09 C01 P36 Part 06 — Project, Action, File, Memory and Checkpoint Authorization Audit

Status: AUDIT COMPLETE; collaborator exposure remains DISABLED.

## Boundary findings

| Surface | Current enforcement | Collaborator grant effect |
|---|---|---|
| Project listing | Authenticated app uses owner-tenant listing; collaborator-facing listing is not wired | No collaborator project listing |
| Project lookup | UI lookup uses owner-scoped registry method | No collaborator project lookup |
| Project mutation/action | Trusted server-side Principal, session-bound gateway and one-time approval receipt; create payload is allowlisted | Read grant cannot execute or mutate |
| File/resource automation | No collaborator-facing file automation route is exposed in the current app surface | No file authority is granted |
| Memory/knowledge | SQLite queries and mutations are scoped to exact tenant issuer + subject; writes require explicit consent | Private memory is never shared |
| Conversation history/preferences | Exact tenant scope; preference writes require consent | No collaborator visibility |
| Task checkpoints | Exact tenant issuer + subject scope and explicit consent; app project choices originate from owner-only project listing | No collaborator checkpoint visibility |

## Audit result and deliberate restriction

- The new owner controller grants only project read visibility at the ACL primitive level.
- The application does not pass that ACL into the authenticated registry used by the current Streamlit UI. It therefore continues to expose only owner-owned projects.
- No generic collaborator action, file, memory, conversation, preference or checkpoint authorization path exists.
- Checkpoint records are tenant-private, but the memory-store primitive does not independently prove that an arbitrary project ID belongs to that tenant. The current UI constrains choices to owner-visible projects; any future API must add a project-ownership check before accepting checkpoint association.
- Internal unscoped store helpers remain trusted implementation details and must not be exposed as client/API routes.

This is a fail-closed audit outcome: collaborator grants do not change any action, file, memory or checkpoint permission. No collaborator UI/API is enabled.

## Evidence added in this batch

- `tests/test_project_access_security_matrix.py` checks immediate revocation through reconstructed registry/store objects, issuer+subject binding, no-ACL collaborator denial, memory/checkpoint tenant isolation and explicit consent.
- Existing action and approval tests continue to cover session-bound receipts and audit-before-execution failure behavior.

## Remaining work

Before any collaborator UI/API is enabled, implement a project-aware checkpoint association guard, review all future file/resource adapters, and add real two-user OIDC tests. No permission is inferred from a project ID, UI selection or user-supplied task payload.
