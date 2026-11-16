# APAA S09 C01 P32 — Android-First Bulk Qualification

**Status:** Android automated viewport matrix added; all four required workflows PASS on exact head `1ab06a3daf8c27f7d7a84c0869ce06aa4f366fe4`; physical Android qualification remains owner-operated and pending.  
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
| Android narrow-screen layout | Pixel profile smoke test plus new 5-viewport matrix | CI PASS on exact head; physical device pending |
| Plan review without execution | Existing Playwright Android-emulation test | CI PASS on exact head; physical device pending |
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

## 7. Exact verification rule

Exact-head verification completed for `1ab06a3daf8c27f7d7a84c0869ce06aa4f366fe4`. All four required workflows completed successfully:
- [Agent Foundation CI #1019](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43827566848) — PASS.
- [Python Demo CI #1094](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43827566820) — PASS.
- [P20 Rootless Podman Runtime Qualification #148](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43827566908) — PASS.
- [P23 Rootless Podman Executor Integration #130](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43827566850) — PASS.

The combined commit status endpoint returned no separate status entries; the four PR-triggered workflow runs above are the available exact-head evidence. These CI runs do not prove physical Android behavior or external real-host qualification. Physical Android remains pending until the owner-run checklist is completed and reviewed. PC physical testing remains optional.

**C01 stays OPEN / NOT COMPLETE. C02 must not start.**
