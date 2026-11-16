# APAA S09 C01 — P35 Owner Access and Permission Boundary Audit

**Checkpoint:** `APAA-S09-C01-P35-OWNER-ACCESS-PERMISSION-AUDIT`  
**Audit date:** 2026-11-16  
**Audited branch:** `feature/apaa-s09-c01-p16-oci-lifecycle`  
**Audited code head:** `bab527177a5e2965bac616ce3bf84a59250676c4`  
**PR:** #11 — Draft / Open / Unmerged  
**Disposition:** repository code review recorded; production/live identity qualification remains BLOCKED.

This document records what was inspected and what the current code actually proves. It is not a claim that a live identity provider, public deployment, invitation system, or production access-control service has been tested.

## 1. Exact-head CI evidence inspected

All four workflows completed successfully on the audited code head:

- Agent Foundation CI #973 — PASS. The Android-sized Chromium viewport smoke job, Python test job, and disposable Linux egress namespace qualification job all completed successfully.
- Python Demo CI #1048 — PASS. Test suite and demo smoke job completed successfully.
- APAA P20 Rootless Podman Runtime Qualification #102 — PASS.
- APAA P23 Rootless Podman Executor Integration #84 — PASS.

This is repository CI and disposable-runner evidence. It does not qualify a real operator-owned Linux host, a production Android device, a live OIDC provider, or a production worker.

## 2. Files and boundaries inspected

The review inspected the current branch versions of:

- `app.py`
- `core/streamlit_auth.py`
- `core/identity.py`
- `core/session_security.py`
- `core/projects.py`
- `core/project_actions.py`
- `core/persistent_projects.py`
- `core/sqlite_project_store.py`
- `core/sqlite_security_store.py`
- `core/approvals.py`
- `tests/test_streamlit_auth.py`
- `tests/test_identity.py`
- `tests/test_session_security.py`
- `tests/test_streamlit_approval.py`
- `tests/test_projects.py`
- `tests/test_persistent_projects.py`
- Existing S04 P08 live-auth and ownership evidence documents.
- S09 C01 P31 final evidence inventory.

## 3. Verified controls already present

### 3.1 OIDC identity adapter

- The app can use Streamlit's OIDC login and constructs a Principal only from server-exposed identity claims.
- The adapter requires a logged-in state, an HTTPS issuer, bounded ASCII subject, finite expiration/issued-at values and acceptable clock skew.
- It rejects malformed or expired identity claims.
- Project identity uses the issuer + subject pair, not subject alone.

### 3.2 Session transition and logout

- Identity changes clear identity-bound project selection, drafts, approval authority, execution gateway and task state.
- Logout clears the identity-bound session state before calling the Streamlit logout action.
- A missing identity marker with leftover identity-bound state is treated as an orphaned session and cleared.
- Tests cover same-subject/different-issuer transitions and pre-logout approval replay denial.

### 3.3 Project ownership

- Project records carry owner issuer and owner subject.
- Authenticated listing and lookup are scoped to the exact issuer + subject.
- Persistent registry access is tenant-bound and rejects cross-issuer and cross-subject reads/mutations.
- The trusted project gateway takes ownership from the server-side Principal, not from the user task payload.
- Legacy unscoped projects are not automatically adopted as belonging to a logged-in user.

### 3.4 Approval boundary

- Project creation is separated into review and explicit confirmation.
- The approval receipt is short-lived, payload-bound, session-bound and one-time.
- Persistent approval nonce consumption is transactionally stored.
- The task text does not receive the approval authority or execution gateway.
- Existing tests cover changed payloads, cross-session receipt rejection, duplicate confirmation and task-text non-authorization.

### 3.5 Data storage

- Project and security SQLite stores enforce owner-only database file permissions and reject symlinked path components.
- Project SQL predicates use the issuer + subject tenant key.
- Durable audit and approval nonce storage are separate from user task content.

## 4. Findings and remaining gaps

### Finding F-01 — Local prototype mode does not enforce authentication

**Severity:** HIGH if exposed beyond a private local development environment.  
**Observed behavior:** `app.py` sets `auth_required` from `[apaa].require_auth`, defaulting to false. Without that setting, the app explicitly enters local prototype mode and displays a warning that authentication is not enforced and the instance must not be exposed publicly.  
**Interpretation:** This is an acknowledged development mode, not a secure multi-user deployment. The warning is not a network access-control mechanism.  
**Required closure:** Before any shared/public deployment, require OIDC at deployment configuration/startup, configure private OIDC secrets and the protected approval signing secret, and verify the deployment cannot be reached in unauthenticated mode. No public deployment is approved by this audit.

