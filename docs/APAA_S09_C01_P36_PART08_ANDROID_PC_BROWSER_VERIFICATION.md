# APAA S09 C01 P36 Part 08 — Android + PC Browser Verification

Status: AUTOMATED BROWSER SMOKE COVERAGE IMPLEMENTED; physical-device verification remains OPEN.

## Android browser coverage

`tests/test_android_viewport_smoke.py` runs Chromium with the Playwright Pixel 7 device profile and checks:
- no page/body horizontal overflow;
- inputs remain readable (minimum 16px);
- primary controls retain touch-sized targets (minimum 44px);
- a user can prepare and review a plan without exposing an execution/Auto-Run control.

This is mobile viewport emulation, not a physical Android handset or native Android/Termux test.

## PC browser coverage

`tests/test_pc_browser_smoke.py` runs Chromium at a 1440×960 desktop viewport and checks:
- no page/body horizontal overflow;
- the main APAA task interface renders;
- no execute, run-task, approve-action or Auto-Run control is exposed in the unauthenticated prototype smoke context.

This is desktop browser automation on a CI runner, not an owner-controlled physical PC/browser security assessment.

## CI integration

The Agent Foundation workflow installs Playwright Chromium and runs both Android and PC smoke suites in the same browser-verification job. The full test suite also compiles all application, core, test and script modules.

## Security boundary

- Browser automation remains disabled in the product runtime.
- The tests do not enable browser/worker execution.
- Android remains a control-plane client; no claim is made that Termux is a hostile-code sandbox.
- Physical Android and PC tests with real OIDC accounts, logout/revocation checks and browser storage inspection remain mandatory external evidence before release qualification.

The latest exact PR head must pass the Android/PC browser job and all other required workflows. Emulation must never be reported as physical-device PASS.
