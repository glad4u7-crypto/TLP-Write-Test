# APAA — Remaining Roadmap After P15

**Repository:** glad4u7-crypto/TLP-Write-Test  
**Current checkpoint:** APAA-S09-C01-P20 — read-only host preflight and lifecycle hardening delivered; exact-head Agent Foundation + Python Demo CI PASS (1002 tests each); disposable namespace egress qualification PASS; real daemon lifecycle qualification pending  
**Latest code commit:** e669a8767fa7471056e3695fca36d413d435675a  
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
| P21 | Browser integration | isolated ephemeral browser only after P16–P20 operational gates; request/redirect/DNS rebinding policy enforced at network boundary; downloads/profile/CDP blocked | Not started; browsing disabled |
| P22 | Android / Termux qualification | device capability matrix; OCI availability, storage, process, network and browser constraints | Not started |
| P23 | Integration and release verification | full tests, exact-head CI, security review, threat model, recovery/cleanup drill, owner permission E2E; draft-only report | Not started |

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

**Current checkpoint:** APAA-S09-C01-P20-CODE-AND-CI-PASS-REAL-OCI-DAEMON-QUALIFICATION-PENDING.  
**Next:** Qualify a real rootless Docker/Podman daemon on a disposable Linux host, including trusted collector and signed attestation, then exercise lifecycle and bounded cleanup. Keep worker/browser disabled until all gates pass.
