# APAA-S09-C01-P31 — Final C01 Evidence Inventory and Closure Gate

**Status:** repository-side closure inventory complete; real-host qualification BLOCKED  
**Branch:** `feature/apaa-s09-c01-p16-oci-lifecycle`  
**PR:** #11 — Draft / Open / Unmerged  
**Rule:** this inventory is a checklist, not evidence. Empty, synthetic, CI-only, or unreviewed evidence never counts as PASS.

## 1. Current verified repository state

At the PR head recorded when this inventory was prepared, the following PR-triggered workflows completed successfully:

- APAA P23 Rootless Podman Executor Integration — PASS.
- Python Demo CI — PASS.
- Agent Foundation CI — PASS.
- APAA P20 Rootless Podman Runtime Qualification — PASS.

These checks establish repository test and disposable CI-runner behavior only. Re-check the exact head SHA and workflow runs before relying on them after any later commit.

Repository deliverables include the P16–P26 worker, attestation, proxy and trust foundations; P27 evidence schema and validator; detached manifest-signature verification; independent-review attestation verifier; P28 manifest builder; P29 privacy preflight; P30 strict JSON/privacy hardening; and the Android-first product architecture. Consult the corresponding source files and exact-head CI records rather than treating this summary as a substitute for them.

## 2. Mandatory external qualification gates

Every row must have a restricted evidence-record reference, exact tested code SHA, operator, UTC timestamp, result and independent reviewer. Do not place secrets or raw host identifiers in this repository.

| Gate | Required evidence | Current status |
|---|---|---|
| G1 — Owner approval and host | Explicit owner approval, disposable Linux host, isolation boundary, maintenance window, rollback/rebuild plan | BLOCKED — no approved host record |
| G2 — Runtime and image | Pinned runtime version, locally present immutable image digest, read-only preflight | BLOCKED — no owner-host evidence |
| G3 — Collector identity | Least-privilege identity, reviewed collector digest and effective privilege proof | BLOCKED — no real-host collector evidence |
| G4 — Trust and signer | Out-of-band root/key fingerprints, protected signer, rotation, revocation and recovery | BLOCKED — no independently provisioned signer evidence |
| G5 — Durable anti-rollback | Separately administered durable monotonic anchor; atomic concurrent updates; restart and backup/restore rollback rejection | BLOCKED — production anchor not qualified |
| G6 — Lifecycle and attestation | Actual CREATE/INSPECT/ATTEST/START/STOP/REMOVE; immutable identity binding; stale/replay/tamper/wrong-host negative tests | BLOCKED — CI lifecycle is not owner-host qualification |
| G7 — Egress enforcement | Effective worker namespace rules plus sink-side evidence for IPv4/IPv6, DNS TCP/UDP, UDP/443/QUIC, WebSocket, alternate interfaces, DNS rebinding/pinned-IP dial-time and firewall hook precedence | BLOCKED — complete real topology not proven |
| G8 — Failure and cleanup | Real daemon interruption, cancellation, timeout, signer/collector loss and bounded orphan cleanup | BLOCKED — no owner-host drill |
| G9 — Android primary-device assessment | Physical Android browser tests; permission behavior, identity/session transitions, logout/revocation propagation, lifecycle/background limits and explicit boundary between Android control plane and isolated worker | BLOCKED — CI Android viewport emulation exists; physical Android evidence absent. PC is an optional future client and is not a prerequisite for Android-only use or Android qualification. If the owner later elects to use/qualify PC, perform separate physical PC verification before making PC release claims |
| G10 — Independent review | Independent reviewer verifies evidence authenticity, host identity, key custody, anchor, sink observations, cleanup, owner grant/revoke controls, resource authorization boundaries, two-user OIDC results and exact code/evidence digests | BLOCKED — no signed independent approval |

## 3. Evidence acceptance rules

