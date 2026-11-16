# APAA S09-C01 — P35-A Global Owner Bootstrap and Recovery Design

**Status:** DESIGN RECORDED; IDENTITY GUARD IMPLEMENTED IN ISOLATION; CONFIG ADAPTER/INTEGRATION/RECOVERY AND LIVE QUALIFICATION NOT COMPLETE  
**Date:** 2026-11-16  
**Branch:** feature/apaa-s09-c01-p16-oci-lifecycle  
**PR:** #11 — Draft / Open / Unmerged

## 1. Purpose and security boundary

This design defines how APAA may establish exactly one initial product owner/admin independently of project creator ownership. It is a design artifact, not a bootstrap implementation, deployment instruction, credential request, or authorization to activate administration.

The global owner identity is the exact pair `(trusted OIDC issuer, OIDC subject)`. Email, display name, username, phone number, browser input, query parameters, task text, model output, project creator status, or a directory display record are never sufficient to establish global ownership.

## 2. Required invariants

1. No owner is inferred from the first user to sign in.
2. No owner is created automatically when the database is empty.
3. Missing, malformed, duplicated, or inconsistent owner configuration fails closed; privileged owner actions remain unavailable.
4. Exactly one active global owner identity is accepted in the initial release. No default administrator group or public self-service enrollment exists.
5. Owner identity is read only from trusted server-side deployment configuration or an offline, owner-authorized provisioning artifact. The browser cannot set or override it.
6. Issuer comparison uses the configured canonical HTTPS issuer string and subject comparison is exact; no email or case-folded identity matching.
7. Project ownership and global APAA ownership are separate authorities. Creating a project never grants global admin rights.
8. Collaborators/read-grantees cannot grant access onward, change owner configuration, recover the owner account, or alter security policy.
9. Owner bootstrap/rekey operations are auditable without recording tokens, secrets, raw authentication claims, or private keys.
10. If owner identity cannot be resolved confidently, all owner-only controls fail closed while ordinary authenticated non-admin project access remains subject to existing project ACL checks.

## 3. Provisioning model (proposed; not implemented)

### 3.1 Out-of-band initial provisioning

- An operator with control of the deployment configuration provisions the exact OIDC issuer and subject using a protected server-side configuration channel.
- The issuer must already be present in the explicit trusted OIDC issuer allowlist. The configured owner issuer must match one of those trusted issuers exactly.
- The subject is obtained from an independently authenticated owner session and verified out of band by the deployment owner; it is never copied from a browser form or task instruction.
- Configuration is injected at deployment time from a secret/configuration manager or a root-/owner-readable file with restrictive permissions. It is not committed to Git, written to ordinary logs, or stored in browser/session state.
- Startup validates schema, issuer allowlist membership, bounded non-empty subject, and uniqueness. Any failure disables global owner administration and emits a sanitized diagnostic.
- There is no “claim ownership” web endpoint and no first-login-wins fallback.

### 3.2 Immutable runtime behavior

- Runtime owner identity is loaded once through a trusted configuration adapter and exposed as an immutable value object.
- Every global-admin action checks the current server-authenticated Principal against the exact configured issuer + subject pair at the server boundary.
- UI visibility is not authorization. Every mutation and privileged read rechecks owner authority server-side.
- A normal project owner is not implicitly the global owner.
- The initial scope is limited to global owner-only configuration and account-level administration. It does not create additional roles or expand collaborator project grants.

## 4. Recovery and re-key model (proposed)

Recovery must not depend on an active browser session belonging to the compromised/lost owner account.

1. The deployment operator first disables owner-only administrative actions using a fail-closed maintenance setting; normal project access remains governed by existing ACL policy.
2. The operator verifies control of the deployment and the new OIDC identity out of band, including the exact issuer and subject from a fresh authenticated session.
3. A re-key request is prepared outside the running application and includes a change identifier, previous owner fingerprint (not raw subject), new owner issuer/subject, reason code, timestamp, and operator identity evidence held outside the repository.
4. The change requires an independently reviewed authorization record and a protected configuration update. A single browser request, model response, project grant, email link, or database row cannot authorize re-key.
5. The application restarts/reloads through a controlled maintenance process; startup verifies the new owner config and trusted issuer membership. If verification fails, global owner actions stay disabled.
6. The change is recorded in an append-only audit channel with old/new identity fingerprints, change ID, result and timestamp. Raw subjects, tokens and secrets are excluded from ordinary logs.
7. The prior owner identity loses global authority immediately after the new configuration is accepted. Project ownership is not silently transferred; any project transfer is a separate explicit and audited operation.

