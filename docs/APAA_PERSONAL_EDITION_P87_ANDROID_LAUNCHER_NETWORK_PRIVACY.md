# APAA Personal Edition P87 — Android Launcher Network & Privacy Defaults

**Status:** Implementation committed; exact-head CI PASS on `fdea40778744403e83500f950d99f4eae6b5be3a` (run [#494](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/44039705644)). Follow-up P88 backup encryption is tracked separately.
**Target:** Existing Android Termux + same-device browser runtime. This checkpoint does not create or claim a native APK.

## Changes

- The Android launcher explicitly binds Streamlit to `127.0.0.1`; it never exposes the Owner runtime on LAN or public interfaces.
- Cross-origin protection (`server.enableCORS`) and Streamlit XSRF protection are explicitly enabled rather than relying on framework defaults.
- Streamlit usage-statistics telemetry is explicitly disabled.
- The launcher runs the P86 fail-closed preflight before starting Streamlit. The preflight validates the port, absolute private data directory, ownership/mode and Streamlit availability.
- A regression test pins these launcher security/privacy settings and rejects a wildcard network bind.

## Verification boundary

P87 exact-head P73 Verification run #494 passed: Python suite, compilation, dependency audit and responsive browser smoke. CI does not replace physical Android A01–A12 acceptance.

## Not enabled / not claimed

- No LAN/public access, remote-control endpoint, background startup, boot persistence or Auto-Run.
- No APK, Play Store package, native AccessibilityService, device-wide control or notification/screen-capture permission.
- Browser/Worker execution remains disabled until an isolated worker and independently verified network-egress boundary are qualified.
- Payments, purchases, subscriptions, trading and money movement remain prohibited.

## Next Android gates

1. Exact-head CI PASS.
2. Owner-run Termux preflight and launch on the actual Android phone.
3. Verify browser access only from the same phone, Owner setup/login, lockout, logout and session expiry.
4. Verify private data directory and backup/restore on the device; do not share secrets or legacy unencrypted backup archives. New backups are encrypted under P88.
5. Complete physical Android A01–A12 and record only redacted evidence.
