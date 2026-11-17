# APAA-S09-C01-P07 — Android Runtime Compatibility Gate

**Status:** Android/Termux detection and fail-closed launch gates implemented. No Android app module or physical-device qualification exists yet.

## Runtime behavior

- `core/runtime_support.py` identifies Android using `sys.platform == "android"` or Android environment markers.
- It identifies Termux conservatively from Android markers plus Termux path markers.
- It performs no shell commands, package installs, browser downloads, permission changes or network calls.
- `PlaywrightBrowserLauncher.launch()` checks the Android gate, and host-local launch is disabled by default on every platform. A local test-only opt-in is not a production browser path.
- The signed OCI inspector gate alone does not place a host process inside the worker namespace; the legacy host Playwright callback is disabled.
- Non-Android hosts are not automatically certified: a real `IsolatedWorkerBackend` must start Chromium inside the attested OCI worker and pass host enforcement tests.

## What remains usable on Android

Pure-Python planning, policy, validation, data processing and tests can be developed in a Python environment where dependencies are available. Android can run pure-Python planning, policy and data-processing components where dependencies are available. This does not establish secure browser automation, device control or full application compatibility.

## Device qualification plan (not executed)

1. Record Android version, device ABI, Python version and Termux/Python distribution.
2. Verify Python-only modules and unit tests without installing browser binaries.
3. Build a dedicated Android application module and implement a user-consented `VpnService`/worker transport that prevents direct-network bypass for APAA browser traffic.
4. Qualify IPv4, IPv6, DNS, UDP/QUIC, proxy outage, process death, VPN revocation and app restart on a physical device.
5. Require independent security review before enabling browser launch.
6. Do not use personal browser profiles, credentials, production websites or payment flows during qualification.

## Safety and verification

- No Android settings, permissions, firewall, proxy, packages, browser binaries or device files were changed.
- No live website, login, payment, purchase, deployment, paid API or Auto-Run action was performed.
- Tests were authored; no test pass is claimed until executed on the exact branch head.
- Android browser automation remains disabled by default pending a real VpnService implementation and physical-device qualification.