**Recovery is not yet implemented.** No CLI, web endpoint, automatic recovery code, key rotation flow, or database-driven owner replacement is included by this design.

## 5. Threat model and mitigations

| Threat | Required mitigation |
|---|---|
| First-user takeover | Never bootstrap from first login; require out-of-band configured owner |
| Forged browser/task identity | Principal only from trusted auth adapter; owner identity never accepted from client |
| Same subject at different issuer | Compare issuer + subject pair exactly |
| Email/display-name collision or change | Never use email/display name as identity key |
| Unauthorized config edit | Protected deployment configuration, restrictive filesystem/secret-manager ACLs, audited operator change |
| Empty or malformed config | Disable owner actions; no fallback |
| Stale session after re-key | Re-evaluate configured owner on every privileged request; invalidate owner-bound session capabilities on config generation change |
| Rollback to former owner config | Protected deployment change history and monotonic deployment revision/rollback controls; do not claim cryptographic anti-rollback until separately qualified |
| Compromised owner session | Operator-controlled out-of-band disable/re-key; short-lived session capabilities and explicit reauthentication |
| Audit log tampering | Append-only protected audit destination; integrity verification and independent retention outside the app database |
| Confusion between project owner and global owner | Separate types, APIs, configuration and tests; never infer global role from project ownership |

## 6. Required implementation interfaces (future work)

Implementation must be split into independently testable units:

- `GlobalOwnerConfig`: immutable, validated issuer + subject pair and configuration generation.
- `load_global_owner_config(trusted_issuers, source)`: server-only loader; no browser/session/task input.
- `is_global_owner(principal, config)`: exact issuer + subject comparison after trusted Principal validation.
- `require_global_owner(principal, config)`: fail-closed authorization guard.
- Startup policy: distinguish “owner not provisioned” from “invalid configuration”; both disable global-admin actions, but invalid configuration must surface a sanitized security error.
- Audit adapter: append-only owner bootstrap/re-key event with opaque identity fingerprints and no credential material.

Do not introduce global roles through mutable `Principal.roles`, generic permission strings, project ACL grants, or user-editable database fields.

## 7. Mandatory test matrix before implementation acceptance

- Empty config disables global owner actions and never claims the first login.
- Malformed config, missing issuer, non-HTTPS issuer, untrusted issuer, empty/oversized subject and duplicate config fields fail closed.
- Same subject at another issuer is denied.
- Same issuer with a different subject is denied.
- Exact configured pair is accepted only when Principal is authenticated and produced by trusted middleware.
- Unauthenticated, malformed, forged, task-derived, query-derived and browser-submitted Principal values are denied.
- Project creator/owner and project read-grantee are not global admins unless their exact identity independently matches configured global owner.
- Config generation change invalidates cached owner authorization and owner-bound approvals.
- Re-key requires maintenance disable + out-of-band authorization record; web/UI/task route cannot perform it.
- Audit records contain only fingerprints/change metadata and reject update/delete.
- Concurrent or partial config update leaves owner actions disabled, never with mixed issuer/subject values.
- Recovery to an older configuration is rejected or explicitly detected by a separately qualified monotonic deployment control.
- Integration tests exercise every global-admin API, not only UI visibility.

## 8. Release gates and evidence

Before enabling global owner administration:
- implementation and focused tests are reviewed on the exact PR head;
- protected configuration permissions and deployment secret handling are inspected;
- live OIDC owner login is tested using the configured issuer;
- owner identity is independently verified out of band;
- recovery/re-key is rehearsed in a disposable environment with rollback/failure tests;
- audit retention and tamper evidence are independently reviewed;
- physical Android owner login/session transition is tested if Android is the primary client;
- independent reviewer attestation is bound to the exact code and evidence manifest.

CI tests alone cannot prove out-of-band identity, secret custody, deployment permissions, recovery operator authority, or production anti-rollback.

## 9. Explicit non-goals and safety locks

