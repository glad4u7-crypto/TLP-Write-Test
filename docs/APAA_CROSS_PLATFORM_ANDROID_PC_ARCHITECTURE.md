# APAA Cross-Platform Architecture — Android Primary, PC Optional

Status: OWNER PRODUCT DIRECTION RECORDED; platform implementation and physical-device verification remain in progress.

## 1. Product decision

Android is the primary device and primary hands-on development/verification target because it is the device the owner currently uses.

PC/desktop support is an OPTIONAL future-use path. The owner may use APAA only on Android and never use a PC; that choice must not block development, access to core features, or the Android roadmap. If the owner later has and chooses to use a PC, the same APAA account and platform-neutral core should be able to support a desktop browser client.

This is Android-first, PC-optional—not a requirement that the owner must own, configure, test, or regularly use a PC.

## 2. Delivery strategy

### Primary path — Android browser experience

- Continue improving the shared responsive web interface for Android Chrome.
- Prioritize touch-friendly controls, readable forms, compact navigation, keyboard behavior, session expiry/reconnect and accessible approval/status states.
- Consider PWA installation only after HTTPS, authentication, CSRF/session protections, update safety and service-worker cache boundaries are reviewed.
- Consider a native Android shell only when validated requirements cannot be met safely by the browser experience.

### Optional path — PC browser experience

- Preserve responsive desktop-browser compatibility for Windows and Linux.
- Support keyboard/mouse interaction and desktop-width layouts without making PC packaging or PC ownership a dependency.
- A desktop wrapper is optional future work, not required for Android delivery.
- PC physical-device verification is required only before making a specific PC release/support qualification claim; it must not block Android-only use.

## 3. Shared platform-neutral core

Keep these capabilities independent of the client device:
- authenticated identity and issuer + subject ownership
- owner-first project access, explicit grants and revocation
- task planning and task state model
- policy engine and denied-action rules
- Ask First approval workflow and single-use approval receipts
- execution gateway and registered capability handlers
- audit events and retention rules
- free/offline provider default with paid-provider extension disabled
- versioned project/task data and export/import migration rules

The Android and optional PC clients must use the same server-side authorization and policy decisions. UI components are never the security boundary.

## 4. Platform adapters and permissions

Device-specific capabilities must be isolated behind explicit platform adapters. Android permissions do not imply PC permissions and vice versa. A capability remains unavailable unless its adapter exists, its security review passes, and the owner separately authorizes it.

No silent access to local files, camera, microphone, notifications, shell, browser sessions, device controls or background execution. Browser/worker execution remains disabled unless separately authorized. Auto-Run remains OFF.

## 5. Security and owner controls

- The owner is the primary administrator; no public-by-default access or self-registration.
- The owner explicitly grants and can revoke other-user access.
- Collaborators cannot elevate privileges or mutate owner resources through a read grant.
- Ask First remains the default for consequential mutations.
- Payment, checkout, purchase, trading and money movement actions are denied.
- No paid API/provider, paid hosting or charges by default; any future paid option requires separate explicit provider and cost approval.
- Session identity changes and revocations take effect at server-side request boundaries.
- No platform-specific UI can bypass core authorization.

## 6. Data continuity (only if PC is later used)

If the owner chooses to use APAA on both Android and PC, design and verify:
- a versioned canonical project/task format;
- secured server-side storage and ownership boundaries;
- conflict handling and concurrent updates;
- export, import, backup and restore;
- session expiry and revocation across devices.

Do not assume the current SQLite local prototype is already a multi-device synchronization service. Multi-device sync requires a separately designed and secured backend and is not enabled by this document.

## 7. Verification gates

Automated CI should continue checking Android-sized and desktop-sized browser viewports, shared permission/policy behavior, keyboard navigation and touch targets.

Hands-on Android verification is the primary product gate: real Android Chrome login/session, responsive layout, approval review, logout and revocation behavior must be checked before claiming Android release readiness.

PC hands-on verification is conditional: perform it if/when the owner chooses to use or qualify the optional PC client. It is not a prerequisite for Android progress.

CI viewport emulation is not a substitute for physical-device verification.

## 8. Current truth / non-claims

- APAA is currently a Streamlit web prototype.
- Responsive Android styling and automated Pixel-profile browser emulation exist; physical Android verification remains outstanding.
- No native Android APK or completed PWA package is claimed.
- Desktop browser viewport smoke coverage exists; no completed Windows/Linux desktop app is claimed.
- No verified multi-device sync service is claimed.
- Android and optional PC release claims require their respective build and verification evidence.

## 9. Implementation order

1. Continue Android-first responsive web usability and physical Android verification.
2. Keep core business logic and authorization platform-neutral.
3. Complete S09 security and access-control gates before enabling sharing or deployment.
4. Audit all routes and resource reads/writes through server-side authorization.
5. Keep PC browser compatibility in CI and architecture, but do not make PC usage a dependency.
6. Establish secured multi-device sync only if/when cross-device use is selected.
7. Decide on native Android or desktop packaging only after measurable requirements exist.

PR #11 remains Draft/Open/Unmerged. This requirement does not authorize deployment, merging, public access, paid services, Auto-Run, browser or worker activation.
