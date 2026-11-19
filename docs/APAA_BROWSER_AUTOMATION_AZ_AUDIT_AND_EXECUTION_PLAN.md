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


## Evidence update — Batch 1 exact-head CI PASS (2026-11-18)

- Audit branch commit: `53a57e51d6716ce31f6e01b173d43c53feee3fd6`.
- APAA Security CI run #1424 / ID `44352009348`: **SUCCESS** on that exact SHA.
- All workflow steps completed successfully: Python syntax; P01 launch lifecycle; trusted-CA, hostname-mismatch and expired-certificate TLS tests; live-browsing controller policy/lifecycle; real Chromium through restricted local proxy; production worker adapter contract; Linux host inspector contract; remaining security suite.
- This closes the repository CI gate for this exact audit-branch head only. It does not override the separately recorded P74 disposable OCI Chromium failure, does not prove production egress isolation, and does not qualify Android/Termux.

## Batch 2 — Chromium FD ownership diagnosis: evidence and hard boundary

The diagnostic evidence in PR #23 / P74 matrix now establishes:
- The FD ownership crash is reproducible in the disposable OCI worker, including before proxy/navigation (local `data:` smoke).
- Process attribution is partial. The browser-side log PID and stack-matched child candidate are distinct; they must not be conflated.
- Shared pipe/memfd inode observations are candidates only, not proof of an erroneous hand-off.
- Exact failing FD, ownership operation, causal call site and root cause remain **unidentified**.
- The Debian runtime Chromium binary is not instrumented with the structured fatal-path diagnostic patch. Patch-application/parser PASS is not runtime instrumentation.
- The upstream Chromium source pin is known, but Debian source-package patch-series equivalence and a compiled matching diagnostic binary remain unproven.
- A narrow diagnostic patch/build recipe exists. It preserves the existing fatal check and does not mutate descriptors, but it has not yet been compiled into the exact runtime image.

### Software-only work that can proceed now
1. Audit the diagnostic patch against the pinned upstream source and inspect its parser/build workflow for correctness.
2. Expand deterministic Python tests for evidence correlation, redaction, PID reuse and bounded capture wherever the current code exposes testable behavior.
3. Add an explicit compatibility/evidence validator that refuses to label diagnostic output as instrumented unless the runtime binary build identity and diagnostic record provenance are both present.
4. Keep a precise list of source-package/build-host/OCI steps that cannot be completed by repository-only tooling.

### External execution gates (deferred)
- Obtain and verify the exact Debian source package and patch series.
- Compile the diagnostic Chromium binary on a disposable Linux build host.
- Run it in the disposable OCI worker under unchanged sandbox and egress policy.
- Capture the first actual FD/operation/PID/TID, then implement only an evidence-justified minimal fix and Chromium-native regression.
- Repeat at least 10 cold starts after a candidate fix.

No behavioral fix is justified today. Release remains **FAILED / NO-GO**; Browser/Worker disabled; Auto-Run OFF.


## Architecture addendum and software correction — 2026-11-19

- Added `docs/APAA_BROWSER_AUTOMATION_PRODUCTION_ARCHITECTURE.md`: end-to-end trust domains, authorized execution sequence, security invariants, failure semantics, implementation map and independently evidenced release gates.
- The architecture explicitly separates the local Playwright launch foundation from the production isolated worker. It does not claim that the existing `IsolatedWorkerBackend` protocol is itself a working Podman backend.
- Software audit found a false-positive evidence claim in `scripts/p74_real_worker_chromium_e2e.py`: `fd_ownership_crash_pid_proven` was set to `bool(fd_diagnostics)`. A structured record anywhere in shared stderr proves that instrumentation emitted a record, not that the record's process emitted the fatal marker.
- Corrected the qualification evidence logic to require a structured record before the fatal marker, a PID/TID prefix on that same diagnostic line matching the record, and agreement with the final prefixed log identity before the fatal marker. Instrumentation presence remains a separate field. Missing/mismatched/interleaved identity fails closed.
- Added regression tests for matching identity, another process logging between the diagnostic record and fatal marker, and a record whose embedded PID/TID disagrees with its log prefix.
- PR #23 latest code head: `3e54057215d4502ffd72c59c35f9c8245bd2b3d4`.
- Targeted P74 diagnostic/symbolication tests: run [44435122181](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/44435122181) — **PASS** on the latest code head.
- Pinned Chromium patch/parser validation: run [44435122836](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/44435122836) — **PASS** on the latest code head.
- Full APAA Security CI run [44435122304](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/44435122304) is pending at this update. Earlier full CI PASS on `12ae7b4190d8c26771386c916085c386c024b9bf` does not certify the new correction.
- P74 real OCI job [44435122167](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/44435122167) was skipped by the explicit Owner gate; it is not runtime qualification.
- No root cause, offending FD, behavioral fix or production worker qualification is claimed. Browser/Worker remain DISABLED; Auto-Run OFF.

### Batch 3 — production integration audit

