# APAA Browser Automation A–Z Audit and Execution Plan

**Date:** 2026-11-18  
**Repository:** `glad4u7-crypto/TLP-Write-Test`  
**Audit branch:** `apaa-browser-az-audit-batch1`  
**Base:** `feature/apaa-s09-c01-p01-browser-launch`  
**Disposition:** OPEN — implementation and qualification are not complete.

## Executive decision

The repository contains substantial browser-launch, navigation-policy, read-only inspection, controller, OCI/network-provisioning, proxy, recovery, and attestation work. It does **not** yet demonstrate a production-acceptable browser automation system. The principal blockers are operational rather than a lack of architecture diagrams:

1. Chromium failed in the disposable OCI real-worker qualification with an FD ownership violation and timeout.
2. The diagnostic PR contains useful collectors and symbolication helpers, but its record says the diagnostic Chromium patch was not compiled into the runtime binary; no root cause or fix is established.
3. The OCI qualification harness is not yet the production `IsolatedWorkerBackend`; host-inspector/parser/provider compatibility and WorkerLaunchSpec alignment remain.
4. Proxy/worker endpoint topology has previously been recorded as mismatched. It must be reconciled without broadening listeners.
5. Actual default-deny egress and bypass resistance must be proved on the provisioned worker, not inferred from unit tests or a workflow contract.
6. Physical Android/Termux acceptance has not been run. Current P07 intentionally rejects Playwright browser launch on Android/Termux.
7. Independent security review and explicit final Owner acceptance are absent.

Browser/Worker dispatch must remain disabled and Auto-Run OFF until all release gates pass.

## Evidence-backed current state

### S09-C01 PR #10 — Browser launch, navigation, inspection

- P01 architecture and launch boundary are documented in `docs/APAA_S09_C01_P01_BROWSER_AUTOMATION_ARCHITECTURE.md`.
- `core/browser_launch.py` provides bounded launch options, fresh non-persistent context, disabled downloads, and cleanup. It does not itself provide OS/container or network isolation.
- P02 `core/browser_navigation.py` provides allowlist, HTTPS policy, DNS-answer screening, and bounded redirect-chain validation. `core/safe_navigation.py` adds Playwright request routing. The P02 scope records exact-head APAA Security CI #1417 SUCCESS for commit `3c019ff048bee4e69f0d7ce23f9a8bc5e82fea85`. That is repository CI evidence, not connection-time destination pinning or host egress proof.
- P03 `core/live_browsing.py` includes bounded read-only inspection. The P03 scope lists additional edge-case tests but says exact-head CI is pending. The branch has advanced beyond the P02 verified commit; rerun and record CI against the actual current head before treating P03 as verified.
- The P01/P02/P03 scope documents explicitly keep production worker/network and Android qualification as separate gates.

### P74 OCI/network work — PR #14

The PR description reports code for rootless Podman lifecycle, namespaces, cgroup-v2, seccomp preflight, nftables default-DROP policy, dual-stack proxying, pinned egress, and a real-worker qualification script. It also records:

- Exact-head Python security CI PASS for its recorded PR head.
- Disposable GitHub-hosted Ubuntu 24.04 real-worker Chromium qualification FAILED: Chromium network service crash, FD ownership violation, and 45-second timeout.
- The harness is not yet wired as the production `IsolatedWorkerBackend`.
- Signed host-inspector parser/provider compatibility, WorkerLaunchSpec alignment, and attestor lifecycle work remain.
- Current decision in the PR record: real-host qualification FAILED / NO-GO.

A failed real-host test is a release blocker, not a test to waive.

### P74 diagnostics — PR #23

- Bounded FD/process snapshots, structured log parsing, source-patch tooling and exact-build symbolication fallback are present.
- The PR record explicitly says the diagnostic source patch was not compiled into the Debian runtime Chromium binary; structured failing-FD records are absent.
- The actual failing FD, operation, root cause, and behavioral fix are therefore unknown.
- Several repeat runs reproduced the failure; a later gated job was skipped. A skipped run is not a pass.

