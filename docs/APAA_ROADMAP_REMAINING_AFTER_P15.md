# APAA — Remaining Roadmap After P15

**Repository:** glad4u7-crypto/TLP-Write-Test  
**Current checkpoint:** APAA-S09-C01-P26 — external inspector signing-provider boundary implemented; exact-head four-workflow CI PASS on `8f1f41c17306e35cfea30e7b0b28115ef98c7dad`; production TPM/HSM, monotonic anchor, trusted host collector and full real-daemon/topology qualification remain pending  
**P26 code commit:** 8f1f41c17306e35cfea30e7b0b28115ef98c7dad  
**Latest documentation/roadmap commit:** e590c46bb0e0fffcfa9abe6edf8e5043844b693c  
**Release state:** Draft / not merged / live browser disabled

## Guardrails
- Free-only. No paid provider, API key or charge.
- No payment, purchase, checkout, trading or money movement.
- Ask First for consequential actions; Auto-Run stays disabled.
- Owner-controlled access; no public-by-default access.
- No merge, deployment, host firewall mutation or production activation without separate explicit authorization.
- Never bypass failed attestation, proxy isolation, permission checks or cleanup.

## Work after P15

| Checkpoint | Work | Acceptance evidence | Current state |
|---|---|---|---|
| P16 | OCI lifecycle executor | argv-only CREATE → INSPECT → ATTEST → START; failed gates prevent START; bounded cleanup | Implementation/tests delivered; latest exact-head CI PASS; real daemon path not qualified |
| P17 | Proxy–Worker topology | explicit RFC1918 network contract, topology-scoped proxy bind and endpoint tests | Code/tests delivered; actual OCI network deployment not qualified |
| P18 | Post-create signed attestation | durable tenant-bound single-use challenge; exact container ID + worker name + launch digest; signature/freshness/firewall checks | Code/tests delivered; trusted host collector and out-of-band key provisioning remain external |
| P19 | Egress isolation proof | strict nftables evidence parser and negative tests for direct TCP/DNS, UDP, QUIC, IPv6 and unknown ruleset objects | Parser/tests delivered; disposable Linux namespace egress script passes in exact-head CI; full worker topology and bypass matrix remain pending |
| P20 | Runtime compatibility | pinned Docker/Podman versions; read-only runtime probes; strict inspect normalization; disposable rootless daemon lifecycle and timeout/cancel qualification | Read-only host preflight delivered; immutable-ID lifecycle and fail-closed timeout/daemon-disconnect regression tests delivered. Exact-head Agent Foundation and Python Demo CI each PASS with 1002 tests; compile, dependency audit, demo smoke and disposable namespace egress qualification PASS. Real Docker/Podman daemon lifecycle, signed host collector, real timeout/cancel/orphan cleanup and full worker-topology egress qualification remain pending |
| P21 | Browser integration | isolated ephemeral browser only after P16–P20 operational gates; request/redirect/DNS rebinding policy enforced at network boundary; downloads/profile/CDP blocked | Restricted foundations exist; live browser integration remains blocked by redirect-hop, pinned-IP dialer and complete transport-level egress qualification; browsing disabled |
| P22 | Android / Termux qualification | device capability matrix; OCI availability, storage, process, network and browser constraints | Conservative Android/Termux detection and fail-closed browser block implemented; physical device/OCI/browser qualification not performed |
| P23 | Integration and release verification | full tests, exact-head CI, security review, threat model, recovery/cleanup drill, owner permission E2E; draft-only report | Executor/attestation-gate code and disposable Podman CI workflow exist; production host integration, recovery drills and owner-permission E2E remain pending |

## P20 exact-head CI and egress evidence

