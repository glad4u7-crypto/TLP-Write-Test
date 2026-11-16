# APAA S09 C01 P32 — Android-First Bulk Qualification

**Status:** Android automated viewport matrix added; all four required workflows PASS on latest verified exact head `6f8cc1e32e6464983dc9468487be2ed51c4f4791`; physical Android qualification remains owner-operated and pending.  
**PC:** Optional. No physical PC test is required for Android-only qualification.  
**Checkpoint:** `APAA-S09-C01-P32-ANDROID-FIRST-BULK-QUALIFICATION`

## 1. Scope and safety locks

This checkpoint advances Android as the primary owner interface. It does not enable browser automation, workers, Auto-Run, payments, purchases, paid providers, host mutation, firewall changes, merge, deployment or C02. The existing PR remains Draft/Open/Unmerged.

PC remains a supported future client direction, but physical PC testing is conditional on the owner later choosing to use or qualify PC. It must not block Android progress.

## 2. Android automated coverage added

Extended `tests/test_android_viewport_smoke.py` with a responsive viewport matrix:

- 320×720 narrow handset viewport
- 360×800 handset viewport
- 393×852 handset viewport
- 412×915 Pixel-class handset viewport
- 915×412 landscape handset viewport

For each viewport, the test checks:
- the main task interface renders;
- document and body do not overflow horizontally;
- input and textarea text remains at least 16 CSS pixels;
- primary and form-submit controls retain at least 44×44 CSS-pixel targets.

Existing Android emulation tests also check the Pixel 7 profile, plan preparation/review without task execution, readable inputs and touch-sized controls.

**Evidence boundary:** Playwright Chromium mobile emulation is automated browser evidence, not a physical Android handset, native APK, Android permission broker, Termux isolation, or real mobile-network test.

## 3. Existing access/session evidence

The repository already contains deterministic tests for:
- owner identity isolation by OIDC issuer + subject;
- session state clearing on identity switch and logout;
- invalidation of old approval receipts after session change;
- read-grant revocation observed by an existing ACL reader and a reconstructed reader;
- append-only grant/revoke audit event ordering;
- checkpoint owner/tenant authorization and resource-boundary audits.

These are code-level regression tests. Review of `app.py`, `core/session_security.py`, `core/streamlit_auth.py`, `tests/test_session_security.py`, `tests/test_streamlit_auth.py` and `tests/test_project_access_session_regression.py` confirms the current implementation has an optional OIDC enforcement switch, fails closed when authentication is required but configuration is missing, clears identity-bound state at logout/identity transitions, and invalidates stale session approval receipts. The ACL regression tests exercise grant/revoke against both an existing reader and a reconstructed reader. They are not live OIDC tests with two real accounts, nor physical browser cookie/storage/revocation evidence.

## 4. Physical Android operator checklist

Run only when the owner is ready, using the Android phone and an owner-controlled, non-production test account/environment. Do not expose the unauthenticated local prototype publicly.

Record PASS only with a dated report and redacted evidence. Never capture or commit passwords, access tokens, cookies, private keys, personal data or raw session secrets.

1. Open the approved test instance in Android Chrome; record Android version, Chrome version and viewport.
2. Check portrait and landscape layout, scrolling, keyboard overlap, text readability and touch targets.
3. If a properly authenticated OIDC test deployment is available, sign in as the owner and verify the displayed identity.
4. Sign out; confirm identity-bound drafts and approval/session capabilities are cleared.
5. Sign in again and verify a new session cannot reuse a prior session's approval receipt.
6. If two controlled OIDC accounts and an owner-authorized test project are available, grant read access, verify the allowed read, revoke it, then verify denial from the already-open second session and after a fresh sign-in.
7. Inspect browser storage at a safe test boundary; verify secrets, approval receipts and private evidence are not stored in local storage, service-worker caches or URL parameters.
8. Test offline/online reconnect and background/resume behavior; confirm the UI does not claim a task ran when it did not.
9. Record unsupported or unavailable steps as BLOCKED with the missing prerequisite; do not substitute mocks or emulation for physical evidence.

If no authenticated test deployment or two controlled OIDC accounts are available, do not attempt public exposure or improvise credentials. Keep the affected live-auth gates BLOCKED.

## 5. Current qualification ledger

| Area | Evidence now available | Honest status |
|---|---|---|
| Android narrow-screen layout | Pixel profile smoke test plus new 5-viewport matrix | CI PASS on latest verified exact head; physical device pending |
| Plan review without execution | Existing Playwright Android-emulation test | CI PASS on latest verified exact head; physical device pending |
| Owner/session identity isolation | Deterministic unit/regression tests and app integration review | Code coverage exists; live OIDC pending |
| Grant/revoke enforcement | Existing ACL and reconstructed-reader tests | Code coverage exists; live two-account Android E2E pending |
| Android keyboard, lifecycle and reconnect | Operator checklist only | Physical phone test pending |
| Native Android APK / PWA | Architecture plan only | Not implemented/qualified |
| Android local hostile-code isolation | Not supported by Termux assumption | Not qualified; separate Linux worker gate remains |
| PC physical device | Not required for Android-only path | Optional |

## 6. Dependencies that cannot be honestly cleared by Android emulation

The Android phone can validate the Android client experience and live owner/session workflows when a secured test deployment exists. It cannot replace:
- owner-approved disposable Linux host qualification;
- protected host signer and out-of-band trust provisioning;
- independently durable anti-rollback storage;
- sink-side network enforcement and real worker/proxy bypass testing;
- independent security reviewer identity and approval.

