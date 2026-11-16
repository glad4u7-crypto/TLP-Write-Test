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
| G9 — Android + PC assessment | Physical Android and PC browser tests; permission behavior, identity/session transitions, logout/revocation propagation, lifecycle/background limits and explicit boundary between Android control plane and isolated worker | BLOCKED — CI viewport emulation exists; physical-device/browser evidence absent |
| G10 — Independent review | Independent reviewer verifies evidence authenticity, host identity, key custody, anchor, sink observations, cleanup, owner grant/revoke controls, resource authorization boundaries, two-user OIDC results and exact code/evidence digests | BLOCKED — no signed independent approval |

## 3. Evidence acceptance rules

1. Use the P27 evidence pack's nine required JSON artifacts and manifest builder.
2. Collect evidence only on an owner-approved disposable host with a locally available digest-pinned image.
3. Keep private keys, tokens, credentials, environment dumps and personal data out of the evidence bundle and repository.
4. Sign the exact raw manifest bytes with the approved evidence signer. Verify against a public-key fingerprint provisioned independently out-of-band.
5. Bind the independent review attestation to the exact manifest digest and verify it with a separately pinned reviewer key.
6. The owner must independently establish reviewer identity and independence; cryptographic validity alone does not do this.
7. Any missing prerequisite, missing artifact, skipped mandatory test, unexplained network observation, failed assertion or untrusted key is BLOCKED or FAIL, never PASS.
8. After any code change, rerun mandatory CI and repeat every affected host gate against the new exact code SHA.

## 4. Android-first boundary

Android remains the primary owner interface and control plane. Android/Termux is not accepted as a hostile-code isolation boundary and must not be used to claim Linux worker qualification. The current architecture decision does not prove a native Android app, PWA, physical-device test, or isolated worker is already operational.

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
- Project checkpoint association is independently bound to an owner-authorized project before any collaborator/API exposure.
- Two distinct real OIDC accounts are used; synthetic principals and unit tests are not accepted as live OIDC evidence.
- Android and PC browsers are both exercised physically for sign-in, sign-out, session switch, revocation, storage isolation and responsive behavior.

Until those tests and the other mandatory gates are independently approved, the safe default remains owner-only application access; no collaborator UI/API is enabled.
