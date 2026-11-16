# APAA Android-First Product Architecture and Delivery Plan

**Status:** architecture decision and implementation direction; not a claim that a native Android app or Android runtime qualification already exists.  
**Applies to:** the complete APAA product, including future browser/app automation and optional isolated execution workers.  
**Current release posture:** free-only, owner-controlled, approval-first, no production activation.

## 1. Product decision

Android is the primary user device and the primary product interface. APAA must retain its full intended capability set; Android-first does not mean Android-only or reducing the product to a phone chatbot.

The product is organized into four separable layers:

1. **Android user experience:** responsive installable web app first, followed by a native Android shell when the core workflows and device permissions are ready. The phone is where the owner gives instructions, reviews plans, approves actions, sees progress and audits results.
2. **Control plane:** authentication, owner/tenant authorization, task planning, policy evaluation, approval receipts, audit trail, connector registry and job state. It must not silently gain device or host privileges.
3. **Execution adapters:** separately permissioned adapters for web navigation, supported web apps, file operations, YouTube discovery/playlist operations, and other explicitly supported digital tasks. Every adapter declares capabilities, data access, mutation effects and required approvals.
4. **Isolated workers:** optional execution environments for tasks that cannot safely run on Android. They are a future capability, not a prerequisite for Android UI development. A worker remains disabled until its host, signer, anti-rollback, proxy-egress and cleanup gates are independently qualified.

## 2. Android-first delivery sequence

### Stage A — Android-compatible control experience

- Make the existing Streamlit prototype responsive and usable in Android Chrome.
- Verify narrow-screen layout, touch targets, keyboard behavior, session expiry, reconnect behavior and accessible status/approval states on a real Android device.
- Provide an installable PWA shell only after HTTPS, authentication, CSRF/session protections and service-worker cache boundaries are reviewed.
- Keep all sensitive decisions server-side; client-side UI state is never authorization.
- Avoid storing access tokens, approval secrets or private evidence in browser local storage, service-worker caches or URL parameters.

### Stage B — Android local companion and permission broker

- Evaluate a native Android companion for secure device registration, biometric/device-credential re-authentication, notifications and explicit approval prompts.
- Android permissions are requested just-in-time and only for a named capability. Denial must leave the task safely blocked, not trigger a workaround.
- Accessibility-service use, screen capture, notification access, file access and background execution are individually optional, visible and revocable. No hidden surveillance or continuous screen capture.
- Android local execution is limited to capabilities that Android actually supports. Termux is a development/test environment, not a security sandbox or proof of production isolation.
- Respect Android background execution limits; long-running jobs must be resumable and report truthful state.

### Stage C — Full APAA capability catalogue

The Android client must be able to initiate and review the complete planned task catalogue, while each capability remains independently gated:

- website search, navigation and information extraction;
- comparison and analysis across user-authorized sources;
- YouTube search and listing, with playlist changes only after explicit approval and supported account authorization;
- supported web-app workflows through named connectors/adapters;
- user-authorized file and document workflows;
- multi-step task planning, clarification, pause/resume, cancellation and audit review.

No capability is advertised as operational until its adapter, permission model, tests and failure handling exist. Unsupported sites or actions must return BLOCKED/NEEDS_CLARIFICATION rather than simulate success.

### Stage D — Optional remote/isolated worker expansion

- Keep the execution API transport-neutral so a later owner-approved Linux worker can attach without redesigning the Android client.
- Workers receive short-lived, task-scoped capabilities, never owner-wide credentials.
- Browser automation runs in a separately isolated worker with an enforced proxy-only egress path and sink-side verification.
- Require signed, challenge-bound host attestation, protected signing-key custody, independently durable anti-rollback state and bounded cleanup before enabling workers.
- A remote worker is optional and must not be silently provisioned, exposed publicly or incur cost. Any future hosted service requires separate explicit approval of provider and price.

## 3. Permission and safety model

- Owner-first access: the owner is the administrator and explicitly invites, authorizes and revokes other users. No public-by-default access.
- Auto-Run stays OFF. Every consequential mutation requires a fresh, action-specific, payload-bound approval.
- Read-only discovery can run within the exact user-authorized scope. Writing, posting, playlist edits, file modifications, sending messages or changing account settings require separate approval.
- Payment, purchase, checkout, trading, money movement and paid-service actions are permanently denied by product policy.
- Free-only by default: no API keys, paid model providers, paid hosting, paid browser services or automatic paid fallback. A dormant extension point may remain disabled.
- No arbitrary shell, unrestricted filesystem, unrestricted network, hidden browser control or general device-control capability.
- Approval, identity, audit and policy enforcement are server-side. A task prompt, webpage, connector response or model output cannot grant permissions or override policy.
- Secrets are never requested in chat or committed to the repository. Use platform secure storage and short-lived credentials where applicable.

