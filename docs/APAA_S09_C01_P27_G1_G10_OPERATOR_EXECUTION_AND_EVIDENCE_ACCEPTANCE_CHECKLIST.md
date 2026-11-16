# APAA S09 C01 P27 — G1–G10 Operator Execution and Evidence Acceptance Checklist

**Status:** operator checklist prepared; no real-host or physical-device qualification claimed  
**Branch:** `feature/apaa-s09-c01-p16-oci-lifecycle`  
**PR:** #11 — Draft / Open / Unmerged  
**Parent:** P27 real-host qualification evidence pack; P31 final evidence inventory; P32 Android-first qualification  
**Execution mode:** human-operated, owner-approved, evidence-first; no deployment, merge, Auto-Run, worker activation, or paid service

## 0. Purpose and non-negotiable rules

This checklist converts the P27 evidence specification into an ordered, auditable operator workflow. It does not provision a host, create accounts, configure trust, change firewall policy, launch a worker, or grant approval.

Use only an isolated disposable Linux host and controlled Android test device/accounts. The owner must explicitly approve the host, test window, operator, exact code SHA, test image digest and rollback/rebuild plan before host-mutating tests. If a prerequisite is missing, stop and record BLOCKED. Never replace missing real evidence with a mock, screenshot, CI result, synthetic identity, ephemeral test key or guessed value.

### 0.1 Safety invariants

- Keep PR #11 Draft/Open/Unmerged.
- Keep Auto-Run OFF; browser and worker execution disabled.
- No production host, production workload, production credentials or production network.
- No host firewall mutation unless a separately reviewed and explicitly approved change plan exists; this checklist does not authorize one.
- No arbitrary image pulls. Use a locally available, reviewed, immutable sha256 image digest.
- No private keys, tokens, passwords, environment dumps, personal data, raw OIDC subject/issuer values or raw host identifiers in repository artifacts/comments.
- No payment, checkout, purchases, trading, money movement, paid API, paid hosting or paid fallback.
- Android/Termux is not an isolation boundary for hostile code.
- CI PASS is repository/disposable-runner evidence, never physical Android or owner-host qualification.
- A skipped, missing, incomplete, unverifiable or unexplained observation is BLOCKED/FAIL, never PASS.

## 1. Run identity and evidence handling

Before any gate begins, the owner/operator creates a restricted evidence record outside this repository.

Record in the restricted record:
- unique run ID and UTC start/end times;
- exact APAA code commit SHA and branch;
- owner approval reference and maintenance window;
- operator identity and role;
- sanitized host alias and host OS/kernel/architecture;
- runtime name/version and local immutable image digest;
- collector/signer versions and public-key fingerprints only;
- proxy policy identifier and test topology description;
- per-gate status, artifact filenames and SHA-256 digests;
- skipped tests with reason, failures, deviations and stop decisions;
- independent reviewer identity reference and disposition.

Use the P27 manifest builder/validator and detached signature/reviewer verification process. Keep raw evidence in the owner's approved restricted store. Only sanitized status, artifact digest and non-sensitive references may be recorded in this repository.

## 2. Ordered gate execution

### G1 — Owner approval, disposable host and rollback

**Prerequisites**
- Owner has selected and explicitly approved a disposable Linux VM/host.
- Host has no production workloads, user data or production credentials.
- Isolation boundary, maintenance window, operator and rollback/rebuild procedure are documented.
- Network access and evidence storage are approved.

**Operator actions**
1. Record approval reference, host alias, OS/kernel and UTC test window.
2. Verify the host is disposable and separated from production systems.
3. Verify rollback means rebuild/discard, not an untested in-place rollback.
4. Record stop conditions and the human operator who can stop the test.

**Accept only if**
- Owner approval is explicit and traceable.
- Isolation and rollback are independently understandable.
- No production data/workload is in scope.

**BLOCKED/FAIL if**
- No approved host, unclear ownership, shared production host, missing rollback or unclear operator authority.

**Artifacts:** owner-approval reference, sanitized host-preflight record, isolation/rollback record.

### G2 — Runtime, local image and read-only preflight

**Prerequisites**
- G1 PASS.
- Runtime/version explicitly approved.
- Image already present locally and identified by immutable sha256 digest.

**Operator actions**
1. Run the P20 read-only runtime preflight using the owner-approved runtime and exact version pin.
2. Capture sanitized version, rootless, cgroup and security facts.
3. Confirm the image is local; do not pull or build from an unreviewed remote base during qualification.
4. Independently compare the actual image digest with the approved digest.