These remain separate external gates. Do not mark them PASS based on Android, mocks or GitHub CI.

## 7. Latest exact-head CI verification

Latest verified exact PR head: `6f8cc1e32e6464983dc9468487be2ed51c4f4791`. All four required PR-triggered workflows and their listed jobs completed successfully on this exact head:

- [Agent Foundation CI #1022](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43828000688) — **PASS**. Foundation test job, dependency audit/compile, disposable Linux egress namespace qualification and Android/desktop Chromium browser smoke tests all passed.
- [Python Demo CI #1097](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43828000755) — **PASS**. Test suite and demo smoke check passed.
- [P20 Rootless Podman Runtime Qualification #151](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43828000804) — **PASS**. Disposable rootless Podman CREATE/INSPECT/START/STOP/REMOVE by immutable ID and no-orphan check passed.
- [P23 Rootless Podman Executor Integration #133](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43828000800) — **PASS**. APAA executor integration against disposable rootless Podman, attestation gate and cleanup checks passed.

The Android/desktop browser job is Chromium/Playwright emulation, not physical-device evidence. Disposable Linux/Podman CI is not the owner's production or independently administered host and does not prove production key custody, durable anti-rollback, or sink-side enforcement. These results do not satisfy the external real-host qualification gates. The documentation updates that record these results are documentation-only; no new CI result is implied for those later documentation commits.

Physical Android remains pending until the owner-run checklist is completed and reviewed. PC physical testing remains optional.

**C01 stays OPEN / NOT COMPLETE. C02 must not start.**


## 8. Exact-head CI re-verification (2026-11-16)

The PR head `65e130cc6b923cdbba1fe741e058bcf0120bd366` completed all four required PR-triggered workflows successfully:

- [Agent Foundation CI #1024](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43828374664) — PASS. The Android and PC Chromium browser verification job passed, including Playwright mobile viewport smoke coverage; disposable Linux egress namespace qualification and the full foundation test job also passed.
- [Python Demo CI #1099](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43828374673) — PASS.
- [P20 Rootless Podman Runtime Qualification #153](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43828374682) — PASS. Disposable rootless Podman lifecycle completed CREATE/INSPECT/START/STOP/REMOVE and orphan check.
- [P23 Rootless Podman Executor Integration #135](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43828374665) — PASS. APAA executor integration against disposable rootless Podman completed successfully.

This clears the earlier automated exact-head CI-pending item for the inspected head. It does not clear physical Android login/logout, real OIDC multi-user access/revocation, Android browser storage/lifecycle, native APK, real-host OCI/network, protected signer, independent anti-rollback or independent reviewer gates. CI is not physical-device or production-host evidence.

**Qualification status:** Android automated browser-emulation coverage PASS; physical Android qualification OPEN. PC physical qualification remains optional. C01 remains OPEN / NOT COMPLETE; PR #11 remains Draft/Open/Unmerged; C02 must not start.

## 9. Later repository-state reconciliation (2026-11-16)

This addendum supersedes the older “latest verified exact head” pointer above where the branch has advanced. It does not upgrade any physical-device or real-host gate.

- P42 owner-controlled read-only grant/revoke UI was inspected in code at `3d8c166628b5c7040d706d963ca69d12283aef7f`. The UI is bound to a server-validated OIDC Principal and configured trusted issuer allowlist; directory identities are private by default; grants require explicit owner confirmation; revocation is separately confirmed and persisted. The grant is limited to project metadata read access. This is implementation review, not live two-account OIDC or physical Android E2E.
- The P31 evidence inventory refresh was committed at `e8fe7e06cc2cd4945c8040b7e5e2e906e7f67fa6`. All four required workflows passed on that exact PR head:
  - [Agent Foundation CI #1055](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43834897418) — PASS; Android/PC Chromium emulation and disposable Linux egress namespace jobs also passed.
  - [Python Demo CI #1130](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43834897840) — PASS.
  - [P20 Rootless Podman Runtime Qualification #184](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43834897467) — PASS.
  - [P23 Rootless Podman Executor Integration #166](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43834897632) — PASS.
- These later results verify repository code and disposable CI only. They do not establish physical Android behavior, live OIDC with two real accounts, browser storage/lifecycle behavior on the handset, native APK/PWA readiness, owner-host Linux qualification, protected signer/key custody, independent durable anti-rollback, sink-side worker/proxy enforcement, or independent reviewer approval.

### Current Android-first disposition

| Gate | Current disposition |
|---|---|
| Android responsive viewport automation | PASS on the recorded exact CI heads; emulation only |
| Owner-controlled grant/revoke UI implementation | Implemented and code-reviewed; live Android/OIDC E2E pending |
| Physical Android login/logout, session switch and storage checks | BLOCKED / owner-operated test deployment and device evidence not supplied |
| Physical Android grant/revoke with two real OIDC accounts | BLOCKED / no live two-account evidence |
| Native Android APK/PWA | Not implemented/qualified |
| Physical PC | Optional; not a prerequisite for Android-first qualification |
| Real Linux host, trust, signer, anti-rollback and sink-side network gates | Separate mandatory C01 blockers; Android testing cannot clear them |

Do not expose an unauthenticated prototype publicly or improvise OIDC credentials. If no secured test deployment and two controlled accounts exist, preserve the live-auth gates as BLOCKED. No secrets or raw device/session data belong in the repository.

**C01 remains OPEN / NOT COMPLETE; C02 remains NOT STARTED.** PR #11 must remain Draft/Open/Unmerged. Auto-Run OFF; browser/worker disabled; no paid services, host/firewall mutation, merge or deployment.
