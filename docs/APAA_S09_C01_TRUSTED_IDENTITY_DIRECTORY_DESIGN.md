# APAA S09 C01 — Trusted Identity Directory Design Contract

**Status:** DESIGN READY FOR OWNER REVIEW; NOT IMPLEMENTED OR ENABLED  
**Scope:** prerequisite design for a future owner-facing read-only project grant/revoke workflow.

## 1. Decision boundary

The current `OwnerProjectAccessController` accepts only server-verified `Principal` objects. It must never receive an identity assembled from a form, URL parameter, task prompt, email address, display name or client-side JavaScript.

The current repository has no trusted directory adapter, no provider-specific user lookup configuration and no owner-approved invitation policy. Therefore the owner grant/revoke UI remains disabled. This document defines a provider-neutral integration contract; it does not claim that a directory or invitation system exists.

## 2. Recommended initial model: previously authenticated identities only

For the first release, use a **closed, owner-controlled directory**:

1. A candidate identity must first authenticate successfully through the same explicitly allowlisted OIDC issuer used by the APAA deployment.
2. The server-side OIDC adapter validates the token/session using the provider's supported library and derives the immutable `(issuer, subject)` pair.
3. The directory stores only the minimum identity record needed for owner selection: issuer, subject, first-seen timestamp, last-seen timestamp and an optional provider-verified display label. Do not use email as the authorization key.
4. The owner UI lists eligible identities from this server-side directory. The owner selects a record; the browser submits only an opaque directory record ID.
5. The server resolves that opaque ID back to the stored issuer+subject pair, verifies that it is active and belongs to an allowed issuer, then constructs/uses the already authenticated `Principal` from trusted server-side identity data.
6. The server calls `OwnerProjectAccessController.grant_read` or `revoke_read`. The controller independently rechecks exact project ownership.
7. If the selected identity has not authenticated, is disabled, belongs to another issuer, or cannot be resolved, the operation fails closed.

This avoids trusting typed emails or free-form issuer/subject values and avoids an unauthenticated public invitation endpoint. It also means a person must have an account in the configured OIDC tenant and sign in once before the owner can select them.

## 3. Required adapter contract

A future implementation should provide a narrow interface equivalent to:

- `record_authenticated_principal(principal)`: accept only a Principal produced by the trusted OIDC middleware; idempotently upsert the issuer+subject identity.
- `list_owner_selectable_identities(owner, project_id)`: require authenticated owner and exact project ownership; return minimal, paginated identity summaries from the configured issuer only.
- `resolve_selected_identity(owner, project_id, opaque_directory_id)`: recheck owner authority and resolve the opaque ID server-side to a currently active authenticated directory identity; return a trusted Principal, never raw client fields.
- `disable_directory_identity(admin_context, opaque_directory_id)`: optional administrative disable path; must not silently rewrite historical grant records.
- `audit_directory_event(...)`: append-only, redacted events for enrollment, lookup, disable and selection.

No generic role-management API is permitted. The only current project permission is read access.

## 4. Identity and issuer rules

- Authorization identity is always the exact pair `(iss, sub)`; never subject alone.
- Configure an explicit OIDC issuer allowlist. Do not accept arbitrary issuers from client input.
- Reject missing, blank, malformed, untrusted, expired or unauthenticated identities.
- Treat email, email_verified, preferred_username and display name as presentation/discovery metadata only; none may replace `sub`.
- If the provider supports multiple tenants/issuers, each issuer must be separately configured and explicitly approved. Cross-issuer selection is disabled by default.
- Do not infer an account's authorization from a matching email address.
- Never log raw ID/access/refresh tokens, cookies, authorization codes or secrets.

## 5. Opaque selection token requirements

The browser-visible identifier must be an unpredictable opaque record ID, not a serialized issuer/subject pair. It is a selector, not a bearer capability:

- every use requires a currently authenticated owner session;
- every use rechecks exact project ownership server-side;
- every use resolves the ID from the trusted directory database;
- stale, deleted, disabled, foreign-issuer or unknown IDs fail closed;
- IDs must not embed personal data or credentials;
- selection alone must not grant access; the owner must explicitly confirm the exact project and read-only permission.

## 6. Persistence and audit requirements

- Store directory records in protected persistent storage, separate from browser/session state.
- Enforce a unique constraint on (issuer, subject).
- Use transactions for identity enrollment and audit append.
- Keep grant/revoke audit events immutable; directory disable must not erase grant history.
- Apply retention and deletion rules approved by the owner without weakening active authorization checks.
- Do not store OIDC tokens or secrets in the directory.
- Protect the database with restrictive filesystem permissions and backup/restore controls.

## 7. Mandatory tests before UI activation

1. Reject Principal objects not produced by the trusted authentication adapter.
2. Reject unauthenticated, malformed, blank and unallowlisted-issuer identities.
3. Same subject under different issuers resolves to different records.
4. Email changes do not change authorization identity.
5. Client cannot supply or override issuer, subject, roles or authentication status.
6. Opaque IDs cannot be used without an authenticated owner session.
7. Non-owner, foreign-project owner and stale session cannot list or resolve identities.
8. Directory identity disable blocks new grants and any policy-defined future access; existing grants are handled by an explicit audited revocation policy.
9. Owner must explicitly confirm a read-only grant for the exact project and exact selected identity.
10. Revoke denies access on the next server-side resource check, including an already-open second session.
11. No read grant authorizes mutation, task execution, files, memory, conversations, preferences, checkpoints, secrets, browser or worker operations.
12. Audit records contain actor and target issuer+subject identifiers in protected storage but no tokens, cookies or secret values.

## 8. Security and product acceptance gates

Before enabling any UI/API:

- Owner approves the closed-directory model and OIDC issuer(s).
- Provider adapter and issuer validation are implemented and reviewed.
- All relevant project read routes are proven to call the ACL check; no collaborator access is inferred from UI visibility.
- Resource authorization regression suite passes.
- Live two-identity OIDC test passes on a private HTTPS non-production instance.
- Android physical test verifies owner grant, reader access, revocation, stale-session denial and browser storage boundaries.
- Independent reviewer approves the exact code SHA and evidence.

## 9. Explicitly out of scope

This design does not authorize open sign-up, email-based invitations, public invitation links, self-service role changes, write/execute grants, cross-tenant sharing, paid identity services, automatic execution, production deployment or C02 work.

**Current safe behavior remains owner-only access.** The directory and collaborator UI are not implemented or enabled by this design.
