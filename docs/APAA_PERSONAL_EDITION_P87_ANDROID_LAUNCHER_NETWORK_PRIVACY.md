# APAA Personal Edition P87 — Android Launcher Network & Privacy Defaults

**Status:** Implementation committed; exact-head CI pending.
**Target:** Existing Android Termux + same-device browser runtime. This checkpoint does not create or claim a native APK.

## Changes

- The Android launcher explicitly binds Streamlit to `127.0.0.1`; it never exposes the Owner runtime on LAN or public interfaces.
- Cross-origin protection (`server.enableCORS`) and Streamlit XSRF protection are explicitly enabled rather than relying on framework defaults.
- Streamlit usage-statistics telemetry is explicitly disabled.
- The launcher runs the P86 fail-closed preflight before starting Streamlit. The preflight validates the port, absolute private data directory, ownership/mode and Streamlit availability.
- A regression test pins these launcher security/privacy settings and rejects a wildcard network bind.

## Verification boundary

The new commit must pass the repository's exact-head P73 GitHub Actions workflow before P87 is marked CI-verified. CI does not replace physical Android A01–A12 acceptance.

## Not enabled / not claimed

- No LAN/public access, remote-control endpoint, background startup, boot persistence or Auto-Run.
- No APK, Play Store package, native AccessibilityService, device-wide control or notification/screen-capture permission.
- Browser/Worker execution remains disabled until an isolated worker and independently verified network-egress boundary are qualified.
- Payments, purchases, subscriptions, trading and money movement remain prohibited.

## Next Android gates

1. Exact-head CI PASS.
2. Owner-run Termux preflight and launch on the actual Android phone.
3. Verify browser access only from the same phone, Owner setup/login, lockout, logout and session expiry.
4. Verify private data directory and backup/restore on the device; do not share secrets or unencrypted backup archives.
5. Complete physical Android A01–A12 and record only redacted evidence.