This design does not implement account invitations, general roles, public registration, payment/purchase authority, trading/money movement, paid API activation, Auto-Run, browser automation, worker activation, deployment, host/firewall changes, or production rollout. PR #11 must remain Draft/Open/Unmerged. S09-C02 must not start until S09-C01 is formally closed.

## 10. Current disposition

- P35-A design: **RECORDED**.
- P35-A implementation: **NOT IMPLEMENTED**.
- Global owner bootstrap/recovery qualification: **BLOCKED / NOT VERIFIED**.
- P35-B/C/D narrow project read-only sharing implementation: **IMPLEMENTED IN REPOSITORY; live qualification BLOCKED**.
- Live OIDC/two-user verification, physical Android and independent review: **BLOCKED**.
- S09-C01: **OPEN / NOT COMPLETE**.
- S09-C02: **NOT STARTED**.

**Checkpoint:** `APAA-S09-C01-P35A-GLOBAL-OWNER-BOOTSTRAP-RECOVERY-DESIGN-RECORDED`


## 11. Isolated identity-guard implementation update (2026-11-16)

Added `core/global_owner.py` and `tests/test_global_owner.py`. The pure server-side guard accepts only a caller-supplied server configuration mapping, validates exact fields, requires an HTTPS issuer in the trusted issuer collection, bounds/validates the subject, and compares authenticated Principals by exact issuer + subject. Missing config, malformed identities, untrusted issuers and non-matching principals fail closed. It exposes an opaque SHA-256 generation/fingerprint for cache invalidation/audit correlation; the fingerprint is not an authorization key.

This is an isolated authorization primitive only. It does not read environment variables, files, browser state, task text or model output; does not establish secure configuration custody; does not implement strict raw-config parsing, startup policy, global-admin API integration, session invalidation, audit persistence, recovery/re-key, or live OIDC. No UI or endpoint exposes it. The application does not yet load or activate a global owner. Focused tests were added but must pass exact-head CI before any test-pass claim.

Updated status: design RECORDED; isolated guard IMPLEMENTED; deployment config adapter, application integration, recovery/re-key and external qualification NOT IMPLEMENTED/BLOCKED.


## 12. Server-side settings adapter and startup integration (2026-11-16)

Added `core/global_owner_config.py` as a narrow adapter over the deployment-provided `[apaa].global_owner` mapping. It accepts only the exact issuer/subject pair, requires the issuer to appear exactly once in the explicit trusted-issuer collection, and delegates identity-shape validation to the immutable guard. Missing owner configuration returns an unprovisioned state; it never infers the first authenticated user. A present but malformed/untrusted configuration raises a configuration error.

The Streamlit startup path now loads this optional mapping only after a trusted OIDC Principal has been produced. Invalid owner configuration displays a sanitized security error and leaves global administration disabled while ordinary authenticated project access remains governed by the existing ACL checks. A valid configuration is loaded as an immutable runtime object but is not placed in browser/session state, exposed in UI, or wired to any privileged endpoint. No owner identity has been provisioned by this code change.

The startup stores only the opaque configuration generation in server session state. When that generation changes, including removal or invalidation, the adapter clears the enumerated owner-bound session capability keys. No raw subject, token or secret is stored. There are currently no global-owner API actions or owner-bound approval receipts to activate; future integrations must use the guard at each server API boundary and extend invalidation coverage before any feature can be enabled.

Tests added for absent configuration/no first-login bootstrap, exact trusted issuer, malformed and duplicate issuer configuration, untrusted issuer, owner-bound cache invalidation, and Streamlit startup behavior for absent/invalid/valid configuration. The valid-config test explicitly asserts that loading configuration does not create an authorized session or activate an admin action.

**Custody limitation:** this adapter consumes the framework's server-side settings mapping. It does not prove secret-manager custody, file ownership/mode, deployment operator access, atomic secret rotation, or monotonic rollback protection. Those remain external qualification requirements. No raw config file, owner subject, credential, token, key or secret is committed.

**Disposition:** server-side adapter and fail-closed startup loading IMPLEMENTED; focused and full exact-head CI PENDING; privileged Global Admin API wiring NOT IMPLEMENTED; session invalidation implemented for reserved owner-bound keys only; recovery/re-key and durable audit NOT IMPLEMENTED; live OIDC, physical Android and independent review BLOCKED. Global Owner remains inactive. All release/safety locks remain unchanged.
