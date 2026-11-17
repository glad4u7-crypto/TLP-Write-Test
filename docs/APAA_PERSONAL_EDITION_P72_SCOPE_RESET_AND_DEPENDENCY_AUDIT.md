# APAA Personal Edition — Product Scope Reset and Dependency Audit

**Checkpoint:** APAA-PERSONAL-P72  
**Date:** 2026-11-17  
**Source audit head:** `46e56d772f829edab5dc106c385ef8eec2af64d8` (PR #12, Draft/Open/Unmerged)  
**Working branch:** `apaa-personal-edition-foundation`  
**Decision:** Personal Edition is the primary delivery target. This is a scope reset and dependency audit, not a claim that the app is complete.

## 1. Product goal

Build a useful, safe, zero-cost personal automation agent controlled by one owner, primarily from an Android phone. The product is not a general public multi-user service and does not need enterprise-scale identity, hardware custody or remote-worker infrastructure for its first usable release.

The first release should let the owner:
- give natural-language task instructions from an Android-friendly interface;
- search and read owner-authorized websites and compare information;
- prepare clear multi-step plans, ask clarification questions, pause and resume;
- review and explicitly approve each consequential change;
- work with owner-selected files/documents;
- discover YouTube videos and, only after explicit approval and supported account authorization, make playlist changes;
- inspect task progress, results and a useful action history;
- export and back up personal project/task data.

The current implementation remains a Streamlit web prototype with deterministic offline planning. It does not yet provide general browser automation, YouTube integration, arbitrary file automation, a native Android APK or a PWA.

## 2. Non-negotiable personal safety

- One configured owner; no public signup, collaborator invitation or multi-tenant sharing in Personal Edition v1.
- Every mutation requires a fresh, action-specific, payload-bound user approval. Auto-Run remains OFF.
- Read-only discovery and write-capable actions are separate capabilities.
- Payment, purchase, checkout, trading, investment orders, money movement and paid-service actions are denied; they are not merely hidden.
- No paid API/provider, paid hosting, billable browser service, automatic paid fallback, API-key request or cost-incurring provisioning.
- Secrets and tokens stay out of chat, Git, task plans, browser local storage and logs.
- Browser/worker execution is not enabled until the specific capability has a bounded design, approval path and meaningful tests.
- Local unauthenticated mode is restricted to loopback/private local development. It must never be presented as safe for public or LAN exposure.
- Remote Android access requires a separately reviewed authenticated HTTPS boundary; a private URL alone is not authentication.
- Backups must be owner-controlled and restorable. Audit records should be useful and privacy-minimizing, not enterprise append-only infrastructure.

## 3. Dependency audit — keep, simplify, defer

### KEEP in Personal Edition v1 (core dependencies)

| Component | Reason |
|---|---|
| `core/planner.py`, task models and clarification flow | Safe task intake and reviewable plan |
| `core/safety.py` | Deny prohibited actions centrally |
| `core/approvals.py`, `core/execution.py` | Explicit approval and allowlisted handler boundary |
| `core/audit.py` plus durable local audit storage | User-visible action history and fail-closed mutation intent |
| `core/projects.py` and SQLite project persistence | Persistent personal workspace |
| `core/memory.py` with explicit consent | Optional personal memory/checkpoints |
| `core/session_security.py` and secret handling | Prevent stale session/credential reuse |
| `core/mobile_ui.py` | Android-first responsive interface |
| Automated unit, integration and browser-emulation tests | Prevent regressions |

### SIMPLIFY (retain a small safe path)

- Identity: one local owner context for local-only use; optional single-owner OIDC only when remote hosting is deliberately chosen. Do not require a multi-account directory.
- Project access: owner-only checks; no collaborator ACL/grant/revoke UI in v1.
- Persistence: one owner-only SQLite data store with private filesystem permissions, backup/export and restore checks. Avoid multi-tenant and multi-host claims.
- Approval: one clear Ask First flow with short-lived, one-time, action/payload-bound receipts. No Auto-Run configuration surface.
- Audit: local durable, privacy-minimizing history with integrity checks. No claim of independent tamper-proofing.
- Android: responsive web client first; decide on PWA/native packaging only after a safe authenticated transport and physical-device usability checks.

### DEFER / PARK (do not build or provision for v1)

- Multi-user tenant sharing, trusted identity directory, owner grant/revoke workflows and two-account OIDC acceptance.
- Enterprise global-admin APIs, owner-generation recovery and offline multi-owner recovery machinery beyond the minimum needed for a single local owner.
- PKCS#11/HSM physical signer provisioning and hardware custody review.
- Remote independent monotonic anchor, mTLS anchor service, CAS conformance and external anti-rollback operations.
- OCI/Podman worker lifecycle, remote attestation, nftables host inspection, proxy-only worker egress and disposable Linux host qualification.
- Independent enterprise reviewer workflow, enterprise evidence packs, production SLO/RPO/RTO and multi-host deployment topology.
- Public signup, PC-first release and enterprise administration dashboards.

Parked modules and tests must not be deleted blindly in this reset: some may be imported by the current app or tests. First prove import/runtime dependencies, then isolate optional code behind explicit disabled feature boundaries. Remove only after the dependency graph and test impact are established.

## 4. Current repository findings

1. The current app is Streamlit 0.4.0, not a native Android app/PWA.
2. The active planner is deterministic and offline; it does not call an AI provider.
3. The UI currently wires project creation only. Structured task plans are not yet dispatched to real browser/app/file handlers.
4. Authenticated mode requires OIDC, a configured global owner, stable signing secret and SQLite stores; it is more elaborate than needed for a single-user local-only first run.
5. Unauthenticated local mode is explicitly warned as unsafe for public exposure, stores projects in Streamlit session state, and uses local JSONL audit. It is not yet an adequate persistent Personal Edition mode.
6. Browser, worker, PKCS#11, remote-anchor and Linux host-inspector modules exist in the wider S09 branch history but are not a reason to require those services for Personal Edition.
7. The repository contains many open Draft PRs (#1–#12). They are not all independent release prerequisites; their changes must be reconciled by dependency and retained/parked classification. Do not merge or close them automatically.

## 5. Recommended implementation order

**P72 — Scope reset and dependency audit:** this document and README alignment.  
**P73 — Personal owner runtime:** design and implement a local-only single-owner profile with persistent owner data, protected local secret handling, durable approvals/audit and safe startup. Preserve existing OIDC mode as optional remote-host path, not default dependency.  
**P74 — Personal workspace persistence:** projects, task plans, checkpoints and consent-gated memory survive restart; backup/export and restore tests.  
**P75 — Android experience:** responsive flow, physical Android smoke test, session behavior, clear approval/review/history UI. Keep the server loopback-only until remote HTTPS/auth is qualified.  
**P76 — Capability contracts:** typed read-only web search/navigation, document/file access and YouTube discovery; no mutation handlers yet.  
**P77 — Local Owner authentication event audit hardening:** tamper-evident local event chain, backup/restore verification and regression tests (implemented on the P73 branch).  
**P78 — First safe adapters:** read-only browsing/search and file inspection with strict origin/path/user-scope boundaries.  
**P79 — Approved mutations:** per-action payload-bound confirmation, durable tenant-scoped idempotency, pre-dispatch cancellation, metadata-only audit, uncertain-outcome recovery and regression tests. Core gateway/storage implementation is committed; P78 adapter/UI integration and exact-head CI remain gates.  
**P80 — Personal release review:** release-readiness assessment, dependency/test/Android/backup review and owner sign-off. The 2026-11-17 review disposition is NO-GO because P78, latest exact-head CI, physical Android acceptance, owner-operated backup/restore and independent review are outstanding.

## 6. Acceptance definition for Personal Edition v1

- Single owner only; no public signup or collaborator access.
- Works without paid APIs or paid infrastructure.
- Persistent personal projects/tasks/checkpoints and owner-controlled backup.
- Android-friendly UI and verified physical Android browser usage.
- Clear plan → review → approve → execute → audit lifecycle.
- No arbitrary shell, unrestricted network, hidden browser control or broad device permissions.
- All prohibited financial/payment actions denied at the policy layer.
- Every enabled adapter has separate allow/deny, approval, failure, retry/cancel and audit tests.
- No feature is described as available until it actually works and has evidence.

## 7. Release posture and current work

This checkpoint does not modify production configuration, delete existing security modules, enable browser/worker execution, provision any host/provider, create credentials, or merge a PR. PR #12 remains Draft/Open/Unmerged. C01 enterprise qualification is no longer the critical path for the Personal Edition v1; its unfinished external hardware/anchor/host gates are parked unless a later feature genuinely needs them. Existing safeguards that protect current code remain until replacement personal-mode safeguards pass tests.

**Checkpoint result:** Personal Edition product scope and repository dependency classification recorded. The following implementation updates supersede the historical progress notes above.

## 8. Later implementation status — 2026-11-17

- P73 single-owner runtime and persistent SQLite owner workspace are implemented; Owner authentication, session expiry, passphrase rotation, payload-free security-event chain, durable action audit, and backup/restore code have automated coverage.
- P79 now binds the existing memory, knowledge, conversation, preference and checkpoint UI mutations to fresh one-time approval receipts for the exact action + JSON payload + Owner tenant + session. Operations receive only the approved private payload snapshot.
- The existing project-create UI is connected to the durable tenant-scoped idempotency ledger. Each reviewed draft has a fresh request key; duplicate dispatch with the same key is blocked.
- P79 core implementation has an earlier exact-head PASS, but the latest UI integration changes still require a new exact-head CI run.
- P78 read-only adapters are still not implemented. No browser, file, YouTube or external mutation handler has been enabled.
- P80 remains **NO-GO** until P78, latest exact-head CI, Owner recovery UI for uncertain outcomes, physical Android acceptance, Owner-operated backup/restore drill, independent security review and explicit Owner acceptance are complete.

**Current safety posture:** PR #13 remains Draft/Open/Unmerged. No merge/deploy; Browser/Worker DISABLED; Auto-Run OFF; no paid providers, payments, purchases, trading or money movement.


## P78 implementation checkpoint — 2026-11-17

- Owner Recovery UI and atomic audited reconciliation are implemented.
- Bounded read-only adapter registry and secure project-file inspection are implemented.
- Injected web/HTTPS/YouTube provider adapters are contracts/wrappers only; no network provider is enabled.
- Exact-head CI is pending. Do not mark P78 automated-PASS until the exact latest branch head completes successfully.

## Code-first implementation reconciliation — 2026-11-17

This section supersedes older P72 historical status notes above.

- P78 read-only adapters and Owner Recovery UI are implemented.
- P81 read-only local runtime diagnostics are implemented and surfaced in the local Owner sidebar. P81 core exact-head CI run #250 passed: **1,499 Python tests passed, 9 skipped; compile, dependency audit and responsive browser smoke passed**.
- P82 Owner Backup & Restore UI is implemented in the local Owner sidebar. It creates a backup download and restores a validated archive only into a new directory; it does not overwrite or switch the live runtime.
- P83 persistent task-plan storage is implemented in the SQLite memory database. Saved plans are Owner/project scoped, require explicit consent and payload-bound approval in the UI, and are revalidated before loading.
- The Owner Health, Backup/Restore and Persistent Task Plan UI/storage additions are under exact-head CI verification. Latest code/documentation branch head at this update is `c250edd303bc5ece924a2b5bbe611c0b64a474db`; do not mark these newer additions verified until the exact-head run succeeds.
- Personal Edition implementation continues code-first. Physical Android acceptance, Owner-operated restore drill and live isolated Browser/Worker egress qualification are intentionally deferred until the Owner starts using the app.
- Browser/Worker DISABLED; Auto-Run OFF; no paid API/provider, payment, purchase, trading or money movement. PR #13 remains Draft/Open/Unmerged; C01 remains OPEN; C02 NOT STARTED.
- P84 project file workspace: owner-approved local UTF-8 text-file storage and bounded read-only inspection are implemented. The project-files directory is not yet included in the backup archive; this is an explicit pre-release follow-up, and the Owner UI/docs disclose the limitation.