Do not make speculative descriptor lifecycle changes or weaken sandbox controls.

### S09-C02 staged work — PRs #24 and #26

- PR #24 has controller-side offline intent/evidence validation and bounded search/filter/navigation contracts. Its record says these do not prove actual DOM visibility or authorize execution.
- PR #26 has a read-only DOM inspector and preview evidence. Its record says it does not click, fill, submit, navigate, or consume Owner approval. Its branch is recorded as 17 commits ahead / 3 behind its base; integration requires a reviewed reconciliation and exact-head CI.
- These PRs are not proof that S09-C01 is qualified and must not be bulk-merged into PR #10.

### Android gate — P07

- `core/runtime_support.py` and the launch path intentionally fail closed on Android/Termux.
- The Android compatibility document says no physical-device qualification has been run and no browser binaries/packages/device settings were changed.
- Therefore Android browser automation is currently unsupported by this branch. Android Python-only preflight can be tested separately; it must not be reported as Chromium/Playwright acceptance.

## A–Z acceptance matrix

| Area | Required acceptance | Current disposition |
|---|---|---|
| Architecture / trust boundaries | Clear owner, policy, browser, worker, proxy, audit responsibilities | Documented; wiring still partial |
| Launch lifecycle | Bounded launch, ephemeral context, cleanup on every partial failure | Implemented; exact-head and host qualification required |
| Navigation policy | HTTPS allowlist, malformed URL rejection, redirect limits | Implemented; CI evidence exists for recorded P02 head |
| Actual request enforcement | Main document, redirects, subresources, frames, popups, WebSockets, background traffic | Not fully operationally qualified |
| DNS / SSRF | Resolve and validate; connection-time destination control; rebinding resistance | Policy exists; connection-time proof missing |
| DOM inspection | Bounded visible-only read; redaction; no hidden/input-value leakage | Implementation/tests present; latest exact-head CI pending |
| Interaction | Fresh target evidence, exact origin, owner approval, no forged/stale locator | Offline foundations staged; live adapter/approval dispatch not qualified |
| Browser host | Concrete trusted host adapter and runtime observation | Incomplete |
| OCI worker | Production backend, immutable runtime identity, least privilege, cleanup | Harness exists; production backend incomplete |
| Network boundary | Default-deny IPv4/IPv6; proxy-only egress; TCP/DNS/UDP/QUIC bypass tests | Real qualification failed / not accepted |
| Proxy | Pinned destination, endpoint topology, TLS/SNI, bounded CONNECT | Components/tests exist; production topology unresolved |
| Attestation | Key custody/rotation, freshness, one-time challenges, replay protection | Partial; external custody/operational proof outstanding |
| Recovery | Crash, timeout, orphan, duplicate/replay, uncertain outcome handling | Repository components/tests exist; end-to-end worker qualification required |
| Audit | Redacted, integrity-checked action lifecycle and evidence | Repository components exist; independent review required |
| Android | Device/runtime support and safe owner-operated acceptance | Physical test not run; browser launch currently fails closed |
| Privacy / owner controls | Owner-only, ask-first, no public access by default | Required; preserve current release restrictions |
| Final release | Independent review + owner acceptance + evidence bundle | Not complete |

## Ordered implementation and verification batches

### Batch 0 — Audit baseline (this document)
- Preserve evidence, distinguish code/CI/host/device proof, and lock release state.
- No merge, deployment, host firewall changes, or live browsing.

### Batch 1 — Exact-head software verification
1. Resolve the current PR #10 branch head and run APAA Security CI on that exact SHA.
2. Confirm P03 tests are included and passing; if failing, fix only the demonstrated regression.
3. Re-run Python syntax, full security suite, TLS tests, request-routing tests, adapter contracts, host-inspector contracts, and browser smoke.
4. Record SHA, workflow run, job conclusions, and test counts. Do not reuse an older SHA's PASS.

**Exit:** exact current PR #10 head has green required checks; P03 remains explicitly partial until then.