1. Use the P27 evidence pack's nine required JSON artifacts and manifest builder.
2. Collect evidence only on an owner-approved disposable host with a locally available digest-pinned image.
3. Keep private keys, tokens, credentials, environment dumps and personal data out of the evidence bundle and repository.
4. Sign the exact raw manifest bytes with the approved evidence signer. Verify against a public-key fingerprint provisioned independently out-of-band.
5. Bind the independent review attestation to the exact manifest digest and verify it with a separately pinned reviewer key.
6. The owner must independently establish reviewer identity and independence; cryptographic validity alone does not do this. PC physical-device testing is conditional on the owner choosing to use or qualify the optional PC client; it must not block Android-only delivery.
7. Any missing prerequisite, missing artifact, skipped mandatory test, unexplained network observation, failed assertion or untrusted key is BLOCKED or FAIL, never PASS.
8. After any code change, rerun mandatory CI and repeat every affected host gate against the new exact code SHA.

## 4. Android-first boundary

Android remains the primary owner interface and control plane. PC is an optional future client; PC ownership, setup and physical-device testing are not required for Android-only use. Android/Termux is not accepted as a hostile-code isolation boundary and must not be used to claim Linux worker qualification. The current architecture decision does not prove a native Android app, PWA, physical-device test, or isolated worker is already operational.

## 5. Release and scope locks

Until every mandatory gate is PASS and independently approved:

- S09-C01 remains **OPEN / NOT COMPLETE**.
- Do not start C02.
- Keep PR #11 Draft / Open / Unmerged.
- Keep Auto-Run OFF and browser/worker execution disabled.
- Do not deploy, mutate a host/firewall, provision a remote worker, or activate a production runtime.
- Do not add paid services, API keys, paid hosting or automatic paid fallbacks.
- Payment, purchase, checkout, trading and money movement remain denied.

## 6. Exact closure condition

C01 may be marked COMPLETE only when all G1–G10 are PASS, the restricted evidence package is integrity- and signature-verified, the independent reviewer approves the exact code SHA and manifest digest, and the owner explicitly accepts the qualification record. Until then the truthful status is **repository implementation and CI: PASS; real-host qualification: BLOCKED; C01: NOT COMPLETE**.

## 7. Next executable action

The next action is not another code-only checkpoint: an owner-approved disposable Linux host, local digest-pinned image, out-of-band trust provisioning, protected signer and durable independent anchor must be made available. Then execute the P27 runbook under a human operator and obtain independent review. If those prerequisites are unavailable, preserve the BLOCKED status and do not simulate the missing evidence.


## 8. P36 owner-controlled access acceptance

P36 adds a narrow owner-only read-grant/revoke controller and immutable grant/revoke event history. This is not permission to enable collaborator access in the application. Before any collaborator feature is activated, the owner and independent reviewer must verify:

- The owner identity is the exact OIDC issuer + subject pair; no subject-only or client-supplied identity is accepted.
- Grant/revoke operations are owner-only, read-only, append-only audited, and immediately enforced by all subsequent reads.
- Revocation is tested from an already-open second session and after process/store reconstruction.
- Project mutation/action, file/resource operations, memory, conversations, preferences and checkpoints remain denied to a read-only collaborator.
- Project checkpoint save and recovery must pass through `OwnerProjectCheckpointAccess`, which derives the tenant from the authenticated principal and verifies exact project ownership.
- Two distinct real OIDC accounts are used; synthetic principals and unit tests are not accepted as live OIDC evidence.
- The physical Android device is exercised for sign-in, sign-out, session switch, revocation, storage isolation and responsive behavior. PC physical verification is optional and only required before making PC-specific release claims.

Until those tests and the other mandatory gates are independently approved, the safe default remains owner-only application access; no collaborator UI/API is enabled.


### P36 implementation references

