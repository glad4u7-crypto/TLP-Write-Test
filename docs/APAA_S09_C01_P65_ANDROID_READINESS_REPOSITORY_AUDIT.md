# APAA-S09-C01-P65 — Android readiness repository audit

**Checkpoint:** P65  
**Audit date:** 2026-11-16  
**Branch:** `feature/apaa-s09-c01-p16-oci-lifecycle`  
**Audited code/documentation head:** `200c9e11b08ff087103b70aa3daa3b8846f3469d`  
**PR:** #11 — Draft / Open / Unmerged  
**Disposition:** Repository-side Android readiness checks reviewed; physical Android acceptance remains BLOCKED pending owner-controlled test environment and device execution.

## 1. Findings confirmed from repository

- The current application is a Streamlit web prototype, not a native Android APK and not yet a fully autonomous browser/device-control agent.
- `app.py` applies the responsive presentation helper in `core/mobile_ui.py`, uses centered layout and starts with the sidebar collapsed.
- `core/mobile_ui.py` provides narrow-screen spacing, 44px minimum button targets, 16px form text, horizontally scrollable tabs and responsive wrapping.
- `tests/test_mobile_ui.py` checks the presentation contract and asserts that styling does not enable Auto-Run, paid APIs or task execution.
- `tests/test_android_viewport_smoke.py` runs Pixel 7 browser emulation, task-plan review flow and a viewport matrix including 320px, 360px, 393px, 412px and landscape 915px.
- These are useful automated browser/emulation checks, not physical-device evidence.

## 2. Exact CI evidence for audited head

For commit `200c9e11b08ff087103b70aa3daa3b8846f3469d`, all four PR-triggered workflows completed successfully:

| Workflow | Run | Result |
|---|---:|---|
| Agent Foundation CI | [#1200](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43894220691) | PASS |
| Python Demo CI | [#1289](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43894220698) | PASS |
| P20 Rootless Podman Runtime Qualification | [#329](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43894220671) | PASS |
| P23 Rootless Podman Executor Integration | [#311](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43894220736) | PASS |

Agent Foundation job inspection confirms successful completion of:
- Python dependency audit, compile and foundation tests;
- Android/desktop Chromium browser-emulation smoke tests;
- disposable Linux egress namespace qualification;
- disposable Linux live host-inspector qualification.

These are CI and disposable-runner results only. They do not qualify a real owner-controlled host, production sink-side network policy, physical Android device, physical protected signing key, independent durable anchor, live OIDC provider, or independent security review.

## 3. Deployment readiness review

The repository documentation reviewed for this checkpoint does not provide a known owner-approved HTTPS test deployment URL. Root-level checks found no `Dockerfile`, `render.yaml` or committed `.streamlit/config.toml` at the audited branch head. This is a repository inspection result, not proof that no deployment exists elsewhere.

Do not create or expose an unauthenticated public deployment as a workaround. Before physical acceptance, an owner-controlled non-production HTTPS instance must be provisioned with authentication enforced, private persistent database paths and secrets held only in the deployment's protected secret store. No credentials or secrets are to be committed.

## 4. Android-only owner acceptance still required

Use [P64 Android-only owner acceptance guide](APAA_S09_C01_P64_ANDROID_ONLY_OWNER_ACCEPTANCE.md) and [authenticated Android test setup runbook](APAA_S09_C01_AUTHENTICATED_ANDROID_TEST_SETUP.md).

Pending owner-operated evidence:
1. Physical Android Chrome A01–A12 checks, bound to the exact tested commit.
2. Two separately controlled OIDC test identities and live owner grant/revoke denial checks.
3. Private persistent test deployment, session expiry/logout/back-cache verification and redacted server-side authorization evidence.
4. Independent review of the evidence digest.

A PC/Windows physical device is not required for this Android-only delivery path. Browser emulation does not replace physical Android testing.

## 5. Safety and release disposition

- Auto-Run: OFF.
- Worker and Browser execution: DISABLED.
- Payment, purchase, checkout, trading and money movement: prohibited.
- Paid provider/API: disabled; no API key or paid service required.
- Merge and deployment: not authorized; PR #11 remains Draft/Open/Unmerged.
- C01: OPEN / NOT COMPLETE until all mandatory external gates G1–G10 are evidenced and independently approved.
- C02: NOT STARTED.

## 6. Next action

Repository-side Android responsive implementation and CI verification are already present and pass on the audited P64 head. The next meaningful gate is not more CSS or a PC setup: it is an owner-approved private HTTPS test environment followed by physical Android and live two-account OIDC acceptance. Until that environment exists, record those checks as BLOCKED; do not claim completion.
