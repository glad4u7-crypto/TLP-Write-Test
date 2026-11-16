# APAA S09 C01 P36 Part 05 — Owner Grant/Revoke Controller

Status: BACKEND IMPLEMENTED; exact-head CI PASS; end-user access workflow and live qualification BLOCKED.

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


## Exact-head follow-up (2026-11-16)

The six check-runs on PR head `d56697513b3dc7e0d18c3c976977462ac59552f2` subsequently completed successfully, including foundation tests, Android/PC Chromium viewport smoke, disposable Linux egress namespace, P20 rootless Podman lifecycle, P23 real Podman executor integration and demo CI. This verifies the automated repository state at that exact head only.

The three remaining release activities are deliberately not marked complete:

1. **Owner access UI integration:** blocked pending a trusted identity-directory / invitation-resolution design. A free-form issuer/subject text field would let an owner mistype or target an unverified identity and is not an acceptable authorization boundary. The existing controller must only receive a server-verified Principal; no user-entered identity is trusted.
2. **Live OIDC two-identity grant/revoke:** requires an owner-controlled private HTTPS non-production instance, configured OIDC test tenant, and two owner-controlled test identities. No provider credentials or private deployment were supplied; no public unauthenticated deployment is permitted as a workaround.
3. **Physical Android verification:** requires the owner to operate Android Chrome against that private test instance and record redacted evidence using `docs/APAA_S09_C01_AUTHENTICATED_ANDROID_TEST_SETUP.md`. CI viewport emulation is not a substitute.

PC physical verification remains optional. Do not weaken authentication or expose a public invitation endpoint to make these tests appear complete.

**Current decision:** P36 backend primitives and automated tests are implemented; end-user owner grant/revoke workflow and live/physical qualification remain OPEN. S09-C01 remains OPEN / NOT COMPLETE; C02 is blocked.


## Latest exact-head verification (2026-11-16)

Exact PR head: `ae23970b281aa94e7a7c0412af889623e9e8b62b`.

All six required PR check-runs completed successfully on this exact head:

| Check | Result |
|---|---|
| Agent Foundation CI | PASS |
| Python Demo CI | PASS |
| P20 disposable rootless Podman lifecycle | PASS |
| P23 real Podman executor integration (disposable CI runtime) | PASS |
| Android and PC Chromium viewport verification | PASS |
| Disposable Linux egress namespace qualification | PASS |

The four workflow runs are [Agent Foundation CI #1026](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43828928803), [Python Demo CI #1101](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43828928850), [P20 #155](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43828928935), and [P23 #137](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43828928800).

These results verify repository tests, browser viewport emulation and disposable CI runtime scenarios only. They do not establish physical Android behavior, live OIDC identity, production resource authorization, owner-controlled trusted identity resolution, or owner-host worker qualification.

## Remaining work — exact disposition

The repository-side controller and regression tests are implemented and CI-verified. The remaining work is not safely executable from repository access alone:

1. **Owner-facing grant/revoke workflow — BLOCKED.** No trusted identity-directory or invitation-resolution adapter exists. Do not add raw issuer/subject fields, accept a typed email as proof of identity, or create a public invitation endpoint. Before UI work, define a verified directory lookup that returns a server-validated authenticated `Principal`, binds it to the exact OIDC issuer, supports expiry/one-time redemption and owner cancellation, and has abuse/rate-limit/audit tests. The UI must remain disabled until all resource read paths enforce the grant and revocation immediately.
2. **Live two-identity OIDC test — BLOCKED.** Requires a private owner-controlled HTTPS test deployment, configured OIDC tenant, persistent private database storage and two owner-controlled test identities.
3. **Physical Android verification — BLOCKED.** Requires the owner to run the documented test procedure on the actual Android phone against that private test deployment and provide redacted results. Automated viewport emulation is not physical-device evidence.
4. **Real-host worker qualification — BLOCKED.** The P31 G1–G10 evidence gates remain mandatory; CI does not substitute for owner-host evidence, out-of-band signer trust, durable anti-rollback, sink-side network observations or independent review.

PC physical verification remains optional. PR #11 stays Draft/Open/Unmerged; Auto-Run OFF; browser/worker disabled; no paid services, host mutation, firewall changes, merge, deployment or C02 start.


## Trusted identity directory preparation (2026-11-16)

Added `docs/APAA_S09_C01_TRUSTED_IDENTITY_DIRECTORY_DESIGN.md` as an implementation-ready, provider-neutral contract. It recommends a closed directory of identities that have already authenticated through an explicitly allowlisted OIDC issuer. Owner selection uses opaque server-resolved directory IDs; email and user-entered issuer/subject values are never authorization keys. It defines adapter boundaries, issuer rules, persistence/audit requirements, negative tests and activation gates.

This is a documentation/design deliverable only. No directory database, provider adapter, invitation endpoint or collaborator UI was added or enabled. Owner-only behavior remains unchanged pending implementation and owner approval of the directory model.
