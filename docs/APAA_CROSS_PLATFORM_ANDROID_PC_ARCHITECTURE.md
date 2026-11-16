# APAA Cross-Platform Product Architecture — Android + PC

Status: PRODUCT REQUIREMENT RECORDED. IMPLEMENTATION AND END-TO-END VERIFICATION ARE NOT COMPLETE.

## 1. Product decision

APAA (Personal AI Automation Agent) must support both:

1. Android phones/tablets.
2. PC desktop environments, initially Windows and Linux.

"Android-first" means Android is the current development, usability and hands-on verification priority. It does not mean Android-only. PC support is a first-class product requirement and must be preserved in architecture and acceptance criteria.

## 2. Recommended delivery strategy

### Phase A — shared responsive web application

Build one shared application experience that works in modern Android and desktop browsers. Use responsive layouts and adaptive interaction patterns:
- Android: touch-first controls, compact navigation, readable forms and narrow-screen layouts.
- PC: keyboard and mouse support, desktop-width workspace, accessible focus states and efficient multi-panel layouts where useful.

A responsive web application is the lowest-complexity shared starting point. Evaluate PWA installation only after browser compatibility, offline behavior, authentication and update safety have been tested.

### Phase B — optional platform packaging

- Android: consider a native wrapper/APK only if browser/PWA capabilities do not meet a validated requirement.
- Windows/Linux: consider a desktop wrapper only if browser-based use is insufficient.
- Do not create two independent agent cores or duplicate permission logic.

Packaging is a later delivery choice, not a prerequisite for Android + PC browser access.

## 3. Platform-neutral core

The following must remain shared and independent of screen/device:
- authenticated identity and issuer + subject ownership
- owner-first project access, explicit grants and revocation
- task planning and task state model
- policy engine and denied-action rules
- Ask First approval workflow and single-use approval receipts
- execution gateway and registered capability handlers
- audit events and retention rules
- provider abstraction with free/offline default and paid-provider extension disabled
- versioned project data and export/import migration rules

UI components must never be the security boundary. Every protected operation must be authorized server-side.

## 4. Platform adapters and permissions

Device-specific capabilities must be isolated behind explicit platform adapters. Android permissions do not imply PC permissions and vice versa. A capability must remain unavailable unless its adapter exists, its security review passes, and the user separately authorizes it.

No silent access to local files, camera, microphone, notifications, shell, browser sessions, device controls or background execution. Browser/worker execution remains disabled unless separately authorized. Auto-Run remains OFF.

## 5. Cross-platform security invariants

- The user is the primary owner/admin.
- No public access or self-registration by default.
- Owner explicitly grants and can revoke other-user access.
- Collaborators cannot elevate privileges, invite others, or mutate owner resources unless a future separate permission model is designed and approved.
- Ask First remains the default for consequential actions.
- No payment, checkout, purchase, trading or money movement actions.
- No paid API/provider use or charges by default; any future paid option requires separate explicit provider and cost approval.
- Session identity changes and revocations take effect at server-side request boundaries.
- No platform-specific UI can bypass core authorization.

## 6. Data continuity between Android and PC

The product should support the same account and authorized projects from Android and PC. Before claiming seamless sync:
- define a versioned canonical project/task format;
- define server-side storage and ownership boundaries;
- define conflict handling and concurrent update behavior;
- define export, import, backup and restore;
- test session expiry and access revocation across devices.

Do not assume that the current SQLite local prototype is already a multi-device synchronization service. Multi-device sync requires an explicitly designed and secured server deployment and is not enabled by this requirement.

## 7. Required verification gates

Automated:
- Android-sized and desktop-sized viewport tests.
- keyboard navigation and touch-target checks.
- shared permission and policy tests independent of platform.
- platform-adapter permission tests.
- session transition, revocation and cross-device identity tests.
- data export/import compatibility tests.

Hands-on:
- real Android phone browser verification.
- real Windows PC browser verification.
- real Linux PC browser verification where supported.
- verify login/logout, project ownership, approval, revocation and responsive layout on each platform.

CI viewport emulation is not a substitute for physical device and desktop verification.

## 8. Current truth / non-claims

At the time this requirement is recorded:
- APAA is a Streamlit web prototype foundation.
- Android-responsive styling exists but real Android device verification is outstanding.
- No native Android APK is complete.
- No completed PWA install package is established.
- No completed Windows or Linux desktop application is established.
- No verified cross-device sync service is established.
- Do not claim Android + PC support is fully delivered until the relevant build and verification gates pass.

## 9. Implementation order

1. Preserve Android-first responsive web usability.
2. Keep core business logic and authorization platform-neutral.
3. Complete S09 security and access-control gates before enabling sharing or deployment.
4. Audit all routes and resource reads/writes through server-side authorization.
5. Establish secured multi-device backend and versioned data migration design.
6. Verify Android and PC browsers with real devices.
7. Decide whether native Android or desktop packaging adds measurable value.

PR #11 remains Draft/Open/Unmerged. This requirement does not authorize deployment, merging, public access, paid services, Auto-Run, browser or worker activation.