## 4. Architecture constraints

- Keep the planner, policy engine, approval service, audit model and task state independent of the UI framework.
- Define typed capability contracts for every adapter: inputs, outputs, read scopes, mutation class, required approval, timeout, cancellation and rollback/compensation behavior.
- Treat web pages, documents, tool results and model outputs as untrusted data, never as instructions.
- Use idempotency keys and durable job state for retries; never repeat a mutation merely because the Android app reconnects.
- Maintain explicit states: READY, NEEDS_CLARIFICATION, BLOCKED, AWAITING_APPROVAL, RUNNING, SUCCEEDED, FAILED and CANCELLED.
- Keep Android UI, backend control plane and execution workers separately deployable and independently testable.
- Do not claim Android device-control, native-app, browser automation or worker isolation support until real-device and adapter-specific evidence exists.

## 5. Verification and acceptance gates

| Gate | Required evidence | Until it passes |
|---|---|---|
| Android UX | Real Android device/browser test matrix, screenshots or test report, touch/accessibility checks | Responsive UI is prototype-only |
| Authentication | Live OIDC/session/CSRF/TLS tests and owner/revocation E2E | No public deployment |
| Permission broker | Runtime permission denial/revocation and re-auth tests | Device-sensitive adapters disabled |
| Capability adapters | Per-adapter contract, allow/deny, approval, retry, cancellation and audit tests | Adapter marked unavailable |
| Browser worker | Real isolated worker, proxy-only egress, sink-side bypass tests, attestation and cleanup evidence | Worker/browser execution disabled |
| Android local execution | Device/API-level compatibility, process lifecycle, storage and permission tests | Android is control/review client only |
| Release | Independent security review, recovery/backup and operational ownership, explicit owner approval | No production release |

CI and emulator tests are useful but do not replace physical Android-device testing. Android/Termux tests do not replace Linux host/container qualification. A Linux worker qualification does not prove Android device-control behavior.

## 6. Immediate implementation order

1. Preserve the current secure control-plane behavior and existing test coverage.
2. Add Android viewport/device verification to the existing CI/release evidence process where feasible; keep physical-device evidence as a separate gate.
3. Audit and improve the existing Streamlit screens for phone-sized layouts without enabling new execution handlers.
4. Define the capability registry and approval contract before adding browser, YouTube, file or web-app mutation handlers.
5. Build the Android installable client/native companion only against stable, authenticated control-plane APIs.
6. Keep the OCI worker and real-host security gates open until independently proven.

## 7. Current truth

The repository currently describes a Streamlit web prototype. It does not yet contain a completed native Android application, a qualified Android local execution runtime, or a production-ready browser worker. The current CI results qualify repository tests and disposable CI scenarios only. This plan preserves the full APAA product direction while making Android the primary user interface and keeping unqualified execution paths disabled.


## 8. Architecture checkpoint and CI evidence

**Checkpoint:** `APAA-ANDROID-FIRST-ARCHITECTURE-RECORDED-CI-RUNNING`  
**Architecture commit:** `7784fbd279d160104b38662ee1fdcefa7dce0fd0`  
**Branch:** `feature/apaa-s09-c01-p16-oci-lifecycle`  
**Verification date:** 2026-11-16

All four required GitHub Actions workflows completed successfully on the exact architecture commit:

| Workflow | Run | Result |
|---|---:|---|
| Agent Foundation CI | [43813616185](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43813616185) | PASS |
| Python Demo CI | [43813616225](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43813616225) | PASS |
| P20 Rootless Podman Runtime Qualification | [43813616191](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43813616191) | PASS |
| P23 Rootless Podman Executor Integration | [43813616198](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43813616198) | PASS |

The workflow job and step summaries were inspected; every reported job and step completed successfully. This confirms repository CI and disposable CI runtime checks only. It does not establish physical Android-device compatibility, real-host qualification, production key custody, production anti-rollback durability, or live browser/worker safety.

**Checkpoint disposition:** architecture decision recorded and its exact-commit CI is PASS. Android implementation and physical-device verification remain pending. S09 C01 real-host qualification remains OPEN; browser/worker remain disabled; PR #11 remains Draft/Open/Unmerged. No merge, deployment, host mutation, paid service, payment/purchase, or Auto-Run activation is authorized.