### Batch 2 — Chromium FD ownership diagnosis
1. Use the exact runtime Chromium Build-ID and matching symbols/instrumented build.
2. Ensure the diagnostic patch is actually compiled into the binary executed by the disposable worker.
3. Capture structured acquire/release/close records for the exact crashing PID/TID and correlate with bounded process/FD snapshots.
4. Reproduce on disposable infrastructure; isolate the smallest causal sequence.
5. Add a deterministic regression test and minimal fix without weakening sandbox policy.
6. Repeat the full real-worker run and inspect its evidence artifact.

**Exit:** root cause supported by runtime evidence, deterministic regression test, and successful repeated real-worker Chromium run. If not, remain NO-GO.

### Batch 3 — Production host/worker/proxy integration
1. Reconcile proxy and worker endpoint addressing; never widen a listener as a workaround.
2. Implement the trusted production `IsolatedWorkerBackend` and runtime observation provider.
3. Align UID/GID, cgroup, seccomp, mounts, resource limits and WorkerLaunchSpec.
4. Complete signed host-inspector schema compatibility for exact dual-stack nftables state.
5. Complete attestor key lifecycle, one-time challenge consumption, freshness and replay protection.
6. Verify cleanup and recovery for partial create, timeout, crash, orphan and host restart.

**Exit:** independently inspectable runtime identity and policy evidence from the actual disposable host.

### Batch 4 — Network containment qualification
- Prove proxy-only access from inside the actual worker.
- Test direct TCP, DNS, UDP, QUIC/UDP 443, IPv4/IPv6, alternate routes, redirects, subresources, frames, popups, WebSockets, service workers and proxy outage.
- Confirm blocked traffic cannot silently fall back to direct egress.
- Verify nftables exact rule inventory, routes, namespace membership, cgroup membership, seccomp and packet capture.
- Run hostile-network regression suite and inspect sanitized artifacts.

**Exit:** all required negative bypass probes blocked and approved proxy path works; evidence reviewed independently.

### Batch 5 — Android owner-operated qualification
- Begin with a read-only device preflight: Android version, ABI, Python distribution/version, Termux availability, storage/runtime constraints.
- Run only Python-only tests supported by the installed environment; do not install browser binaries, alter permissions, firewall, VPN, proxy, or device settings automatically.
- Record that P07 currently blocks Playwright on Android/Termux. Do not attempt to bypass that guard.
- Evaluate an Android-compatible browser-host architecture separately before any browser launch test.
- Use only a disposable test account/site and synthetic data if a future approved device test becomes possible. No personal browser profile, cookies, credentials, payment, purchase, or production account.

**Exit:** device-specific evidence and a supported runtime design. If no supported browser host exists, mark Android browser automation unsupported rather than passing it.

### Batch 6 — Independent review and Owner acceptance
- Independent security review of source, host evidence, bypass tests, recovery, privacy, and approval boundaries.
- Owner-operated backup/restore drill on the intended runtime.
- Owner acceptance of the evidence bundle.
- Only then consider enabling a narrowly scoped browser capability. This plan does not authorize merge, deployment, or enablement.

## Mandatory safety invariants

- Owner-first access; no public signup or anonymous use by default.
- Ask First for sensitive actions; no Auto-Run.
- No payment, purchase, checkout, trading, or money movement.
- No paid provider, API key, billing change, or unapproved secret provisioning.
- No personal browser profile, imported cookies, credential scraping, or production account tests.
- No arbitrary shell, host firewall changes, or namespace/container provisioning on a personal host.
- No force-push, bulk merge, merge, or deployment as part of this audit.
- Browser/Worker dispatch remains DISABLED until every required gate is evidenced and the Owner explicitly accepts.

## Current checkpoint

**APAA → S09 → C01 → Browser Automation A–Z → Batch 0 recorded; Batch 1 next.**

Current known blockers: PR #10 latest exact-head CI needs re-observation; P03 exact-head CI pending; P74 real-worker Chromium failure unresolved; production worker/host/proxy integration incomplete; real egress qualification not accepted; Android physical qualification not run; independent review and Owner acceptance pending.
