# APAA BCS-06 — Android Compatibility

## Decision

Android is a supported **local Owner-interface host**, not a qualified browser-worker host.

- Execution path: Android + Termux, same-phone local web application.
- Owner interface: Android Chrome at `http://127.0.0.1:<configured-port>`.
- Bind address: loopback only (`127.0.0.1`, `::1`, or `localhost`). Never bind the Owner interface to `0.0.0.0` or a LAN address.
- Authentication: the current app uses Streamlit OIDC when `[apaa].require_auth = true` and `[auth]` is configured. Unauthenticated local prototype mode is not an Owner-secure mode and must not be exposed or treated as accepted. No local Owner-passphrase feature is claimed by this milestone. Every protected mutation continues to require explicit Owner confirmation.
- Browser runtime: Android/Termux browser-worker launch remains disabled. Browser work, when separately qualified, runs on an attested isolated Linux worker; Chrome on the phone is the control surface, not the automation worker.
- Native APK: deferred. No Android accessibility service, device-control bridge, or cross-app automation is implied.
- No payment, purchase, checkout, trading, money movement, arbitrary shell, public signup, or Auto-Run.

## Feasibility matrix

| Capability | Disposition | Evidence / limitation |
|---|---|---|
| Python application and local HTTP UI in Termux | Feasible in principle | Termux provides Android-native packages; actual phone installation and launch still require physical acceptance |
| Owner UI in Android Chrome | Supported design | Same-device loopback URL; responsive UI and browser smoke tests exist, but real handset test is pending |
| Owner login, approval, history | Existing application controls | Must be rechecked on physical Android; no bypass is introduced |
| Chromium/Playwright browser worker inside Termux | Unsupported / fail closed | No qualified Android worker image, sandbox, host attestation or network isolation evidence |
| Isolated Linux browser worker | Separate qualification track | OCI/Linux isolation and real-host qualification remain outside BCS-06 |
| Android background persistence | Limited | Android may stop background processes; use foreground session and explicit restart/recovery procedure |
| Native APK / accessibility control | Deferred | Not part of this compatibility milestone |

## Runtime selection

`core/android_compatibility.py` provides a side-effect-free compatibility assessment. It does not install packages, launch processes, start a server, or authorize browser dispatch. Android/Termux is allowed to host the local Owner UI by design, while browser-worker support remains false. `core/runtime_support.py` continues to fail closed for browser launch on Android.

## Owner control from Android Chrome

1. Start the APAA application manually in Termux using the documented local launcher.
2. Bind only to `127.0.0.1` (or IPv6 loopback where explicitly configured).
3. Open the exact local URL in Chrome on the same phone.
4. Authenticate through the configured OIDC provider as the Owner.
5. Review each proposed action and explicitly approve or cancel it.
6. Confirm action history and audit integrity after the test.
7. Stop the app from Termux. If Android terminates it, restart manually and verify durable state recovery.

Do not expose the port to Wi-Fi/LAN, use a tunnel, or treat a Chrome tab as proof that an isolated worker exists.

## Supported browser runtime

BCS-06 does **not** qualify a browser automation runtime on Android. Android Chrome is a user-operated Owner console. The current Android/Termux browser launch guard remains in force. A Linux browser worker must independently pass its OCI, host-attestation, network-egress, TLS, crash/orphan and security-review gates before dispatch can be enabled.

## Physical Android acceptance matrix (Owner-operated)

Before manual Chrome checks, run `python scripts/android_device_acceptance.py` from the repository root in Termux. This non-invasive diagnostic reports Android/Termux detection, Python version, non-root status, presence of OIDC-required Owner configuration (without printing secrets), and a loopback TCP self-test. It does not test Chrome itself and cannot replace the manual acceptance matrix. It exits non-zero if any automated diagnostic fails.

All checks below require the actual target handset. Desktop emulation, CI viewport tests, or a Linux shell are not substitutes.

| ID | Test | Expected result |
|---|---|---|
| A01 | Install supported Termux distribution and update packages | Installation succeeds; record app/package versions |
| A01a | Run `python scripts/android_device_acceptance.py` | D01–D06 diagnostics all PASS; retain redacted output |
| A02 | Start APAA from Termux | App starts without root |
| A03 | Verify bind address | Listener is loopback only |
| A04 | Open local URL in Android Chrome | Owner login page loads on same phone |
| A05 | Responsive layout / portrait and landscape | No clipped critical controls; touch targets usable |
| A06 | Owner login and logout | Correct passphrase required; logout invalidates session |
| A07 | Idle/absolute session expiry | Expired session requires re-login |
| A08 | Owner approval flow | Approve and cancel both behave correctly; no implicit approval |
| A09 | Action history and audit verification | Recent history visible; tampering/failure remains fail-closed |
| A10 | Restart app / terminate and relaunch | Persistent Owner identity, project and checkpoints recover |
| A11 | Attempt non-loopback bind and Android browser-worker launch | Non-loopback rejected; browser-worker launch blocked |
| A12 | Stop app and inspect data permissions | Clean stop; private app data remains private; no secrets in shared storage/logs |

### Evidence required

Record only redacted facts: handset model, Android version, Termux source/version, Python version, test ID, PASS/FAIL, and sanitized error category. Never upload passphrases, cookies, tokens, session IDs, private databases, or unredacted logs.

## Acceptance status

- Automated contract tests: added in `tests/test_android_compatibility.py` and `tests/test_android_owner_ui.py`; exact-head CI must pass.\n- Android launcher: `scripts/android_owner_ui.py` requires OIDC auth and binds Streamlit to `127.0.0.1`.
- Existing Android/Desktop browser viewport tests: useful UI regression evidence only.
- Physical A01–A12: **NOT RUN** until the Owner performs them on the actual Android phone. The diagnostic script is ready but has not been run on the handset.
- Android browser-worker runtime: **NOT SUPPORTED / DISABLED**.
- Overall BCS-06: implementation and automated contract scope can be completed in CI, but final physical-device acceptance remains **PENDING OWNER TEST**. Do not report the handset as accepted without A01–A12 evidence.

## Safety / release state

Draft only. No merge, deployment, public exposure, Auto-Run, browser dispatch, payment, purchase, trading, or money movement. No device mutation is performed by the assessment module.