**Accept only if**
- Runtime exactly matches approved pin and rootless contract.
- Local image digest is immutable and exact.
- Preflight is read-only and successful.

**BLOCKED/FAIL if**
- Runtime absent/unpinned, rootless requirements unmet, image absent/mutable/mismatched, or preflight output is incomplete.

**Artifacts:** host-preflight.json; image digest reference in manifest.

### G3 — Collector identity and least privilege

**Prerequisites**
- G1 and G2 PASS.
- Reviewed collector build/package and expected digest exist.

**Operator actions**
1. Identify dedicated collector UID/GID and its effective groups/capabilities.
2. Compare actual permissions with the reviewed least-privilege policy.
3. Verify collector cannot read/export private signer material.
4. Record collector package/binary digest and effective privilege evidence.
5. Verify no ambient privileged service or unrelated account is used.

**Accept only if**
- Actual identity and effective privileges match the approved least-privilege specification.
- Collector cannot export private key material.
- Evidence is reproducible and sanitized.

**BLOCKED/FAIL if**
- Collector uses root/unreviewed privilege, signer secret is readable, digest differs, or effective privileges cannot be proven.

**Artifacts:** identity.json and reviewed collector digest.

### G4 — Trust root, signer and key lifecycle

**Prerequisites**
- G1–G3 PASS.
- Trust root and evidence signer provisioned out-of-band by authorized custodians.
- Protected signer mechanism and recovery contacts documented.

**Operator actions**
1. Verify public root and signer fingerprints through two independent out-of-band channels.
2. Verify trust bundle issuer, validity, sequence and signature.
3. Verify private key is non-exportable or protected under the approved custody design.
4. Test authorized signing request, unauthorized caller denial, rotation overlap, revocation and recovery in the isolated qualification environment.
5. Record only public fingerprints, key IDs and test outcomes.

**Accept only if**
- Fingerprints match independent pins.
- Only authorized collector identity can request signing.
- Private material is not exposed.
- Rotation, revocation and recovery behavior is demonstrated.

**BLOCKED/FAIL if**
- Trust provisioned from the same untrusted channel, key is exportable/unprotected contrary to policy, fingerprint mismatch, or lifecycle tests are missing.

**Artifacts:** trust.json and restricted key-custody record.

### G5 — Durable anti-rollback anchor

**Prerequisites**
- G1–G4 PASS.
- Anchor is separately administered from the worker/collector and has a documented persistence contract.

**Operator actions**
1. Record anchor backend identity and administrative separation.
2. Exercise atomic compare-and-swap with concurrent sequence updates.
3. Restart the control plane and verify sequence durability.
4. In the isolated environment, restore an older snapshot and verify rollback is rejected.
5. Test unavailable anchor, duplicate sequence, stale sequence and concurrent update failure modes.

**Accept only if**
- No rollback or duplicate acceptance occurs.
- Updates are atomic under concurrency.
- Restart/restore behavior is durable and independently observable.

**BLOCKED/FAIL if**
- Anchor is in-memory, administered by same worker trust domain without approved separation, restore permits rollback, or concurrency semantics are unproven.

**Artifacts:** anchor-recovery.json and restricted anchor administration evidence.

### G6 — Real OCI lifecycle and attestation binding

**Prerequisites**
- G1–G5 PASS.
- Reviewed APAA executor, local digest-pinned image and isolated proxy-only topology are available.
- Human operator is present for all lifecycle tests.

**Operator actions**
1. CREATE one stopped container with the approved immutable image digest and hardened launch configuration.
2. INSPECT and compare immutable container ID, image digest, launch-spec digest, network namespace, read-only rootfs, capabilities, no-new-privileges and seccomp.
3. Obtain a fresh, single-use, tenant-bound challenge and host/worker/container/network-bound attestation from the trusted collector.
4. Verify valid attestation allows exactly one START.
5. Verify stale, replayed, tampered, wrong-host, wrong-worker, wrong-container, wrong-network, wrong-launch-spec, unknown/revoked-key evidence blocks START.
6. STOP and REMOVE by immutable ID and prove no qualification container remains.
7. Record each lifecycle result and timestamps.

**Accept only if**
- Actual daemon behavior matches the approved lifecycle contract.
- Evidence is bound to exact immutable runtime objects and code/image digests.
- All negative tests deny start.
- Cleanup leaves no orphan.