- Owner-only read grant/revoke controller: `core/project_access_controller.py`.
- Exact-owner checkpoint association and recovery: `core/project_checkpoint_access.py`.
- Resource authorization audit: `docs/APAA_S09_C01_P36_PART06_RESOURCE_AUTHORIZATION_AUDIT.md`.
- Two-user/session regression tests: `tests/test_project_access_session_regression.py`.
- Android and PC browser smoke suites: `tests/test_android_viewport_smoke.py`, `tests/test_pc_browser_smoke.py`.

Repository tests and CI remain separate from live OIDC and physical-device evidence. Recheck the exact latest PR head before marking any code-side P36 verification PASS.


## 9. P36 exact-head CI refresh (2026-11-16)

The P36 owner grant/revoke backend/controller and its repository regressions were included in PR head `ae23970b281aa94e7a7c0412af889623e9e8b62b`. All six PR check-runs on that exact head completed successfully: Agent Foundation CI, Python Demo CI, P20 disposable rootless Podman lifecycle, P23 disposable rootless Podman executor integration, Android/PC Chromium viewport verification and disposable Linux egress namespace qualification.

Workflow runs: [Agent Foundation #1026](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43828928803), [Python Demo #1101](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43828928850), [P20 #155](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43828928935), [P23 #137](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43828928800).

This updates repository-side CI status only. It does not change any G1–G10 external qualification status. In particular, live OIDC, physical Android, real-host signer/anti-rollback/egress evidence and independent review remain BLOCKED.

The owner grant/revoke controller is a backend primitive, not an enabled collaborator feature. End-user access UI remains disabled until a trusted identity-directory/invitation-resolution design returns server-verified Principals and every project/resource read path enforces grant and immediate revocation. Do not accept user-entered issuer/subject identifiers or expose a public invitation endpoint. The owner-only default remains in force.

**Current truthful status:** repository implementation and exact-head CI: PASS; end-user collaborator workflow: BLOCKED; live/physical/real-host qualification: BLOCKED; S09-C01: OPEN / NOT COMPLETE; C02: NOT STARTED.


## 10. P42 owner-controlled read-only grant/revoke UI and P31 evidence refresh (2026-11-16)

**P42 implementation disposition:** IMPLEMENTED in the PR work branch. The owner-facing controls are present in `app.py` and are gated on a validated authenticated Principal plus an explicitly configured trusted OIDC issuer allowlist and an owner-owned project.

### P42 controls inspected

- Directory enrollment is sourced only from the server-validated Streamlit OIDC Principal. An identity is private by default and must explicitly opt in to directory discoverability.
- The owner selects an opaque server-issued directory ID; the browser does not submit issuer/subject values as identity claims.
- The server resolves the opaque ID to an authenticated Principal and rechecks owner authority before grant.
- Grant requires a separate confirmation checkbox and form submission; it grants project metadata read access only.
- Active grants are listed for the owner. Revocation requires a separate confirmation and is persisted through the owner-only controller.
- The read boundary uses ACL-aware project list/detail calls; the current grant does not authorize project edits/deletion, task approvals/dispatch/execution, files/resources, memory/knowledge, conversation history, preferences or checkpoints.
- The directory-discoverability preference is separate from project permission. Opting out prevents new selection but does not silently revoke an existing grant; the owner can still identify an active grant for revocation.
- No public invitation endpoint, email-based identity matching, client-supplied issuer/subject, generic role grant or collaborator privilege escalation is introduced.

### Exact PR-head CI evidence

The P42 state was checked on exact PR head `3d8c166628b5c7040d706d963ca69d12283aef7f`. All four required workflow runs completed successfully on that exact SHA:

| Workflow | Run | Result |
|---|---:|---|
| Agent Foundation CI | [#1054](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43834326479) | PASS |
| Python Demo CI | [#1129](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43834326471) | PASS |
| P20 disposable rootless Podman lifecycle | [#183](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43834326304) | PASS |
| P23 disposable Podman executor integration | [#165](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43834326459) | PASS |

Agent Foundation CI additionally completed its Android/desktop Chromium viewport-emulation job and disposable Linux egress namespace job successfully. P20 completed its disposable rootless Podman CREATE/INSPECT/START/STOP/REMOVE and no-leftover checks. P23 completed the disposable Podman executor/attestation-gate integration and no-worker-leftover checks.

**Evidence scope:** These are exact-PR-head repository and disposable CI-runner results. Chromium viewport emulation is not a physical Android test. Disposable Linux namespace and Podman checks are not production-host qualification. These results do not establish live OIDC with two real identities, actual Android device behavior, protected production signer/key custody, an independently administered durable anti-rollback anchor, production worker/proxy sink-side enforcement, production Linux host qualification, or independent human approval.

### P31 final disposition

- Repository-side P31 evidence inventory: **UPDATED / RECORDED**.
- P42 owner-controlled read-only grant/revoke UI: **IMPLEMENTED**.
- P42 exact-head CI on the recorded SHA above: **PASS (4/4 workflows; all reported jobs successful)**.
- PR #11: **Draft / Open / Unmerged** at the time of this evidence check.
- G1–G10 external qualification gates: **BLOCKED / NOT EVIDENCED**; no gate is promoted to PASS by CI-only evidence.
- Live OIDC, physical Android and production Linux host qualification: **NOT COMPLETED**.
- S09-C01: **OPEN / NOT COMPLETE**.
- S09-C02: **NOT STARTED**.

This section closes the repository-side P31 evidence refresh only. It does not close S09-C01 or authorize collaborator access in any deployment, merge, release, worker activation, paid API, payment, Auto-Run, or production action. Recheck CI on any subsequent commit SHA before treating this evidence as current.

## 11. P32 Android-first reconciliation and latest exact-head CI (2026-11-16)

This section supersedes older CI-head pointers in this inventory. It records the P32 Android-first qualification documentation and its exact-head verification without upgrading any external qualification gate.

### P32 documentation disposition

- P32 Android-first bulk qualification document: updated and reconciled with P42 owner-controlled read-only grant/revoke implementation and the outstanding physical-device/live-auth boundaries.
- Android viewport automation: repository CI coverage only; Chromium/Playwright emulation, not a physical Android handset.
- Physical Android: BLOCKED pending owner-operated handset evidence for browser login/logout, session changes, storage/lifecycle, and two-real-account grant/revoke.
- Native Android APK/PWA: not implemented/qualified.
- PC physical-device testing: optional and not a prerequisite for Android-first qualification.
- Real-host Linux worker qualification: separate mandatory C01 blocker; Android/Termux is not a hostile-code isolation boundary.

### Latest exact-head evidence

P32 evidence reconciliation commit `7af3f6de5d435f6b3a489dabf3a29705a27ef712` completed all four required PR-triggered workflows successfully, with every returned job successful:

| Workflow | Run | Result |
|---|---:|---|
| Agent Foundation CI | [#43835713964](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43835713964) | PASS |
| Python Demo CI | [#43835713847](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43835713847) | PASS |
| P20 Rootless Podman Runtime Qualification | [#43835713859](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43835713859) | PASS |
| P23 Rootless Podman Executor Integration | [#43835713968](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43835713968) | PASS |

Agent Foundation's foundation test, Android/PC Chromium browser verification and disposable Linux egress namespace jobs passed. Python Demo's test job passed. P20's disposable rootless Podman lifecycle job passed. P23's disposable Podman executor/attestation integration job passed.

**Evidence boundary:** These results establish tests on GitHub-hosted disposable CI infrastructure for the exact commit above. They do not establish a physical Android device, live OIDC with two real identities, production Linux host, protected production signer/key custody, separately administered durable anti-rollback, production sink-side egress enforcement, or independent reviewer approval.

### Current mandatory gate matrix (reconfirmed)

| Gate | Status | What is still required |
|---|---|---|
| G1 — Owner approval and host | BLOCKED | Explicit owner-approved disposable Linux host, maintenance window, isolation boundary and rollback plan |
| G2 — Runtime and image | BLOCKED | Locally available immutable digest-pinned image and read-only owner-host preflight |
| G3 — Collector identity | BLOCKED | Reviewed least-privilege collector and effective privilege evidence |
| G4 — Trust and signer | BLOCKED | Out-of-band trust fingerprints and protected signer with rotation/revocation/recovery evidence |
| G5 — Durable anti-rollback | BLOCKED | Separately administered durable monotonic anchor, atomic concurrency and restore/rollback rejection |
| G6 — Lifecycle and attestation | BLOCKED | Real owner-host lifecycle, immutable binding and negative/replay/tamper tests |
| G7 — Egress enforcement | BLOCKED | Complete real topology evidence including IPv4/IPv6, DNS TCP/UDP, UDP/443/QUIC, WebSocket, alternate interfaces, dial-time pinned-IP and sink-side observations |
| G8 — Failure and cleanup | BLOCKED | Real daemon interruption, timeout/cancel, signer/collector loss and bounded orphan cleanup drill |
| G9 — Android primary-device assessment | BLOCKED | Physical Android browser/session/storage/lifecycle and two-real-account grant/revoke evidence |
| G10 — Independent review | BLOCKED | Independent reviewer verifies exact code SHA, host, trust, anchor, sink observations, cleanup and two-user OIDC evidence |

No G1–G10 status is promoted by the P32 CI results. No evidence is fabricated, no secrets or raw host identifiers are added to the repository.

### Repository and release disposition

- P31 evidence inventory: **RECONCILED through P32 exact-head CI evidence**.
- P32 Android-first documentation: **UPDATED; CI PASS on the exact recorded commit**.
- P42 owner-controlled read-only grant/revoke UI: **IMPLEMENTED in repository; live OIDC/device qualification pending**.
- Repository-side CI: **PASS on recorded exact heads only; re-run required after this new documentation commit**.
- Real-host/physical/live-identity qualification: **BLOCKED**.
- S09-C01: **OPEN / NOT COMPLETE**.
- S09-C02: **NOT STARTED**.
- PR #11: **Draft / Open / Unmerged**.
- Auto-Run OFF; browser/worker execution disabled; no paid API/payment; no deployment, merge, host/firewall mutation or production activation.

**Closure rule unchanged:** C01 cannot be declared complete until every mandatory G1–G10 gate has genuine evidence, signature/integrity checks, independent review and explicit owner acceptance against the exact final code SHA. This document update closes the repository-side evidence reconciliation task only.

## 12. G1–G10 operator execution checklist prepared (2026-11-16)

Added `docs/APAA_S09_C01_P27_G1_G10_OPERATOR_EXECUTION_AND_EVIDENCE_ACCEPTANCE_CHECKLIST.md` as the ordered operator-facing companion to the P27 evidence pack.

The checklist now defines, for each G1–G10:
- prerequisites and explicit stop conditions;
- human operator actions;
- objective PASS acceptance criteria;
- BLOCKED/FAIL conditions;
- required evidence artifacts and privacy boundaries;
- dependency order and fail-closed behavior;
- manifest, detached signature, independent reviewer and owner-acceptance sequence.

It distinguishes physical Android/two-real-account OIDC qualification from Chromium emulation, and separates disposable CI results from owner-host evidence. It does not provision infrastructure, create identities, mutate firewall policy, launch workers or authorize deployment.

**Disposition:** documentation/checklist prepared; no G1–G10 external test has been performed by this change. G1–G10 remain BLOCKED. C01 remains OPEN / NOT COMPLETE; C02 NOT STARTED. PR #11 remains Draft/Open/Unmerged; Auto-Run OFF; browser/worker disabled; no paid API/payment, deployment, merge, host/firewall mutation or production activation. The new documentation commit requires exact-head CI verification before its repository-side status is current.


## 13. P27 evidence-tooling audit and latest exact-head CI (2026-11-16)

**Audited code head before this P31/P35 documentation reconciliation:** ad3024f34c3be101643f6082ef29e5226cf459a0.

### 13.1 P27 tooling review

Reviewed:
- scripts/build_apaa_p27_manifest.py
- scripts/check_apaa_p27_evidence_privacy.py
- scripts/validate_apaa_p27_evidence.py
- scripts/verify_apaa_p27_review.py
- tests/test_apaa_p27_manifest_builder.py
- tests/test_apaa_p27_evidence_privacy.py
- tests/test_apaa_p27_evidence.py
- tests/test_apaa_p27_review.py

Repository-side controls present:
- Manifest builder requires the exact nine-artifact inventory, bounded regular non-symlink JSON files, required metadata, UTC timestamps and an immutable image digest; it refuses to overwrite an existing manifest and reports integrity/authenticity/qualification as separate states.
- Privacy preflight checks the exact pack inventory, rejects duplicate JSON keys and non-standard JSON constants, bounds file size, detects common secret patterns and explicitly states that pattern scanning is not a privacy guarantee.
- Evidence validator rejects unknown/missing manifest fields, duplicate manifest keys, unsafe/non-canonical paths, symlinks/non-regular files, inventory mismatch, oversized files and digest mismatch. Detached Ed25519 verification requires an independently supplied expected public-key fingerprint and reports host qualification as NOT_ASSESSED.
- Independent-review verifier requires a separately pinned reviewer key, binds the signed attestation to the exact manifest digest, rejects malformed/duplicate JSON, invalid disposition/findings and non-UTC/future timestamps. Its output explicitly leaves reviewer identity and independence to out-of-band owner verification and does not grant qualification approval.
- Targeted tests cover manifest inventory/metadata, symlink rejection, tamper/path traversal, signature/key mismatch, duplicate keys, non-standard JSON constants, excessive nesting, review digest binding, reviewer-key pinning and unresolved PASS findings.

**Audit limitation:** this was a source/test review, not a live signing ceremony, protected-key custody test, real evidence-pack qualification, or independent reviewer exercise. A clean pattern scan is not proof of absence of sensitive data. Evidence observations still require human review and trusted restricted storage.

### 13.2 Latest exact-head CI reconciliation

Commit ad3024f34c3be101643f6082ef29e5226cf459a0 has all four PR-triggered workflows completed successfully:
- Agent Foundation CI — PASS: https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43837466004
- Python Demo CI — PASS: https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43837465991
- P20 Rootless Podman Runtime Qualification — PASS: https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43837466249
- P23 Rootless Podman Executor Integration — PASS: https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43837466126

All jobs in the Agent Foundation run completed successfully, including tests, disposable Linux egress namespace qualification and Android/PC Chromium browser emulation. These remain disposable CI/emulation results, not physical Android or owner-operated production-host evidence.

### 13.3 P35/P42 status reconciliation

P35's earlier F-02 and P35-B–D status reflected a prior code head. P42 subsequently implemented the narrow owner-confirmed read-only grant/revoke workflow. See the P35 Section 8 reconciliation. The general APAA-wide owner bootstrap/recovery, live two-user OIDC, physical Android verification and independent review remain open/blocked.

### 13.4 Current disposition and locks

- Repository code review and exact-head CI for ad3024f34c3be101643f6082ef29e5226cf459a0: PASS for the checks listed above.
- P27 evidence tooling source/test audit: RECORDED; no authentic host evidence generated.
- P35 narrow read-only sharing implementation: IMPLEMENTED; live qualification BLOCKED.
- G1–G10: BLOCKED pending authentic external evidence and independent review.
- S09-C01: OPEN / NOT COMPLETE; S09-C02: NOT STARTED.
- PR #11: Draft/Open/Unmerged.
- Auto-Run OFF; browser/worker disabled; no deployment, merge, paid API/payment, host/firewall mutation or production activation.
