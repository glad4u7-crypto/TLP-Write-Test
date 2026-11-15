# APAA-S09-C01-P07 — Android Runtime Compatibility Gate

**Status:** Android/Termux detection and fail-closed browser-launch gate implemented. Physical-device compatibility is not qualified.

## Runtime behavior

- `core/runtime_support.py` identifies Android using `sys.platform == "android"` or Android environment markers.
- It identifies Termux conservatively from Android markers plus Termux path markers.
- It performs no shell commands, package installs, browser downloads, permission changes or network calls.
- `PlaywrightBrowserLauncher.launch()` checks this gate before importing/starting Playwright. Android/Termux browser launch is rejected with an explicit explanation.
- Non-Android hosts are not automatically certified: Playwright and a compatible browser binary still require local validation.

## What remains usable on Android

Pure-Python planning, policy, validation, data processing and tests can be developed in a Python environment where dependencies are available. This gate only blocks the optional Playwright browser-launch path; it does not claim the entire APAA application has been tested on Android.

## Device qualification plan (not executed)

1. Record Android version, device ABI, Python version and Termux/Python distribution.
2. Verify Python-only modules and unit tests without installing browser binaries.
3. In a disposable test environment, separately evaluate a supported browser automation runtime and its sandbox/network controls.
4. Require independent security review before enabling browser launch.
5. Do not use personal browser profiles, credentials, production websites or payment flows during qualification.

## Safety and verification

- No Android settings, permissions, firewall, proxy, packages, browser binaries or device files were changed.
- No live website, login, payment, purchase, deployment, paid API or Auto-Run action was performed.
- Tests were authored; no test pass is claimed until executed on the exact branch head.
- Android browser automation remains disabled by default pending physical-device qualification.
