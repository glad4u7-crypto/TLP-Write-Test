# APAA-S09-C01-P59 — CI Reconciliation and Remaining Test Inventory

**Checkpoint:** `APAA-S09-C01-P59-CI-RECONCILIATION-AND-REMAINING-TEST-INVENTORY`  
**Status:** COMPLETE for the P59 repository scope — P58 exact-commit CI evidence and the P60–P63 qualification inventory are reconciled. Current remediation-branch CI is tracked separately; external qualification gates remain BLOCKED.  
**Branch:** `feature/apaa-s09-c01-p16-oci-lifecycle`  
**PR:** #11 — Draft / Open / Unmerged.  
**Safety:** no merge, deployment, host mutation, paid service, Auto-Run, browser/worker activation, or C02 start.

## 1. Exact-head CI evidence

The repository README and P32 qualification record identify the last recorded exact PR head as:

`6f8cc1e32e6464983dc9468487be2ed51c4f4791`

The four required PR-triggered workflows were fetched for that exact SHA and all completed successfully:

| Workflow | Run | Result |
|---|---:|---|
| Agent Foundation CI | [#1022](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43828000688) | PASS |
| Python Demo CI | [#1097](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43828000755) | PASS |
| APAA P20 Rootless Podman Runtime Qualification | [#151](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43828000804) | PASS |
| APAA P23 Rootless Podman Executor Integration | [#133](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43828000800) | PASS |

Agent Foundation's recorded jobs include dependency audit/compile, disposable Linux egress namespace qualification, and Android/desktop Chromium browser smoke tests. P20/P23 are disposable CI qualification, not owner-host qualification.

**Important:** this is the last exact PR-head SHA recorded in the checked-in README/P32 evidence. Any subsequent commit must receive a fresh exact-head workflow check before P59 can claim current-head CI PASS.

## 2. Separate failing commit requiring ancestry reconciliation

A separate commit was inspected:

`c02dcfe549117a74554df4316e1904c35e5026fc` — `test(APAA): cover private owner-only deployment gate`.

Its associated workflow runs reported:
- Python Demo CI: FAIL — 10 failed, 1338 passed, 9 skipped.
- Agent Foundation CI: FAIL — the same 10 test failures.
- P20 Rootless Podman Runtime Qualification: PASS.
- P23 Rootless Podman Executor Integration: PASS.

The failing tests include authenticated app fail-closed cases, approval-authority/session cleanup and global-owner session state. The logs show missing `global_owner_generation` / `approval_authority` session keys after the app stopped before those capabilities were initialized.

The inspected commit's diff adds an owner-only deployment wiring test; the available evidence does **not** establish that this SHA is the current PR #11 head or that it is an ancestor of the last recorded passing head. Therefore:
- do not describe this failure as a failure on SHA `6f8cc1e...`;
- do not ignore it if `c02dcfe...` is later proposed as a release candidate;
- reconcile its branch/ancestry and rerun CI on the exact candidate SHA before accepting it.


## 2A. P59 remediation commit — CI pending

After inspecting the current PR-branch test fixture, the authenticated AppTest helper was found to accept `configure_owner` but discard it. This meant positive authenticated integration tests could enter the new owner-only fail-closed gate without provisioning the matching server-side owner identity.

The fixture now provisions the exact synthetic OIDC issuer + subject as the server-side owner by default; tests explicitly exercising missing/invalid owner configuration continue to opt out. This is test-fixture-only and does not weaken the runtime owner gate.

- Remediation commit: [57e44ad26c6e91bd713c742769534f4b4157c8fc](https://github.com/glad4u7-crypto/TLP-Write-Test/commit/57e44ad26c6e91bd713c742769534f4b4157c8fc).
- Historical status at the time of the original P59 inspection: no PR-triggered workflow run or commit status had yet been returned for this intermediate commit. This pending status was superseded by the later remediation-branch commits and exact-head CI evidence recorded below and in `docs/APAA_S09_C01_ACTION_AUDIT_REMEDIATION_01.md`.

## 3. P58 verification boundary

P58's protected-key/remote-anchor implementation must be reviewed against the exact source commit(s) and their PR ancestry. The four passing workflows above establish aggregate repository/CI behavior at the recorded PR head; they do not by themselves prove that a particular P58 commit was tested unless its ancestry is confirmed.

P58 is not externally qualified by these runs. No real protected HSM/TPM signer, separately administered production anchor, owner-host rollback drill, or independent review is implied.

## 4. Remaining test inventory

### P60 — Signing key rotation, revocation and recovery
- Generate and validate key identifiers, algorithms, minimum strength and public-key fingerprints.
- Rotate active key while preserving verification of permitted historical evidence.
- Revoke compromised/retired key and prove all new signing attempts are denied.
- Reject unknown, revoked, expired, wrong-purpose and wrong-tenant keys.
- Test interrupted rotation, restart recovery, duplicate rotation and concurrent rotation.
- Prove private key material never appears in logs, manifests, CI artifacts or application session state.
- Test protected signer custody and recovery only with an owner-approved isolated environment; CI mocks are not HSM/TPM evidence.

### P61 — Anchor durability, rollback and backup/restore
- Atomic compare-and-advance (CAS): exactly one concurrent writer wins for a given expected revision.
- Reject stale revision, lower revision, same-revision mutation and conflicting digest.
- Verify durable commit across process restart and service restart.
- Inject interruption around write, flush/fsync, acknowledgement and restart boundaries.
- Restore old database/filesystem snapshots and backups; prove monotonic state cannot roll back.
- Test backup integrity, restore authorization, retention and recovery without exposing anchor secrets.
- Confirm the anchor is independently administered and not restorable by the same principal who can rewrite the evidence being anchored.

### P62 — Concurrent recovery, crash injection and audit tampering
- Concurrent owner recovery and key rotation; verify single-winner semantics and no split-brain.
- Crash at every recovery transition; restart must resume safely or fail closed.
- Replay old recovery challenges, receipts and signed manifests; reject all stale/replayed inputs.
- Mutate, truncate, reorder, delete and replace audit records; detect tampering and fail closed.
- Verify audit sequence/hash continuity and externally anchored checkpoints.
- Verify recovery is idempotent and never silently re-enables a revoked key or stale owner session.
- Exercise cancellation, timeout, partial write, disk-full and unavailable-anchor cases.

### P63 — Evidence review and C01 decision
- Bind every artifact to exact source SHA, test command, environment, UTC timestamp and operator.
- Verify raw manifest digest and signature using an independently provisioned public-key fingerprint.
- Verify independent-review attestation against the exact manifest digest and reviewer key.
- Confirm evidence completeness, redaction, provenance, test coverage and negative-test outcomes.
- Mark each external gate PASS/BLOCKED/FAIL with reviewer rationale; no inferred PASS.
- Obtain independent reviewer approval and explicit owner acceptance.
- C01 remains OPEN unless every mandatory P31 G1–G10 gate is independently PASS.

## 5. Mandatory external gates still not satisfied by CI

The P31 closure matrix remains authoritative. In particular, CI does not replace:
- owner-approved disposable Linux host and immutable image evidence;
- protected signer and out-of-band trust provisioning;
- independently administered durable anti-rollback anchor;
- actual worker lifecycle and sink-side IPv4/IPv6/DNS/QUIC/WebSocket egress enforcement;
- crash/cleanup drills on the owner-approved host;
- physical Android Chrome assessment and live OIDC/two-account grant/revoke tests;
- independent security review and owner acceptance.

Android remains the primary device. Physical PC testing is optional and is not a prerequisite for Android-only qualification.

## 6. P59 exit criteria

P59 can close only when:
1. P58 source commits and their ancestry to the exact candidate PR head are confirmed.
2. All required CI workflows are green on the exact candidate SHA.
3. Any separate failing candidate commit (including `c02dcfe...`, if it is in the candidate ancestry) is fixed or explicitly excluded with verified ancestry evidence.
4. The P60–P63 test inventory is frozen and traceable to evidence artifacts.
5. No external qualification is misrepresented as CI PASS.

Current disposition: **P59 repository scope COMPLETE** — P58 exact-commit CI is verified, the P60–P63 inventory is consolidated, and remediation source/test head `69d05e4d0ed3fef3c4c46ab4c17dbf09e82d2aa7` passed all five applicable workflows. Real-host and other external qualification remain BLOCKED; C01 OPEN; C02 NOT STARTED.


## 7. Superseding action-audit remediation verification (2026-11-16)

The intermediate pending status in Section 2A is historical and is superseded by the later remediation branch. The action-audit fixes and strengthened workflow-policy tests were verified on code/test head `f81be85ef75b3d0b26ee3e3e80dacb921db16ad6`; the subsequent documentation-only commit `075715f49337cdb3af367663f32c367e1869417e` also completed all five applicable PR workflows successfully.

| Workflow | Run | Result |
|---|---:|---|
| Agent Foundation CI | [#1228](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43913944979) | PASS |
| Python Demo CI | [#1317](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43913945016) | PASS |
| APAA Security CI | [#25](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43913944772) | PASS |
| P23 Rootless Podman Executor Integration | [#339](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43913944791) | PASS |
| P20 Rootless Podman Runtime Qualification | [#357](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43913944784) | PASS |

The Agent Foundation and APAA Security pytest jobs each reported **1,352 passed, 9 skipped**. Skipped tests are reported separately and are not counted as passes. This verifies the repository software and disposable CI checks only; it does not close any external qualification gate.

**Current action-audit disposition:** software findings FIXED; current candidate exact-head CI PASS 5/5; PR #12 remains Draft / Open / Unmerged; external gates BLOCKED; C01 OPEN / NO-GO; C02 NOT STARTED.
