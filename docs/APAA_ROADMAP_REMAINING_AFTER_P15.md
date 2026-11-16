# APAA — Remaining Roadmap After P15

**Repository:** glad4u7-crypto/TLP-Write-Test  
**Current implementation checkpoint:** APAA-S09-C01-P20 — pinned OCI runtime compatibility gate and unit tests added; runtime qualification pending  
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
| P16 | OCI lifecycle executor | fake-runner tests prove CREATE → INSPECT → ATTEST → START; failures never start; cleanup attempted | Implemented; exact-head CI pending |
| P17 | Proxy–Worker topology (P12 reconciliation) | explicit RFC1918 network contract, topology-scoped proxy bind and endpoint tests | Implementation/tests committed; real OCI network not created or qualified |
| P18 | Post-create signed attestation binding | durable tenant-bound single-use challenge; exact inspected container ID + worker name + launch digest; signature/freshness/firewall checks; executor integration tests | Implementation and integration tests committed; exact-head CI verified; trusted host collector and out-of-band key provisioning remain external qualification |
| P19 | Egress isolation proof | strict nftables evidence parser and negative tests for direct TCP/DNS, UDP, QUIC, IPv6 and unknown ruleset objects | Parser/tests committed; disposable Linux network-namespace qualification added to CI; exact-head result pending; OCI runtime/host firewall integration remains pending |
| P20 | Runtime compatibility | pinned Podman and Docker versions; rootless disposable Linux integration; verify inspect-schema compatibility and cleanup after timeout/cancel | Not started |
| P21 | Browser integration | isolated ephemeral browser only after P16–P20 gates; request/redirect/DNS rebinding policy enforced at network boundary; downloads/profile/CDP blocked | Not started; browsing disabled |
| P22 | Android / Termux qualification | device capability matrix; OCI availability, storage, process, network and browser constraints; no claim until tested | Not started |
| P23 | Integration and release verification | full tests, exact-head CI, security review, threat model, recovery/cleanup drill, owner permission E2E; draft-only report | Not started |

## Dependency order
P17 → P18 → P19 → P20 → P21 → P22 → P23. P16 can be tested in isolation but cannot enable browsing by itself.

## Definition of complete
A checkpoint is complete only when implementation, negative tests, exact-head CI and its stated environment qualification all pass. A mock test is not proof of real host isolation. A documentation item is not runtime evidence. A queued CI run is pending, not PASS.

## Current blockers
1. Trusted host inspector/collector installation and qualification.
2. Out-of-band Ed25519 signing-key provisioning and operational key rotation/revocation procedure.
3. Dedicated internal OCI network creation and qualification.
4. Real TCP/DNS/UDP/QUIC bypass test on a disposable Linux namespace.
5. Pinned Docker/Podman host integration.
6. Exact-head CI for the current P18 test commit.
7. No browser launch is enabled.
8. Android/Termux OCI and browser support is unqualified.

**Current checkpoint:** APAA-S09-C01-P19-LINUX-QUALIFICATION-CI-PENDING.  
**Next:** Verify the disposable Linux namespace job on the exact head; then continue P20 runtime compatibility qualification.