For code commit [e669a8767fa7471056e3695fca36d413d435675a](https://github.com/glad4u7-crypto/TLP-Write-Test/commit/e669a8767fa7471056e3695fca36d413d435675a):

- [Agent Foundation CI run 43801033918](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43801033918): **PASS**; Foundation tests **1002 passed**; Python 3.12 compile **PASS**; dependency audit **PASS — no known vulnerabilities found**.
- [Python Demo CI run 43801033691](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43801033691): **PASS**; tests **1002 passed**; `demo.py` output check **PASS**.
- Disposable Linux egress namespace qualification: **PASS**. The test created a disposable network namespace/veth pair and namespace-local nftables rules; only the exact IPv4 TCP proxy endpoint was allowed. Direct TCP, DNS TCP/UDP, UDP/443 and IPv6 probes were blocked from reaching the host-side sink.
- This namespace test does not prove the final OCI worker/proxy topology or alternate-interface bypass resistance.

## P20 host-side preflight

Run on a disposable Linux host with the exact operator-approved version pin:

```bash
python -m scripts.qualify_oci_runtime_preflight --runtime podman --pinned-version 5.4.2
```

The version is an example only. The command performs read-only version/info/help probes. Exit 0 means the runtime contract preflight passed; it does not create or start a worker and does not qualify lifecycle, signed attestation, cleanup or egress.

See [P20 Disposable Linux Host Runbook](APAA_S09_C01_P20_DISPOSABLE_HOST_RUNBOOK.md) and [P20 Runtime Compatibility Report](APAA_S09_C01_P20_RUNTIME_COMPATIBILITY.md).

## Remaining operational blockers

1. Disposable Linux host with real rootless Docker and/or Podman, separately approved pinned versions and a locally available digest-pinned test image.
2. Actual CREATE/INSPECT/ATTEST/START/STOP/REMOVE verification against a real daemon.
3. Trusted host inspector/collector installation and out-of-band Ed25519 key provisioning, rotation, revocation and recovery. Do not substitute self-asserted or test-key evidence.
4. Real-daemon timeout, cancellation, daemon interruption and orphan-cleanup drills; unit tests alone are not host evidence.
5. Full worker-topology egress enforcement, including alternate-interface bypass resistance, external DNS policy, IPv6 UDP and host firewall hook precedence.
6. Host firewall hook-precedence and production topology review.
7. Android/Termux OCI and browser support remains unqualified.
8. P21 browser integration remains disabled until preceding operational gates pass.

## Definition of complete

A checkpoint is complete only when implementation, negative tests, exact-head CI and its stated environment qualification all pass. Mock tests are not proof of real host isolation. Documentation is not runtime evidence. A queued or explicitly skipped CI step is not PASS.

**Current checkpoint:** APAA-S09-C01-P27-REAL-HOST-QUALIFICATION-EVIDENCE-PACK-DRAFTED-CI-PASS-REAL-HOST-QUALIFICATION-BLOCKED.  
**Next:** Owner must provide/approve a disposable Linux host, protected signing key, independent monotonic anchor and local digest-pinned test image. Then execute the P27 evidence pack and obtain independent review. Do not start C02 or enable worker/browser until all mandatory C01 gates pass.


## P24–P26 follow-on trust work (2026-11-16)

- **P24 Signed inspector trust bundle:** implementation and exact-head CI passed; signature verification uses an independently pinned root key and strict bundle schema. Production trust-root custody and authenticated configuration integration remain external.
- **P25 Monotonic inspector trust sequence:** implementation and exact-head CI passed on `7f4992b3a9f83daff8ba592390254488db25aee4`; the sequence backend is a protocol contract with an in-memory test fake only. No independently administered durable anti-rollback anchor is provisioned or qualified.
- **P26 External inspector signing provider:** implementation and all four exact-head workflows passed on `8f1f41c17306e35cfea30e7b0b28115ef98c7dad`: Agent Foundation CI #43808497146, Python Demo CI #43808497002, P20 Runtime Qualification #43808496957 and P23 Executor Integration #43808496949. This validates code/tests and CI disposable runner checks only. No TPM/HSM adapter or host key is provisioned.

## C01 closure decision — 2026-11-16

**C01 remains OPEN / NOT COMPLETE. C02 must not start.**

Remaining hard acceptance gates (not replaceable by unit tests or documentation):
1. An owner-approved disposable Linux host/runtime and locally available digest-pinned test image, with actual APAA CREATE/INSPECT/ATTEST/START/STOP/REMOVE execution.
2. A real least-privilege host collector, provisioned out-of-band Ed25519 trust root and inspector signing key (preferably non-exportable TPM/HSM), with rotation/revocation and recovery tests.
3. A separately administered durable monotonic sequence anchor with atomic compare-and-swap, restart/concurrency and backup/restore rollback rejection tests.
4. End-to-end worker/proxy topology qualification, including redirect-aware proxy enforcement, pinned-IP connection at dial time, DNS rebinding, WebSocket, UDP/QUIC, IPv6, alternate-interface bypass and host firewall hook precedence.
5. Bounded timeout/cancel/daemon interruption/orphan cleanup drills against the real daemon.
6. Physical Android/Termux capability assessment. Browser launch must remain denied on Android until supported OCI/browser/network isolation is demonstrated.
7. Final exact-head CI after all code changes, independent security review and owner-controlled permission/access E2E.

**No live browsing, production worker, host mutation, firewall change, deployment, PR merge, paid service, API key or Auto-Run is authorized by this roadmap.**


## Latest exact-head verification — documentation commit `e590c46bb0e0fffcfa9abe6edf8e5043844b693c`

All four workflows completed successfully on this exact commit:
- Agent Foundation CI #43808654976 — **PASS** (both the main test job and disposable Linux egress namespace qualification passed).
- Python Demo CI #43808654967 — **PASS**.
- P20 Rootless Podman Runtime Qualification #43808654979 — **PASS**. The disposable GitHub-hosted runner completed rootless Podman setup, local digest-addressed image build without pulling, hardened container CREATE/INSPECT, START, running-state verification, STOP, REMOVE by immutable ID, no-leftover-container check and sanitized evidence upload.
- P23 Rootless Podman Executor Integration #43808654973 — **PASS**.

This is stronger than a unit-test-only result: CI exercised a real disposable rootless Podman daemon lifecycle. It still does not qualify the user's own host, a production host collector/key, TPM/HSM custody, durable independent monotonic storage, Docker rootless lifecycle, Android/Termux, or the full APAA worker/proxy egress topology. C01 remains open until those mandatory environment-dependent gates are independently satisfied.


## P26/P27 latest verification — 2026-11-16

- P26 software boundary and security gate documentation are committed; no production TPM/HSM, host key, collector service or independent monotonic anchor is provisioned.
- All four workflows completed **PASS** on exact documentation head `1230e97fd8f83d5efc154bf18bf7cabc9c4a35c9`:
  - Agent Foundation CI #929 — [run 43809225079](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43809225079).
  - Python Demo CI #1004 — [run 43809225000](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43809225000).
  - P23 Rootless Podman Executor Integration #40 — [run 43809225001](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43809225001).
  - P20 Rootless Podman Runtime Qualification #58 — [run 43809224997](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43809224997).
- P27 added `docs/APAA_S09_C01_P27_REAL_HOST_QUALIFICATION_EVIDENCE_PACK.md`, defining hard prerequisites, evidence manifest, trust/signer checks, real-daemon attestation lifecycle, egress probes, cleanup, integrity and independent review.
- P27 is an operator evidence specification, not a claim that real-host tests have run. Real-host security qualification remains BLOCKED pending owner-approved infrastructure and independently reviewed evidence.
- PR #11 remains Draft/Open/Unmerged. No deployment, host mutation, firewall change, worker/browser activation, paid service, API key or Auto-Run.


## P27 manifest validator implementation — 2026-11-16

- Added `scripts/validate_apaa_p27_evidence.py` using only the Python standard library. It validates the closed manifest fields, UTC timestamps, immutable SHA-256 image reference, safe relative artifact paths, exact artifact inventory and per-file SHA-256 digests.
- Added `tests/test_apaa_p27_evidence.py` covering valid packs, tampering, unlisted/missing artifacts, path traversal, non-UTC timestamps, mutable image references and CLI exit behavior.
- The validator explicitly reports authenticity as NOT_CHECKED and host qualification as NOT_ASSESSED. It cannot approve a host, verify a detached signature or convert test outcomes to PASS.
- CI for the implementation commit must pass before this code is treated as verified. Real-host key custody, independent monotonic anchor, actual worker/proxy topology and independent review remain BLOCKED.


## APAA S09 C01 — P27 detached evidence signature verifier (2026-11-16)

- Implemented Ed25519 detached signature verification over the exact raw manifest bytes in `scripts/validate_apaa_p27_evidence.py`.
- The detached signature and raw 32-byte public key must be regular non-symlink files outside the evidence directory. The caller must supply an independently provisioned public-key SHA-256 fingerprint; signature verification cannot bootstrap trust from a key embedded in the evidence pack.
- Added negative tests for manifest alteration, wrong signer key, wrong pinned fingerprint, sidecar placement and incomplete trust inputs. Test private keys are ephemeral and test-only.
- Latest exact implementation head `1009939c847a2fc3157e9715e79bacacad89ced0`: all four required CI workflows PASS; Foundation and Demo suites each report 1049 passed, 7 skipped; P23 and P20 rootless Podman qualification PASS.
- The result `VERIFIED_ED25519` proves only that the exact manifest bytes verify under the supplied pinned public key. It does not prove who controls that key, protected hardware custody, real-host identity, truthful observations, or network isolation.
- **Next:** define an independent reviewer-verification/disposition contract and test it against the manifest digest and signer fingerprint. Keep host qualification BLOCKED until owner-approved real host, out-of-band trust provisioning, protected signer, durable anti-rollback anchor and sink-side network evidence exist.


## Signed independent reviewer disposition

The repository includes `scripts/verify_apaa_p27_review.py` to verify a detached reviewer attestation after the evidence manifest has passed integrity and Ed25519 signature verification. The reviewer attestation is canonical JSON signed by a separate Ed25519 reviewer key and binds the exact SHA-256 digest of the raw manifest bytes, reviewer ID, UTC review time, disposition (PASS/FAIL/BLOCKED), reviewer-key fingerprint and findings. The attestation, signature and reviewer public key must be outside the evidence directory. The reviewer key fingerprint must be independently pinned out-of-band.

The verifier reports `reviewer_identity=OUT_OF_BAND_IDENTITY_CHECK_REQUIRED` and `reviewer_independence=OUT_OF_BAND_INDEPENDENCE_CHECK_REQUIRED`. Even a cryptographically valid PASS disposition returns `qualification_approval=NOT_GRANTED_BY_CRYPTOGRAPHIC_VERIFICATION`; an owner must independently establish the reviewer identity and independence and approve the exact evidence/code. This verifier cannot prove the real host or the truth of observations.

Example:

```bash
python -m scripts.verify_apaa_p27_review EVIDENCE_DIRECTORY \
  --manifest-signature /secure/evidence/manifest.sig \
  --manifest-public-key /secure/trust/host-evidence.pub \
  --manifest-key-sha256 OUT_OF_BAND_HOST_KEY_FINGERPRINT \
  --review-attestation /secure/review/review-attestation.json \
  --review-signature /secure/review/review-attestation.sig \
  --review-public-key /secure/trust/reviewer.pub \
  --review-key-sha256 OUT_OF_BAND_REVIEWER_KEY_FINGERPRINT
```


P27 review-verifier tests cover digest binding, pinned reviewer key, tampering, PASS-with-findings rejection, UTC timestamp and detached sidecar placement. The verifier is a cryptographic evidence tool only; reviewer identity/independence and overall qualification approval remain owner-controlled external gates.
