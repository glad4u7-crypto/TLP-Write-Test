# APAA S09 C01 P36 Part 08 — Android Primary + Optional PC Browser Verification

Status: AUTOMATED ANDROID/PC VIEWPORT SMOKE COVERAGE IMPLEMENTED; physical Android verification remains OPEN; physical PC verification is optional and conditional on owner choice.

## Android browser coverage

`tests/test_android_viewport_smoke.py` runs Chromium with the Playwright Pixel 7 device profile and checks:
- no page/body horizontal overflow;
- inputs remain readable (minimum 16px);
- primary controls retain touch-sized targets (minimum 44px);
- a user can prepare and review a plan without exposing an execution/Auto-Run control.

This is mobile viewport emulation, not a physical Android handset or native Android/Termux test.

## Optional PC browser coverage

`tests/test_pc_browser_smoke.py` runs Chromium at a 1440×960 desktop viewport and checks:
- no page/body horizontal overflow;
- the main APAA task interface renders;
- no execute, run-task, approve-action or Auto-Run control is exposed in the unauthenticated prototype smoke context.

This is desktop browser automation on a CI runner, not an owner-controlled physical PC/browser security assessment. PC is an optional future client; physical PC testing is required only before claiming PC-specific release readiness and must not block Android-only use.

## CI integration

The Agent Foundation workflow installs Playwright Chromium and runs both Android and PC smoke suites in the same browser-verification job. The full test suite also compiles all application, core, test and script modules.

## Security boundary

- Browser automation remains disabled in the product runtime.
- The tests do not enable browser/worker execution.
- Android remains a control-plane client; no claim is made that Termux is a hostile-code sandbox.
- Physical Android tests with real OIDC accounts, logout/revocation checks and browser storage inspection remain mandatory for Android release qualification.
- Physical PC tests are conditional on the owner choosing to use or qualify the optional PC client; they are not an Android release prerequisite.

The latest exact PR head must pass the automated Android/PC viewport job and all other required workflows. Emulation must never be reported as physical-device PASS.
