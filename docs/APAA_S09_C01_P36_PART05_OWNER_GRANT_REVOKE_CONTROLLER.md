# APAA S09 C01 P36 Part 05 — Owner Grant/Revoke Controller

Status: IMPLEMENTED; exact-head CI verification pending.

## Delivered

- Added `OwnerProjectAccessController` as a narrow server-side facade over the durable `ProjectAccessControl` store.
- Every management method requires a trusted authenticated `Principal` and rechecks exact project ownership using both OIDC issuer and subject.
- Exposed only four operations: grant read, revoke read, list grants and list immutable grant/revoke events.
- The grantee identity is validated server-side and bound to the exact issuer + subject pair.
- Self-grant and self-revocation are rejected. Revoke is idempotent and does not create a false audit event when no active grant changes.
- Grant/revoke persistence and immutable event creation remain in the same SQLite transaction.
- Added controller tests for owner-only management, wrong issuer, unauthenticated actor, self-access, missing project, immediate revocation and absence of generic privilege-escalation methods.

## Explicitly not granted

A read grant does not authorize project mutation, action execution, file access, memory access, checkpoint access, secrets, invitations, browser automation, worker execution or payment. No Streamlit management controls or public API are enabled by this part. Existing app collaborator visibility remains disabled pending the Part 06 callsite audit.

## Verification

Implementation commits:
- Controller: `7c602e27907efadcd8ff014d79c3a887b6160e1b`
- Regression tests: `408dd785e1385f4d285b64fd206739889cc633e1`

The exact-head CI result must be checked after the complete P36 batch. No PASS is inferred from earlier commits.

## Release boundary

PR #11 remains Draft/Open/Unmerged. Auto-Run OFF. Browser and worker disabled. No merge, deployment, host mutation, firewall change, paid service or C02 start is authorized.