**BLOCKED/FAIL if**
- Any binding mismatch is accepted, invalid attestation starts a worker, cleanup is incomplete, or only CI/mock lifecycle evidence exists.

**Artifacts:** lifecycle.json, negative-tests.json, sanitized daemon observations.

### G7 — Egress and sink-side enforcement

**Prerequisites**
- G1–G6 PASS.
- Approved proxy endpoint and expected network tuple documented.
- Isolated sink-side observer is available.

**Operator actions**
1. Capture effective worker namespace policy and its digest.
2. Verify only the approved proxy destination/protocol tuple is allowed.
3. Test direct IPv4 and IPv6 TCP.
4. Test DNS over UDP and TCP, UDP/443 and QUIC.
5. Test WebSocket, alternate interfaces/routes, unexpected gateways and firewall hook precedence.
6. Test DNS rebinding and dial-time pinned-IP behavior.
7. Correlate every probe with sink-side observations; a local client error alone is not proof of network denial.
8. Do not change host firewall rules under this checklist.

**Accept only if**
- All forbidden paths are denied at the effective enforcement point.
- Approved proxy path behaves as expected.
- Sink-side evidence independently confirms results.
- No unexplained packet, alternate route or bypass remains.

**BLOCKED/FAIL if**
- Any forbidden traffic reaches sink, IPv6/UDP path is untested, sink evidence absent, or firewall precedence/alternate interface is unknown.

**Artifacts:** egress.json, policy digest, restricted sink observations.

### G8 — Failure handling and bounded cleanup

**Prerequisites**
- G1–G7 PASS.
- Isolated disposable environment and explicit stop/cleanup procedure.

**Operator actions**
1. Exercise cancellation and timeout at each lifecycle boundary.
2. In the isolated environment, test daemon interruption, collector loss and signer loss.
3. Confirm fail-closed behavior and bounded STOP/REMOVE deadlines.
4. Inspect runtime inventory after every path.
5. Verify no orphaned container, process, namespace or temporary credential remains.

**Accept only if**
- Every failure path stops safely within documented bounds.
- No unapproved restart or retry bypass occurs.
- Cleanup is complete and evidenced.

**BLOCKED/FAIL if**
- Cleanup deadline exceeded, orphan remains, daemon loss leaves worker running, or failure behavior is not observable.

**Artifacts:** failure-cleanup.json and sanitized inventory.

### G9 — Physical Android primary-device assessment

**Prerequisites**
- Owner-approved secured test deployment or local secured test environment.
- Physical Android handset, supported browser and two controlled real OIDC accounts.
- No public unauthenticated exposure. Do not put credentials/tokens in repository evidence.

**Operator actions**
1. Record handset model/Android/browser versions in restricted evidence; use a sanitized device alias in reports.
2. Test login, logout, expired session and identity switch.
3. Verify user A cannot see user B's projects or stale cached data after session transition.
4. Test portrait/landscape, keyboard, viewport, scrolling, touch targets and browser storage behavior.
5. Test app background/resume, network loss/reconnect and browser process recreation.
6. With two real accounts, test directory opt-in separately from project grant; verify owner confirmation required.
7. Verify grant exposes only permitted project metadata; attempt prohibited edits, deletes, task execution, files/resources, memory, conversations, preferences and checkpoints.
8. Revoke grant; verify access denied on next read and from an already-open second session.
9. Verify logout/session change clears identity-bound state.
10. Capture sanitized results; do not expose raw identity claims, cookies or local storage.

**Accept only if**
- Physical device tests are actually performed.
- Two distinct real OIDC identities are independently established.
- Grant/revoke and all denied surfaces behave as specified.
- No stale session or cross-tenant data is visible.

**BLOCKED/FAIL if**
- Only emulator/viewport CI exists, no secured test environment/two accounts, any unauthorized data/action is accessible, or revocation does not promptly take effect.

**Artifacts:** restricted device test record, sanitized Android test summary and two-account OIDC evidence references.

**Boundary:** Native APK/PWA status must be reported separately. Browser testing does not prove native application support. PC physical testing is optional unless a PC release claim is made.

### G10 — Independent review and owner acceptance

**Prerequisites**
- G1–G9 evidence package complete.
- Exact final code SHA frozen for review.
- Manifest integrity and detached signature verified.
- Reviewer key independently pinned and reviewer identity/independence checked out-of-band.

