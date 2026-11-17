# APAA Android-First, Free-Only Operating Requirements

Status: Owner-approved project requirement, 2026-11-17
Project: Personal AI Automation Agent (APAA)
Repository: `glad4u7-crypto/TLP-Write-Test`

## 1. Product definition

APAA is an Android-first personal automation agent. The Owner should be able to give a natural-language instruction from an Android phone and have APAA perform the corresponding ordinary digital task that the Owner could perform manually on that phone, across supported Android apps, browsers, websites, files, and connected services.

APAA is not limited to web search, browser automation, or read-only research. Those are only subsets of the intended capability.

The product goal is broad practical task coverage, subject to Android platform restrictions, app permissions, service terms, security controls, and explicit Owner approval.

## 2. Non-negotiable cost requirements

- The project and its required runtime must be designed to operate without subscription fees, paid APIs, paid model endpoints, paid automation platforms, or mandatory purchases.
- Prefer free and open-source software, local execution, on-device capabilities, and user-owned infrastructure that has no mandatory service charge.
- Do not add a feature whose normal operation silently depends on a paid tier, trial, credit balance, or metered API.
- Before proposing an optional external service, document whether it is genuinely free, its limits, whether a key/account is required, and whether it can unexpectedly incur charges. Paid options are not part of the default architecture.
- Do not claim that internet connectivity, mobile data, hosting, or device electricity are free. The requirement is that APAA itself must not require a paid product/service to operate.
- Do not require Google Play paid developer registration or another paid distribution channel. Prefer a transparent, owner-controlled installation route where practical.

## 3. Absolute financial-action prohibition

APAA must not perform, initiate, automate, or facilitate:
- payments, UPI transfers, bank transfers, wallet transfers, remittances, or money movement;
- purchases, checkout, subscriptions, paid bookings, paid upgrades, or placing paid orders;
- adding or saving payment methods, changing payment credentials, or confirming financial transactions.

This prohibition applies even if a website/app exposes an API or the Owner has previously approved another category of actions. No general-purpose approval can override it. Financial flows should be detected and blocked before execution; ambiguous financial actions must fail closed.

## 4. Android-first execution coverage

Build toward three complementary execution paths:

1. **Native Android interaction:** explicitly enabled AccessibilityService and approved Android intents/deep links for screen understanding, navigation, taps, scrolling, and text entry in apps where Android and the app permit it.
2. **Browser automation:** a separately isolated, owner-controlled browser runtime for supported websites, with default-deny network egress, destination validation, and no uncontrolled background access.
3. **Direct integrations:** free/local or otherwise no-cost APIs and app integrations where available, with explicit per-integration scopes and the same approval/audit policy.

Prefer a supported direct integration when it is safer and more reliable than UI automation. Fall back to UI interaction only where it is permitted and tested. Keep the Owner informed about which execution path is being used.

## 5. Platform and security limits

- Do not root the phone as a requirement. Do not require bypassing Android sandboxing, permission prompts, app protections, DRM, CAPTCHA, OTP, biometric checks, or security controls.
- Android Accessibility access, screen capture, notifications, files, contacts, microphone, camera, and other sensitive permissions must be separately explained and explicitly enabled by the Owner.
- Respect Android background-execution limits, foreground-service requirements, app-specific restrictions, and user-visible indicators.
- Banking, identity, security, and other sensitive apps must not be treated as ordinary automation targets. Never read or store passwords, OTPs, card details, private keys, or authentication secrets. Do not automate transaction or identity-verification confirmation screens.
- If an app prevents automation or requires a human security step, stop and ask the Owner to complete that step manually; never claim the task is complete.
- Never expose local control endpoints to the public internet. Use authenticated, least-privilege, owner-controlled local communication.

## 6. Permission, approval, and audit

- The Owner is the primary administrator and controls all users, permissions, integrations, and revocation.
- Default behavior is Ask First for actions that change external state, send content, publish, delete, share, or modify account settings.
- Auto-Run remains OFF by default. No silent unattended action execution.
- Every action must be scoped, previewable where practical, attributable to the Owner session, and recorded in a payload-minimizing audit trail.
- Uncertain outcomes must not be blindly retried. Present the uncertainty and require Owner reconciliation.
- A missing permission, failed authentication, untrusted destination, or ambiguous instruction must stop execution safely.

## 7. Capability development and release criteria

For every capability, track:
- Android app / website / service and exact task scope;
- execution path (native Android, browser, or direct integration);
- free/open-source dependencies and any operational cost or limit;
- required Android permissions and Owner approvals;
- prohibited/blocked cases;
- unit, integration, security, and real-device test evidence;
- current status: planned, implemented, CI-tested, device-tested, accepted, or blocked.

Do not label a capability complete based only on interface code or mocked tests. Android device behavior and the target app's actual restrictions must be tested before claiming practical support.

## 8. Current implementation boundary

The current Personal Edition branch contains the Owner/runtime foundations, read-only adapters, and public read-only research providers described in the project documentation. Those components do not yet deliver general Android app control. Browser/Worker execution remains disabled until its isolation and egress boundary are qualified. Physical Android acceptance and live provider smoke tests remain separate acceptance gates.

This document records the Owner's product requirements; it does not assert that the full target capability has already been implemented.
