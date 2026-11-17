# APAA-S09-C01-P71 — Android acceptance audit and closure boundary

**Date:** 2026-11-17  
**Branch:** `apaa-s09-c01-action-audit-remediation-01`  
**Audited head before this report:** `80f9c082c1bda20397e821d1b2a072bc8b3f4d60`  
**PR:** #12 — Draft / Open / Unmerged  
**Scope:** Workstream A — Android-first client and owner acceptance  
**Disposition:** Repository-side Android responsive UI and emulated browser checks are implemented; physical Android acceptance and authenticated private deployment remain BLOCKED. This checkpoint does not claim Workstream A complete.

## 1. Audit result

The repository contains a Streamlit responsive web prototype, not a native Android APK and not yet an installable PWA. The product architecture explicitly sequences an authenticated, HTTPS-protected PWA shell before a native Android companion. No native Android project/build configuration was found in the reviewed Android delivery documents and files.

Existing Android-oriented repository implementation:
- `core/mobile_ui.py`: responsive narrow-screen CSS, 44px minimum button height, 16px form text, wrapping and horizontal tab scrolling.
- `tests/test_mobile_ui.py`: verifies responsive styling and ensures the CSS does not enable Auto-Run or external paid execution.
- `tests/test_android_viewport_smoke.py`: Playwright Chromium emulation for Pixel 7, narrow viewports (320/360/393/412px), landscape viewport, touch target/readability checks, and plan-only interaction.
- `scripts/preflight_android_deployment.py` plus `tests/test_android_deployment_preflight.py`: read-only fail-closed deployment configuration checks.

These checks establish repository/emulation behavior only. They do not establish physical-device compatibility, native Android functionality, TLS, OIDC, real session revocation, or owner-host persistence.

## 2. A01–A12 physical acceptance matrix

All twelve physical checks remain **BLOCKED / NOT RUN** because no owner-approved private HTTPS deployment and no physical-device test session were supplied to this repository workflow. Do not convert emulation to physical PASS.

| Test | Physical acceptance | Reason |
|---|---|---|
| A01 HTTPS origin and certificate | BLOCKED | No approved private test URL |
| A02 portrait layout and no horizontal page scroll | BLOCKED | Requires physical Android browser |
| A03 rotate landscape/portrait | BLOCKED | Requires physical Android browser |
| A04 keyboard/input visibility | BLOCKED | Requires physical keyboard behavior |
| A05 touch interaction | BLOCKED | Requires physical touch input |
| A06 prepare plan without execution | BLOCKED | Requires physical device against approved deployment |
| A07 browser back/forward and session integrity | BLOCKED | Requires live authenticated session |
| A08 lock/unlock and session expiry | BLOCKED | Requires physical device and configured session policy |
| A09 logout/back-cache denial | BLOCKED | Requires live server-side authentication |
| A10 owner re-login and tenant isolation | BLOCKED | Requires live OIDC owner identity |
| A11 browser permission review | BLOCKED | Requires physical browser/site settings |
| A12 no enabled prohibited/Auto-Run controls | BLOCKED | Requires physical owner acceptance; automated plan-only checks are supplemental |

## 3. Two-account OIDC acceptance

**BLOCKED / NOT RUN.** This requires a trusted OIDC issuer, two separately controlled test identities, an owner-controlled private deployment and a disposable project. Mocked principals or CI browser emulation are not substitutes. The second account must have no default access; only a specifically approved read-only grant may be tested; prohibited mutations and execution must be denied; revocation must take effect on the next server authorization check and survive restart.

## 4. Issues and safety findings

No new Android CSS defect was established by the reviewed source. Existing responsive checks and exact-head CI are the appropriate automated regression evidence. The remaining blockers are environmental and product-scope boundaries, not issues that can be safely fixed by changing CSS.

Important delivery gap: the current client is a responsive Streamlit web prototype. It is not a native Android app or installable PWA. The architecture correctly defers PWA installation until HTTPS, authentication, CSRF/session protection and service-worker cache boundaries are reviewed. Do not add a service worker or public install route before those controls are ready.

The Android viewport test launches a local-only Streamlit test server with CORS and XSRF protection disabled for the isolated localhost browser test. This must not be copied into deployment configuration. The deployment preflight remains read-only and does not prove that a real host is secure.

## 5. Required next steps to complete Workstream A

1. Owner provisions or selects a genuinely private, no-cost HTTPS test host with authentication enforced and private persistent storage. No paid plan, public anonymous demo or billing action.
2. Configure trusted OIDC using the provider's protected secret store. Do not paste credentials, client secrets, cookies or tokens into ChatGPT or GitHub.
3. Run `python scripts/preflight_android_deployment.py --secrets /absolute/private/path/secrets.toml` in the trusted host environment; keep secret values private.
4. Open the approved URL on the owner's physical Android phone and execute P64 A01–A12. Record redacted results privately against the exact tested code SHA.
5. Run live two-account OIDC grant/revoke, stale-session denial and restart persistence tests.
6. Obtain independent review of the redacted evidence digest and exact code SHA.
7. Only after the authenticated PWA/security boundary is independently reviewed, decide whether to implement the installable PWA shell; native Android companion remains a separate later stage.

## 6. Release and permission locks

- Owner-first/private access; no public signup or anonymous access.
- Auto-Run OFF; Worker and Browser execution DISABLED.
- No Accessibility, VPN, device-admin, screen-capture or broad device permissions for this acceptance path.
- No paid API/provider, paid hosting, purchase, payment, checkout, trading or money movement.
- No deployment, merge, public exposure, DNS/firewall mutation, provider account creation or secret provisioning performed by this checkpoint.
- PR #12 remains Draft/Open/Unmerged.
- S09 C01 remains OPEN / NOT COMPLETE; S09 C02 remains NOT STARTED.

## 7. Final status

| Area | Status |
|---|---|
| Responsive Android web UI in repository | IMPLEMENTED |
| Android browser emulation tests | IMPLEMENTED; exact-head CI PASS on P70 |
| Read-only authenticated deployment preflight | IMPLEMENTED; not run against a real host |
| Native Android APK | NOT IMPLEMENTED |
| Installable PWA | NOT IMPLEMENTED; correctly gated on HTTPS/auth review |
| Physical Android A01–A12 | BLOCKED |
| Live two-account OIDC grant/revoke | BLOCKED |
| Independent evidence review | BLOCKED |

**Conclusion:** Repository-side Android preparation is complete for this audit checkpoint, but Workstream A is not complete. Physical device, private host, live OIDC and independent evidence are mandatory external gates. No test result is fabricated or promoted across environments.
