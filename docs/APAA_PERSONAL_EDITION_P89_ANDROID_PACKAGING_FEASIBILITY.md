# APAA Personal Edition P89 — Android App Packaging Feasibility & Delivery Gate

**Checkpoint:** P89 — Android-first delivery decision  
**Status:** Feasibility audit recorded; no APK built or claimed.  
**Repository:** `glad4u7-crypto/TLP-Write-Test`  
**Branch:** `apaa-personal-edition-foundation`

## 1. Current verified baseline

- APAA Personal Edition is a Python + Streamlit application.
- Android launch currently uses Termux and a same-device browser at `127.0.0.1`.
- The launcher binds loopback only, runs a fail-closed preflight and keeps the data directory private.
- Encrypted backup/restore is implemented and CI verified in P88.
- The repository has no native Android Gradle project, Android manifest, APK signing configuration or Android application module at this checkpoint.
- Browser viewport tests are Chromium emulation. They do not qualify Termux compatibility, Android lifecycle behavior or a native APK.

## 2. Packaging decision

Do **not** wrap the current Streamlit page in a thin WebView APK and label it a native APAA app. That would still depend on a separately running Python/Streamlit server, would not solve Android process lifecycle or secure local IPC, and could create a misleading installable shell around an unqualified runtime.

Do **not** attempt to embed the full Streamlit server into an APK as a quick packaging step. The current repository does not provide a supported Android Python runtime/build pipeline for its complete dependency graph.

The Android-first product architecture already defines a responsive installable web experience as the first client stage, with a native Android shell only after the core client/API boundary and device-permission requirements are ready. P89 follows that architecture.

## 3. Android runtime doctor (new)

A read-only diagnostic command is now available for the Owner to run in the existing Termux checkout:

```sh
python scripts/apaa_android_doctor.py
```

It reports Python implementation/version, platform and CPU architecture, a Termux-detection boolean, Streamlit and cryptography versions, AES-GCM/scrypt availability, loopback socket-bind availability and the current Git commit. It does not print environment variables or filesystem paths, inspect personal files/browser profiles, read credentials, create/change files, or make network connections. It briefly binds a temporary socket to `127.0.0.1` only.

Exit code 0 means the basic runtime dependencies and loopback bind are present; exit code 2 means review the reported missing requirements. This is not a substitute for launching APAA or completing physical A01–A12 acceptance.

## 4. Recommended delivery sequence

### P89-A — Android browser experience hardening
- Complete owner-run physical Android acceptance A01–A12 using the existing runbook.
- Record actual device model, Android version, Termux/Python versions and exact commit.
- Test startup, background/foreground, screen rotation, keyboard, reconnect, logout, session expiry and encrypted backup/restore.
- Keep loopback binding and Auto-Run OFF.

### P89-B — Installable web app assessment
- First establish an explicit authentication/session and origin model for local and future remote modes.
- Define a strict service-worker policy: never cache owner pages, API responses, session state, backups, approval receipts or private project data.
- Add a versioned web manifest and install/update behavior only after cache, CSRF, origin and logout/revocation behavior are tested.
- Do not claim PWA readiness until real Android Chrome installation and update tests pass.

### P89-C — Native Android client (separate module)
- Introduce a Kotlin/Android application module only after a stable, authenticated, transport-neutral APAA control API exists.
- Use Android device credential/biometric re-authentication only as an additional Owner-presence gate, never as a replacement for server-side authorization.
- Keep approval receipts and policy decisions server-side. Use short-lived, task-scoped capabilities.
- Request Android permissions just-in-time, explain each permission, and provide revocation.
- Implement foreground/background lifecycle, process death recovery, network-loss handling and accessibility before any execution feature.
- Sign release artifacts with a protected release key; document reproducible build inputs and update/rollback policy.

## 5. Non-negotiable safety boundary

- No public/LAN listener, tunnel or remote exposure.
- Browser/Worker execution stays disabled until host-level egress isolation and all approval gates are independently qualified.
- Auto-Run stays OFF; consequential actions remain Ask First.
- No payments, purchases, checkout, trading or money movement.
- No hidden accessibility-service use, screen capture, background surveillance or silent device control.
- No paid build/hosting service or external account connection by default.

## 6. Exit criteria

P89 is not complete until:
1. The physical Android A01–A12 runbook is executed and evidence is recorded.
2. A selected client packaging path is supported by the existing architecture and security model.
3. Android lifecycle, reconnect, local storage, update and recovery tests pass on the Owner's actual device.
4. No test bypasses loopback, authentication, approval or privacy controls.
5. Any APK is reproducibly built, signed and independently verified before distribution.

## 7. Current truthful status

**Available now:** Termux + loopback browser launch path, owner authentication, private local storage, encrypted backup/restore, CI-tested responsive browser UI.

**Not available/verified:** Native APK, installable PWA, physical Android A01–A12 acceptance, background service, Android accessibility automation or production remote worker.

P89 prioritizes a fast and safe Android experience without creating an APK that merely hides an unqualified server process.