### Finding F-02 — Project owner CRUD is not an invite/member-management system

**Severity:** HIGH against the owner's stated product requirement; not evidence of an existing cross-user data leak.  
**Observed behavior:** Current project ownership binds each project to one issuer + subject pair. The reviewed code provides owner-scoped listing, read, update and delete checks. It does not provide a verified project-member invitation, grant, role, or revocation workflow.  
**Interpretation:** Owner-only isolation exists; owner-controlled sharing with selected people is not yet implemented. Do not describe invitations or revocation as available.  
**Required closure:** Add an explicit access-grant model keyed by project ID and grantee issuer + subject. Only the project owner may grant or revoke. New users receive no access by default. Revocation must take effect on the next authorization check and invalidate relevant cached selections/session capabilities. The owner must remain the only administrator; collaborators must not be able to grant access onward unless a separately reviewed role is introduced. Require tests for forged grantee identity, cross-issuer collision, owner self-revocation, revoked-user stale sessions, and concurrent grant/revoke operations.

### Finding F-03 — Global APAA owner/admin bootstrap is not established

**Severity:** MEDIUM.  
**Observed behavior:** The current Principal/project model establishes authenticated identity and per-project creator ownership. The reviewed code does not establish a separately provisioned APAA-wide owner/admin authority, recovery path, or account-level invitation console.  
**Interpretation:** Project creator ownership must not be conflated with an independently bootstrapped product owner/admin.  
**Required closure:** Define a one-time owner bootstrap anchored to an independently configured issuer + subject pair, a recovery/rekey procedure, and an auditable owner-controlled grant/revoke policy. Never accept an owner identifier from browser input, task text or model output.

### Finding F-04 — Live OIDC and two-user browser verification remain unperformed

**Severity:** HIGH release gate.  
**Observed behavior:** Automated tests validate claim parsing and authorization primitives. The existing P06 live-verification document explicitly requires a configured OIDC client, HTTPS callback URL, private runtime secrets and two separately authenticated browser identities. Those prerequisites and live results are not present in the inspected evidence.  
**Required closure:** Complete the P06-01 through P06-09 live matrix in a disposable deployment. Do not put secrets, tokens or raw identity claims into repository evidence.

### Finding F-05 — Project mutation UI is narrower than the backend contract

**Severity:** LOW / product completeness.  
**Observed behavior:** The UI exposes project creation/review/confirmation and viewing. Owner-guarded update/delete methods are available in the registry API, but the inspected UI does not expose those controls.  
**Required closure:** Implement edit/delete UI only after the owner access model is approved; require separate action-specific review/approval and audit events for each mutation.

## 5. Required owner-first access invariants

The following rules remain mandatory for all future APAA clients and adapters:

1. The APAA owner is provisioned explicitly and is the only default administrator.
2. No public or anonymous access is enabled by default.
3. Every other person starts with zero access.
4. The owner explicitly grants access to a validated identity (issuer + subject); an email address or display name alone is not an identity proof.
5. The owner can revoke any grant; revocation is enforced server-side, not only by hiding a UI element.
6. Collaborators cannot elevate themselves, change the owner, invite others, or bypass the approval gate.
7. All project and resource access checks use the complete issuer + subject identity.
8. A stale browser session, task, approval receipt or cached project ID never preserves access after revocation or identity switch.
9. Owner/admin actions are audited without logging credentials, bearer tokens or sensitive task payloads.
10. Payment, purchase, checkout, trading and money movement remain denied; paid providers remain disabled; Auto-Run remains OFF.

## 6. Prioritized next implementation sequence

| Priority | Work item | Acceptance evidence |
|---|---|---|
| P35-A | Define APAA owner bootstrap and recovery threat model | Reviewed design, no client-controlled owner identity |
| P35-B | Add persistent project access grants keyed by project + issuer + subject | Unit/integration tests for grant, deny, revoke, stale-session denial |
| P35-C | Add owner-only grant/revoke controller and audit events | Non-owner denial, forged-identity denial, durable audit |
| P35-D | Add owner access-management UI suitable for Android | Narrow viewport, accessible review, explicit confirmation |
| P35-E | Live two-user OIDC test | P06 matrix with redacted evidence |
| P35-F | Independent review | Reviewer attestation bound to exact code/evidence digest |

These are repository implementation and verification tasks. They do not authorize production rollout, real-host mutation, worker activation or a paid service.

## 7. Release and chapter locks