**Reviewer actions**
1. Verify exact code SHA and manifest digest.
2. Verify every required artifact, timestamp, operator and gate result.
3. Reconcile host identity, trust root, signer custody, anchor administration, lifecycle, sink-side observations, cleanup and Android two-account evidence.
4. Confirm no secrets/personal data are exposed and evidence has not been altered.
5. Review all deviations, skipped tests and remediation.
6. Sign disposition bound to exact manifest digest and code SHA.

**Owner actions**
1. Independently establish reviewer identity and independence.
2. Review findings and exceptions.
3. Explicitly accept or reject the exact qualification record.
4. Keep deployment/merge/worker locks in place unless a separate, explicit future authorization is given.

**Accept only if**
- Reviewer is independent and authenticated out-of-band.
- Every mandatory gate is PASS with complete, authentic evidence.
- Signed review binds the exact manifest and code SHA.
- Owner explicitly accepts.

**BLOCKED/FAIL if**
- Any gate is BLOCKED/FAIL/SKIPPED, reviewer independence uncertain, signature/fingerprint invalid, or owner acceptance absent.

**Artifacts:** review.json, detached reviewer attestation/signature, owner acceptance reference.

## 3. Gate dependency and stop logic

The mandatory order is:

`G1 → G2 → G3 → G4 → G5 → G6 → G7 → G8`

G9 (physical Android) may be prepared in parallel only after a secured test environment and real OIDC accounts are available; it does not replace or waive G1–G8. G10 is last and reviews the complete exact-SHA evidence set.

- If G1 fails/blocks, do not start host qualification.
- If G2–G5 fail/block, do not create/start a worker.
- If G6 fails, do not proceed to worker network qualification.
- If G7 fails, worker remains disabled.
- If G8 fails, worker remains disabled and the environment must be cleaned/rebuilt.
- If G9 fails, Android-first product qualification remains blocked.
- If G10 is not independently PASS and owner-accepted, C01 remains open.

## 4. Evidence package validation and review sequence

1. Assemble the nine required P27 artifacts in the restricted evidence directory.
2. Ensure every file is sanitized and every required artifact is present.
3. Build the manifest with exact run metadata and SHA-256 digests.
4. Run the strict privacy preflight before export; human review remains required.
5. Run the P27 evidence validator; record integrity result separately from authenticity.
6. Verify detached manifest signature against an independently provisioned public-key fingerprint.
7. Verify detached independent reviewer attestation against a separately pinned reviewer key.
8. Independently establish reviewer identity and independence; cryptographic signature alone cannot prove either.
9. Owner reviews the complete result and records explicit acceptance.

A validator success means artifact structure/integrity only. It does not prove observations true, host identity, key custody, gate PASS or reviewer independence.

## 5. Gate status ledger template

Use this template only in the restricted evidence record; do not fill with invented values.

| Gate | Status (PASS/FAIL/BLOCKED/SKIPPED) | Exact code SHA | Evidence reference/digest | Operator UTC | Reviewer |
|---|---|---|---|---|---|
| G1 | BLOCKED until genuine evidence | — | — | — | — |
| G2 | BLOCKED until genuine evidence | — | — | — | — |
| G3 | BLOCKED until genuine evidence | — | — | — | — |
| G4 | BLOCKED until genuine evidence | — | — | — | — |
| G5 | BLOCKED until genuine evidence | — | — | — | — |
| G6 | BLOCKED until genuine evidence | — | — | — | — |
| G7 | BLOCKED until genuine evidence | — | — | — | — |
| G8 | BLOCKED until genuine evidence | — | — | — | — |
| G9 | BLOCKED until genuine evidence | — | — | — | — |
| G10 | BLOCKED until genuine evidence | — | — | — | — |

## 6. Current project disposition

At the time this checklist is prepared:
- Repository implementation and exact-head CI: PASS on the specific commits recorded in P31/P32.
- This checklist: documentation prepared; no host/device action performed.
- G1–G10: BLOCKED pending genuine external evidence.
- Physical Android and live two-account OIDC: BLOCKED.
- Production Linux host, protected signer, independent durable anchor and sink-side egress: BLOCKED.
- S09-C01: OPEN / NOT COMPLETE.
- S09-C02: NOT STARTED.
- PR #11: Draft / Open / Unmerged.
- Auto-Run OFF; browser/worker disabled; no paid API/payment, deployment, merge, host/firewall mutation or production activation.

**This checklist is not an authorization to perform host-mutating operations.** Obtain explicit owner approval and follow the separate P27/P20 runbooks. No gate may be promoted without real evidence and independent review.
