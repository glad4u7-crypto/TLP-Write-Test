# APAA — Remaining Roadmap After P15

**Repository:** glad4u7-crypto/TLP-Write-Test  
**Current implementation checkpoint:** APAA-S09-C01-P20 — implementation and exact-head CI PASS; real OCI daemon qualification pending  
**Release state:** Draft / not merged / live browser disabled

## Guardrails
- Free-only build. No paid provider, API key or charge.
- No payment, purchase, checkout, trading or money movement.
- Ask First for every consequential action; Auto-Run stays disabled.
- Owner-controlled access; no public-by-default access.
- No main-branch merge, deployment, firewall mutation or production activation without separate explicit authorization.
- Never bypass failed attestation, proxy isolation, permission checks or cleanup.

## P15 baseline
P15 added immutable OCI command-plan construction. It is not an operational worker. Rootless mode, pinned image, dedicated egress network, seccomp and firewall are not proven by plan construction alone.

## Work after P15

| Checkpoint | Work | Acceptance evidence | Current state |
|---|---|---|---|
| P16 | OCI lifecycle executor | argv-only CREATE → INSPECT → ATTEST → START; failed gates prevent START; bounded cleanup | Implementation and exact-head CI included in PR #11; real daemon path not yet qualified |
| P17 | Proxy–Worker topology | explicit RFC1918 network contract, topology-scoped proxy bind and endpoint tests | Code/tests delivered; actual OCI network deployment not qualified |
| P18 | Post-create signed attestation | durable tenant-bound single-use challenge; exact container ID + worker name + launch digest; signature/freshness/firewall checks | Code/tests delivered; trusted host collector and out-of-band key provisioning remain external |
| P19 | Egress isolation proof | strict nftables evidence parser and negative tests for direct TCP/DNS, UDP, QUIC, IPv6 and unknown ruleset objects | Parser/tests delivered. Hosted CI namespace job is explicitly SKIPPED; no live egress PASS |
| P20 | Runtime compatibility | pinned Docker/Podman versions; read-only runtime probes; strict inspect normalization; disposable rootless daemon lifecycle and timeout/cancel qualification | Implementation and tests delivered. Exact head `c8104c4ab49ceaaa378d2fa3c6dda61468d1bb29`: Agent Foundation CI PASS (992 tests, audit clean, compile PASS) and Python Demo CI PASS. Real Docker/Podman daemon qualification pending |
| P21 | Browser integration | isolated ephemeral browser only after P16–P20 operational gates; request/redirect/DNS rebinding policy enforced at network boundary; downloads/profile/CDP blocked | Not started; browsing disabled |
| P22 | Android / Termux qualification | device capability matrix; OCI availability, storage, process, network and browser constraints; no claim until tested | Not started |
| P23 | Integration and release verification | full tests, exact-head CI, security review, threat model, recovery/cleanup drill, owner permission E2E; draft-only report | Not started |

## P20 exact-head evidence

- [Agent Foundation CI — run 43795182589](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43795182589): PASS; Python 3.12 compile, dependency audit with no known vulnerabilities, 992 tests passed.
- [Python Demo CI — run 43795182578](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43795182578): PASS.
- The green job named “Disposable Linux egress namespace qualification” only ran a step that reports the operational test as skipped due to hosted-runner capability limits. It is not a live isolation PASS.

Full record: [APAA S09 C01 P20 Runtime Compatibility](APAA_S09_C01_P20_RUNTIME_COMPATIBILITY.md).

## Dependency order
P17 → P18 → P19 → P20 → P21 → P22 → P23. P16 can be tested in isolation but cannot enable browsing by itself.

## Remaining operational blockers
1. Disposable Linux qualification host with real rootless Docker and/or Podman.
2. Real daemon CREATE/INSPECT/ATTEST/START/STOP/REMOVE verification and actual inspect-schema compatibility.
3. Timeout, cancellation, daemon interruption and orphan-cleanup drills.
4. Live namespace egress enforcement and TCP/DNS/UDP/QUIC/IPv6/alternate-interface bypass matrix.
5. Trusted host inspector/collector installation and qualification.
6. Out-of-band Ed25519 key provisioning, rotation, revocation and recovery.
7. Production topology and firewall hook-precedence review.
8. Android/Termux OCI and browser support remains unqualified.
9. P21 browser integration remains disabled until the preceding operational gates pass.

## Definition of complete
A checkpoint is complete only when implementation, negative tests, exact-head CI and its stated environment qualification all pass. Mock tests are not proof of real host isolation. Documentation is not runtime evidence. A queued or explicitly skipped CI step is not PASS.

**Current checkpoint:** APAA-S09-C01-P20-CI-PASS-DAEMON-QUALIFICATION-PENDING.  
**Next:** Run the disposable rootless Docker/Podman qualification and timeout/cancellation drills on a capable isolated Linux host; keep the worker/browser disabled until all gates pass.