The current code confirms `core/browser_worker_adapter.py` defines an injected `IsolatedWorkerBackend` protocol and requires an explicitly supplied backend. The OCI runtime, observer, host inspector, nftables attestation, keyring and challenge-ledger components are present, but a concrete production backend that composes them and starts the browser only after fresh verified attestation is not yet demonstrated. The `WorkerLaunchSpec` ↔ `OCIWorkerSpec` mapping, actual dual-stack host-inspector schema, production control channel and deployment key custody/restore must be implemented and tested before this layer can be called complete.

**Next software-only work:** map exact constructor/field contracts across `WorkerLaunchSpec`, `OCIWorkerSpec`, observer, namespace/firewall provisioners and adapter callbacks; implement only deterministic, testable composition that does not run host provisioning in CI; add fake-runtime contract tests. Real host firewall, OCI Chromium and device acceptance remain external gates.


## Batch 3 software integration finding — worker identity mismatch (2026-11-19)

A direct contract comparison found a concrete mismatch:
- `WorkerLaunchSpec` permits and binds an explicit non-root UID/GID (the existing contract tests use UID/GID 10001).
- The OCI create path previously hardcoded `--user 65532:65532`.
- The runtime observer also hardcoded the expected identity as `65532:65532`.
- Therefore a valid launch spec using another permitted UID/GID could not be faithfully enforced or attested by the OCI implementation.

Software correction on PR #14:
- `OCIWorkerSpec` now carries bounded non-root `uid` and `gid` fields (backward-compatible defaults 65532).
- Podman create now uses the exact spec identity rather than a hardcoded identity.
- `PodmanWorkerObserver` now compares the observed OCI `Config.User` with the exact immutable spec UID/GID.
- Added regression tests for a non-default UID/GID, mismatched identity, and root/out-of-range/bool identity rejection.
- PR #14 current code head: `01d9e5e798448e47990cc4573a450b8400c8b6e4`.
- Targeted P74 diagnostic/symbolication suite on that head: run [44435513420](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/44435513420) — **PASS**. (This workflow includes the worker qualification script and relevant tests, but does not by itself certify the OCI observer contract.)
- Full APAA Security CI run [44435513302](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/44435513302) is queued/pending at this update.
- Real OCI worker qualification run [44435513283](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/44435513283) is skipped by the Owner gate, not passed.

**Still open in Batch 3:** exact `WorkerLaunchSpec` mapping for writable mounts and proxy endpoint; concrete production `IsolatedWorkerBackend`; a fixed, authenticated browser-worker control channel; independent host observation of the effective UID/GID and all runtime settings; exact dual-stack nftables parser/provider integration; external key custody/rotation/restore. The UID/GID fix closes only the hardcoded identity mismatch, not the full production integration gate.


## Architecture/design completion update — 2026-11-19

The target architecture decision layer has now been completed in documentation:

- Expanded `docs/APAA_BROWSER_AUTOMATION_PRODUCTION_ARCHITECTURE.md` with normative component ownership/contracts, versioned typed-job envelope, capability/approval matrix, worker lifecycle state machine, signed evidence requirements, browser action/evidence contract, recovery/privacy rules, deployment profiles and an explicit completion checklist.
- Added `docs/APAA_BROWSER_AUTOMATION_ARCHITECTURE_DECISIONS.md` with nine Architecture Decision Records covering Owner-first authorization, planner/execution separation, capability separation, ephemeral worker, proxy-only dual-stack egress, independent attestation, fail-closed uncertainty, Android host separation and prohibition of financial actions.
- Explicitly documented that target design completion does not equal implementation or qualification completion.
- Recorded a concrete code/design mismatch: `core/browser_nftables.py` currently parses a narrow IPv4 destination + TCP + exact-port output allowlist and does not demonstrate IPv6 destination-rule validation. This cannot substantiate the architecture's dual-stack egress claim. The parser/provider/fixtures must be extended and reviewed; no dual-stack attestation claim is accepted until then.
- Remaining software integration blockers are concrete production `IsolatedWorkerBackend` composition, trusted OCI runtime observation provider, authenticated worker control channel, full `WorkerLaunchSpec` to OCI mapping (including mounts/proxy/resources), complete nftables effective-ruleset validation, and operational attestor key/challenge lifecycle.
- External qualification blockers remain unresolved Chromium FD ownership root cause, disposable-host OCI/egress qualification, Android support qualification, independent review and Owner acceptance.

Documentation commits on `apaa-browser-az-audit-batch1`:
- Architecture contract expansion: `2bdfd0ca0f69e125516d638ffa51be9d31a94fbe`
- Architecture decision records: `b2a824dabd2e33e3a75d5774ef2f872c43d5124c`

No merge, deployment, host provisioning, Browser/Worker enablement or Auto-Run activation was performed.


### PR #14 exact-head CI follow-up — 2026-11-19

