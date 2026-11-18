# APAA Android Owner-Operated Read-Only Preflight

**Scope:** Device identification and Python-runtime preflight only.  
**Status:** NOT RUN — requires the Owner to run commands on the physical Android device.  
**Related gate:** S09-C01-P07.  
**Important:** This does not qualify Chromium, Playwright, browser networking, or production APAA.

## Safety boundary

- Do not install packages or browser binaries for this test.
- Do not change Android permissions, firewall, VPN, proxy, DNS, battery, developer, accessibility, or security settings.
- Do not grant Accessibility, screen-capture, device-admin, root, or unknown-app permissions.
- Do not use a personal browser profile, cookies, credentials, production account, or real website.
- Do not paste passphrases, tokens, cookies, device serials, IMEI, account identifiers, private logs, or screenshots containing personal data.
- If Termux is not already installed, stop; do not install it just for this preflight.

## Step 1 — Confirm environment

If Termux is already installed, open it and run:

```sh
printf 'Android release: '; getprop ro.build.version.release
printf 'Device ABI: '; getprop ro.product.cpu.abi
printf 'Termux prefix: '; printf '%s\n' "$PREFIX"
python --version
python -c 'import platform,sys; print("sys.platform:", sys.platform); print("machine:", platform.machine()); print("python:", sys.version.split()[0])'
```

Return only these non-sensitive fields:
- Android release
- ABI
- Whether Termux is already installed
- Python version
- `sys.platform`
- `platform.machine()`

Do not return the full environment, `getprop` dump, HOME path, usernames, device model serials, or app data.

## Step 2 — Run the repository's pure-Python runtime gate (only if the repository is already present)

From the repository root, run:

```sh
python -c 'from core.runtime_support import assess_runtime; r=assess_runtime(); print({"platform":r.platform,"is_android":r.is_android,"is_termux":r.is_termux,"browser_launch_allowed":r.browser_launch_allowed,"reason":r.reason})'
```

Expected safe result on Android: `is_android=True`, `browser_launch_allowed=False`. This is an expected fail-closed result, not a failed test.

If the repository and dependencies are already available, optionally run only the pure-Python gate tests:

```sh
python -m pytest -q tests/test_runtime_support.py
```

If pytest is not already installed, stop. Do not install it for this step.

## Step 3 — Stop conditions

Stop immediately if:
- Termux is absent;
- Python is unavailable;
- the repository is not already available;
- a command requests elevated permissions;
- the test proposes downloading a browser, opening a network listener, changing routes/firewall/proxy, or accessing user data.

Do not try to bypass `require_browser_runtime()`. Current repository policy intentionally blocks Playwright launch on Android/Termux.

## Evidence to report

Use this minimal template and replace only values actually observed:

- Android release:
- ABI:
- Termux already installed: yes/no
- Python version:
- sys.platform:
- platform.machine():
- Runtime gate output: PASS / expected Android fail-closed / not run
- pytest gate: PASS / FAIL / not installed / not run

**No browser launch is requested or authorized by this preflight.** A separate architecture decision and independent security qualification are required before an Android browser runtime can be evaluated.
