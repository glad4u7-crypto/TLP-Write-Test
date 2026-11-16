# APAA — Remaining Roadmap After P15

**Repository:** glad4u7-crypto/TLP-Write-Test  
**Current implementation checkpoint:** APAA-S09-C01-P16 — gated OCI lifecycle executor  
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
| P16 | OCI lifecycle executor | fake-runner tests prove CREATE → INSPECT → ATTEST → START; failures never start; cleanup attempted | Implemented; P18 durable identity-bound gate integrated; exact-head CI pending |
| P17 | Proxy–Worker topology (P12 reconciliation) | explicit RFC1918 network contract, topology-scoped proxy bind and endpoint tests | Implementation/tests committed; real OCI network not created or qualified |
| P18 | Post-create signed attestation binding | durable tenant-bound single-use challenge; exact inspected container ID + worker name + launch digest; signature/freshness/firewall checks | Control-plane integration committed; key provisioning and trusted host collector qualification pending |
| P19 | Egress isolation proof | strict nftables evidence parser and negative tests for direct TCP/DNS, UDP, QUIC, IPv6 and unknown ruleset objects | Parser/tests committed; actual kernel/namespace bypass tests pending |
| P20 | Runtime compatibility | pinned Podman and Docker versions; rootless disposable Linux integration; verify inspect-schema compatibility and cleanup after timeout/cancel | Not started |
| P21 | Browser integration | isolated ephemeral browser only after P16–P20 gates; request/redirect/DNS rebinding policy enforced at network boundary; downloads/profile/CDP blocked | Not started; browsing disabled |
| P22 | Android / Termux qualification | device capability matrix; OCI availability, storage, process, network and browser constraints; no claim until tested | Not started |
| P23 | Integration and release verification | full tests, exact-head CI, security review, threat model, recovery/cleanup drill, owner permission E2E; draft-only report | Not started |

## Dependency order
P17 → P18 → P19 → P20 → P21 → P22 → P23. P16 can be tested in isolation but cannot enable browsing by itself.

## Definition of complete
A checkpoint is complete only when implementation, negative tests, exact-head CI and its stated environment qualification all pass. A mock test is not proof of real host isolation. A documentation item is not runtime evidence. A queued CI run is pending, not PASS.

## Current blockers
1. No trusted host inspector/collector is installed or qualified.
2. No out-of-band Ed25519 signing-key provisioning and durable one-time challenge store.
3. Proxy–worker network topology has not been reconciled.
4. No real TCP/DNS/UDP/QUIC bypass test on a disposable Linux namespace.
5. No pinned Docker/Podman host integration.
6. No browser launch is enabled.
7. Android/Termux OCI and browser support is unqualified.

**Current checkpoint:** APAA-S09-C01-P16-IMPLEMENTED-CI-PENDING.  
**Next:** APAA-S09-C01-P17 — Proxy–Worker topology contract and test design.