- Full APAA Security CI run `44435513302` completed **FAILURE** on SHA `01d9e5e798448e47990cc4573a450b8400c8b6e4`: 1,254 passed, 1 failed. The failure was isolated to the newly added UID/GID test fixture: its stdout used a literal backslash-n instead of a newline, causing the fixture's output ID and cidfile ID to disagree. All preceding TLS, live-browsing, worker-adapter and host-inspector contract steps passed.
- Corrected only that test fixture on PR #14 in commit `4a8d02b63158cc38cbdb8092a7291b3d78435e81`. This is a test-fixture correction, not a production runtime behavior change.
- Exact-head CI for the corrected commit must complete before the UID/GID integration correction can be called CI-verified. The earlier P93 run `44435513449` passed on the prior SHA but does not certify the corrected commit.


## Next implementation batch — dual-stack egress parser (2026-11-19)

- Opened Draft PR #29: `apaa-s09-c01-dual-stack-egress`, head currently `bc35fca37fdc311f2d3a0afa79f29f55d5fcb576`, base `feature/apaa-s09-c01-p01-browser-launch`.
- `core/browser_nftables.py` now recognizes both nftables `ip daddr` (IPv4) and `ip6 daddr` (IPv6) exact matches, checks address-family consistency and continues to require exact TCP protocol, proxy port, proxy address allowlist and output default-DROP.
- Added regression tests for mixed dual-stack allowlist acceptance, cross-family mismatch rejection, missing IPv6 proxy rule and unexpected extra IPv6 proxy rule.
- Initial exact-head APAA Security CI run `44437253176` failed before the parser tests in an existing live-browsing regression: the base branch returned 125 element records despite the 100-item cap. This was traced to missing Python-boundary cap enforcement on the PR base (the separate audit PR #28 already carries the same hardening).
- Carried the one-line fail-closed 100-element slice into PR #29 to make it safe against its actual base. Corrected-head CI run `44437445462` is in progress; no PASS is claimed yet.
- No host firewall, OCI worker, Browser/Worker enablement, merge or deployment.


### PR #29 dual-stack + whole-ruleset parser exact-head verification — 2026-11-19

- PR #29 current head: `e731a7715d2697508b249076facdd5d80012f1d1` (Draft/Open/Unmerged).
- Dual-stack exact-match parser changes accept only correctly family-matched IPv4/IPv6 destination expressions, exact TCP destination port and the expected proxy IP allowlist.
- Whole-ruleset validation now requires exactly one dedicated `inet filter` table and one `inet filter` output base chain with default DROP. Every rule must belong to that chain. Additional tables/chains/hooks, foreign-chain rules, sets, maps, elements, counters and unknown nftables object types are rejected.
- Adversarial tests cover unexpected IPv4/NAT table, extra forward/prerouting chains, foreign-chain rules, sets/maps/elements and masquerade expression.
- The 100-element cap is re-enforced at the Python browser-adapter boundary to protect this PR's selected base branch.
- Exact-head APAA Security CI run [44437843797](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/44437843797) on the exact head SHA `e731a7715d2697508b249076facdd5d80012f1d1`: **PASS**. All workflow steps passed, including syntax, P01 launch lifecycle, Chromium TLS positive/negative cases, live browsing with restricted local proxy, worker adapter and Linux host-inspector contracts, and the remaining security test suite.
- Earlier intermediate head `cc0b644e10071ca8631d2bc250cf06f4e34bf3f4` also passed run `44437819687`, but the final exact-head result above is the authoritative CI evidence.
- This is parser + CI verification only. It does not prove a real host's effective firewall, dual-stack leak resistance, OCI containment or browser worker production readiness. Disposable-host qualification and independent review remain mandatory.
- No merge, deployment, host provisioning or capability enablement was performed.

### OCI launch-plan contract mapping follow-up — 2026-11-19

A further source-to-contract review found that the inert OCI argv plan did not yet faithfully map all relevant WorkerLaunchSpec settings:
- It made the entire /tmp tree writable although the spec declared only job-scoped writable paths.
- It did not pass the approved proxy endpoint to the worker environment or constrain the worker entrypoint.

PR #29 follow-up changes:
- OCI plan now mounts only the exact declared job-scoped tmpfs paths with noexec,nosuid,nodev; the broad writable /tmp tmpfs was removed.
- It passes the explicit approved proxy endpoint to the worker, sets an empty NO_PROXY/no_proxy bypass list, and binds TMPDIR only when /tmp/job is declared.
- It pins the container entrypoint to /usr/local/bin/apaa-worker.
- Regression tests assert the exact mount, proxy environment, bypass policy and entrypoint.
- Commits: 4b3a1db4ec6dce36a89d9398ae9ba3ccd26627b1, bf931e91645313abbd706699302cb1c5623e55fc, 7ad00c57f60d33536fbf4224053f273a05bdb640.
- Fresh exact-head APAA Security CI for latest head 7ad00c57f60d33536fbf4224053f273a05bdb640 is pending at this update. The previous exact-head CI pass 44437843797 on e731a7715d2697508b249076facdd5d80012f1d1 does not certify these newer OCI mapping changes.
- This remains an inert argv-plan change; it does not provision or execute a container. The fixed worker entrypoint/image contract must be validated against the actual reviewed worker image before any real host qualification.