- P34 exact-head CI: **PASS (4/4 workflows)**.
- P35 owner/access audit: **RECORDED; implementation gaps identified**.
- Live OIDC/two-user qualification: **BLOCKED**.
- Global APAA owner bootstrap: **NOT IMPLEMENTED / NOT VERIFIED**.
- Invitation/grant/revocation: **NOT IMPLEMENTED**.
- Physical Android device qualification: **PENDING**.
- S09 C01 real-host gates G1–G10: **OPEN/BLOCKED as listed in P31**.
- S09 C01: **OPEN / NOT COMPLETE**.
- PR #11: **Draft / Open / Unmerged**.
- Browser/worker: **DISABLED**.
- Auto-Run: **OFF**.
- Paid APIs/providers/services: **DISABLED**.
- Payment, purchase, checkout, trading and money movement: **PROHIBITED**.
- No deployment, merge, host/firewall mutation or C02 start is authorized.

**Next checkpoint:** `APAA-S09-C01-P35-OWNER-ACCESS-PERMISSION-AUDIT-RECORDED`


## 8. P42/P36 implementation reconciliation (2026-11-16)

This section supersedes the earlier implementation-status statements in F-02, the P35-A–P35-D sequence, and Section 7 where they describe grant/revoke or sharing UI as not implemented. Those statements are retained above as the historical finding at the earlier audited code head; they are not the current branch disposition.

**Current implementation inspected:** P42 owner-controlled read-only grant/revoke UI, core/project_access.py, core/persistent_projects.py, and the P36 Part 11 design record.

The current branch now implements the narrow owner-controlled workflow:
- The UI is gated on a server-validated authenticated Principal, an explicitly configured trusted OIDC issuer allowlist, and an owner-owned project.
- Directory enrollment is private by default and requires explicit discoverability consent.
- The browser selects an opaque server-issued directory ID. The server resolves it to a Principal and rechecks owner authority; issuer/subject claims are never accepted from browser input.
- Grant and revoke each require explicit owner confirmation. Grants expose project metadata read only.
- Active grants are listed for the owner. ACL-aware project list/detail reads recheck authorization; durable grant/revoke events are recorded.
- Project mutation/deletion, task dispatch/execution, files/resources, memory/knowledge, conversations/preferences and checkpoints are not granted. No public invitation endpoint, email identity matching or generic role grant exists.

**Current repository disposition:** owner-controlled read-only grant/revoke UI and backend primitive are IMPLEMENTED in the PR branch. This closes the earlier repository implementation gap F-02 for the narrow read-only scope only. It does not implement a general invitation system, broad collaborator roles, account-level administration, or a separately provisioned APAA-wide owner bootstrap. F-03 therefore remains OPEN: global owner bootstrap/recovery is not established by per-project ownership.

**Required external acceptance remains BLOCKED:** live OIDC with two distinct real accounts, physical Android session/revocation testing, out-of-band identity validation, independent review and exact-head qualification. Unit tests and Chromium viewport emulation do not replace these checks. Keep the feature disabled unless trusted OIDC configuration is explicitly supplied by the owner.

**Updated P35 status**
- P35-A global owner bootstrap/recovery threat model: OPEN.
- P35-B narrow persistent read grant/revoke: IMPLEMENTED; exact-head CI evidence tracked in P31.
- P35-C owner-only controller and durable audit: IMPLEMENTED; live identity/host acceptance BLOCKED.
- P35-D owner-confirmed Android-responsive UI: IMPLEMENTED in repository; physical Android qualification BLOCKED.
- P35-E live two-user OIDC: BLOCKED.
- P35-F independent review: BLOCKED.

No deployment, merge, Auto-Run, worker activation, paid service, host/firewall mutation, payment or C02 start is authorized.


## 9. P35-A global owner bootstrap/recovery design recorded

The separate design is recorded in [P35-A Global Owner Bootstrap and Recovery Design](APAA_S09_C01_P35A_GLOBAL_OWNER_BOOTSTRAP_AND_RECOVERY_DESIGN.md). It defines an out-of-band, server-configured exact OIDC issuer + subject owner; rejects first-login-wins, browser/task-supplied identity, email/display-name matching and project-owner-to-global-admin promotion; and specifies fail-closed startup, immutable runtime checks, operator-controlled recovery/re-key, audit constraints, threats and mandatory test/release gates.

This closes the **design/documentation** portion of P35-A only. It does not implement a loader, global-owner guard, recovery command, protected configuration, monotonic revision control or live identity verification. Those remain explicit future implementation and external qualification work. No owner identity or secret was requested, stored, or added to the repository.

Current P35-A: DESIGN RECORDED / IMPLEMENTATION NOT IMPLEMENTED / QUALIFICATION BLOCKED. P35-B/C/D: narrow read-only sharing implemented in repository; live qualification blocked. P35-E/F: blocked.
