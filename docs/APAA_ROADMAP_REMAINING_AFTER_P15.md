# APAA — Remaining Roadmap After P15

**Repository:** glad4u7-crypto/TLP-Write-Test  
**Current checkpoint:** APAA-S09-C01-P20 — read-only host preflight and tests added; hosted live-egress attempt failed due IPv6/network capability limits; real daemon qualification pending  
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
| P16 | OCI lifecycle executor | argv-only CREATE → INSPECT → ATTEST → START; failed gates prevent START; bounded cleanup | Implementation/tests delivered; real daemon path not qualified |
| P17 | Proxy–Worker topology | explicit RFC1918 network contract, topology-scoped proxy bind and endpoint tests | Code/tests delivered; actual OCI network deployment not qualified |
| P18 | Post-create signed attestation | durable tenant-bound single-use challenge; exact container ID + worker name + launch digest; signature/freshness/firewall checks | Code/tests delivered; trusted host collector and out-of-band key provisioning remain external |
| P19 | Egress isolation proof | strict nftables evidence parser and negative tests for direct TCP/DNS, UDP, QUIC, IPv6 and unknown ruleset objects | Parser/tests delivered. Namespace workflow has previously reported a hosted-runner limitation; no live egress PASS |
| P20 | Runtime compatibility | pinned Docker/Podman versions; read-only runtime probes; strict inspect normalization; disposable rootless daemon lifecycle and timeout/cancel qualification | Added read-only host preflight command and tests (995 tests passed on code head `b4b2d3bf`); the first live egress attempt on hosted Ubuntu failed because IPv6/network capabilities were unavailable. Script now fails early with actionable diagnostics; latest-head CI pending. Real Docker/Podman daemon lifecycle and timeout/cancel qualification remain pending |
| P21 | Browser integration | isolated ephemeral browser only after P16–P20 operational gates; request/redirect/DNS rebinding policy enforced at network boundary; downloads/profile/CDP blocked | Not started; browsing disabled |
| P22 | Android / Termux qualification | device capability matrix; OCI availability, storage, process, network and browser constraints | Not started |
| P23 | Integration and release verification | full tests, exact-head CI, security review, threat model, recovery/cleanup drill, owner permission E2E; draft-only report | Not started |

## P20 live egress qualification attempt

The hosted runner attempt failed to bind the IPv6 sink and could not create a required IPv6 socket (`Operation not permitted`). This is not an egress PASS. See [failed run 43795768030](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43795768030). The script now preflights IPv6 addresses/sockets and namespace-local nftables permissions; a capable disposable Linux runner is still required.

## P20 host-side preflight

Run on a disposable Linux host with the exact operator-approved version pin:

```bash
python -m scripts.qualify_oci_runtime_preflight --runtime podman --pinned-version 5.4.2
```

The version is an example only. The command performs read-only version/info/help probes. Exit 0 means the runtime contract preflight passed; it does not create or start a worker and does not qualify lifecycle, signed attestation, cleanup or egress.

See [P20 Disposable Linux Host Runbook](APAA_S09_C01_P20_DISPOSABLE_HOST_RUNBOOK.md) and [P20 Runtime Compatibility Report](APAA_S09_C01_P20_RUNTIME_COMPATIBILITY.md).

## Previously verified CI evidence

At implementation head `c8104c4ab49ceaaa378d2fa3c6dda61468d1bb29`:
- [Agent Foundation CI — run 43795182589](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43795182589): PASS; compile PASS, dependency audit clean, 992 tests passed.
- [Python Demo CI — run 43795182578](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43795182578): PASS.

At documentation head `72ea66fee9823df4f27d13738b482b953cc28f85`, all checks completed; however, the egress job ran a limitation-report step and was not a live isolation PASS.

## Dependency order
P17 → P18 → P19 → P20 → P21 → P22 → P23. P16 can be tested in isolation but cannot enable browsing by itself.

## Remaining operational blockers
1. Disposable Linux host with real rootless Docker and/or Podman, pinned versions and local digest-pinned test image.
2. Actual CREATE/INSPECT/ATTEST/START/STOP/REMOVE verification.
3. Timeout, cancellation, daemon interruption and orphan-cleanup drills.
4. Live namespace egress enforcement and TCP/DNS/UDP/QUIC/IPv6/alternate-interface bypass matrix.
5. Trusted host inspector/collector installation and out-of-band Ed25519 key provisioning, rotation, revocation and recovery.
6. Host firewall hook-precedence and production topology review.
7. Android/Termux OCI and browser support remains unqualified.
8. P21 browser integration remains disabled until preceding operational gates pass.

## Definition of complete
A checkpoint is complete only when implementation, negative tests, exact-head CI and its stated environment qualification all pass. Mock tests are not proof of real host isolation. Documentation is not runtime evidence. A queued or explicitly skipped CI step is not PASS.

**Current checkpoint:** APAA-S09-C01-P20-HOST-PREFLIGHT-ADDED-EGRESS-RUNNER-LIMITED-DAEMON-QUALIFICATION-PENDING.  
**Next:** Review the new exact-head CI, then run the read-only preflight and lifecycle/timeout qualification on a capable disposable Linux host. Keep worker/browser disabled until all gates pass.
