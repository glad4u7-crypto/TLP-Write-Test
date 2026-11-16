# Autonomous Personal AI Automation Agent (APAA)

A safety-first, zero-cost foundation for a personal digital-task agent. The current product is a Streamlit web prototype; it is not yet a fully autonomous browser/device-control system or a native Android app.

## Current application

- Streamlit workspace and Project Manager.
- Structured Task Workspace with READY / NEEDS_CLARIFICATION / BLOCKED review, ordered step details, clarification re-planning and visible mutation-approval labels; planning remains read-only.
- Deterministic built-in `RuleBasedProvider`; no external AI model or network API is called by the current dashboard.
- Optional OIDC authentication using Streamlit's verified identity claims. For any deployment exposed beyond a private local prototype, configure authentication as required with `[apaa].require_auth = true`.
- Authenticated project records use SQLite persistence scoped by the OIDC issuer + subject pair.
- Local unauthenticated prototype mode is explicitly warned as unsafe for public exposure; its project registry is session-only and its audit fallback is local JSONL.
- Explicit two-step project creation: review details, then confirm. The trusted UI/controller issues a short-lived, payload-bound, single-use approval receipt.
- Approval receipts are bound to the action, canonical payload, tenant and session scope; authenticated mode uses a configured stable signing secret and durable SQLite nonce storage.
- Execution gateway dispatches only explicitly registered handlers. The current UI registers project creation only; it does not expose arbitrary shell, browser, email, network, filesystem or device actions.
- Authenticated execution audit uses durable SQLite events; audit intent is persisted before handler dispatch and failure blocks dispatch. Local prototype mode uses a JSONL audit file.
- Tenant-scoped project CRUD and identity/session cleanup are covered by automated tests.

## Zero-cost and safety boundaries

- Built-in `RuleBasedProvider` is the active default and performs no network requests.
- External model providers are not called by the current dashboard. The dormant provider extension must remain disabled unless the user explicitly opts in; any paid provider additionally requires separate explicit cost approval.
- No API key is required for the current zero-cost build. Do not request or add paid-provider credentials for routine development.
- Payment, purchase, checkout, trading, money movement and paid-service action identifiers are denied by the safety policy.
- Auto-Run remains disabled; no task text can grant execution authority.
- No real-world browser, shell, email, arbitrary network, filesystem or device handlers are registered.

## Run locally

Requires Python 3.10 or newer.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
streamlit run app.py
```

On Windows, activate the virtual environment with `.venv\\Scripts\\activate`.

Local prototype mode does not enforce authentication. Do not expose it publicly. For authenticated non-production verification, configure Streamlit OIDC under `[auth]`, set `[apaa].require_auth = true`, and provide a protected `approval_signing_secret_hex` of at least 32 bytes (hex-encoded), plus private paths for `security_db_path` and `project_db_path`. Never commit secrets, tokens, cookies or identity data. Live OIDC/browser verification and production deployment are not yet approved.

## Verify

```bash
python -m compileall -q app.py core tests
python -m pytest -q
```

GitHub Actions additionally run dependency audit, browser smoke tests and disposable rootless-Podman qualification workflows.

## Known limitations and release blockers

- Streamlit web prototype only; a native Android application has not been built. The Task Workspace has responsive browser styling but has not yet had real-device Android verification.
- The planner is deterministic planning logic, not a generative model.
- Only project creation is currently wired through the UI execution gateway. Structured task plans are not dispatched or executed.
- OIDC claim-adapter and authorization tests do not replace live identity-provider and real-browser testing.
- Browser cookies, CSRF, redirects, TLS/reverse-proxy configuration, branch protection, independent audit anchoring, encrypted off-site backups, retention/restore operations, host/container isolation, single-writer deployment topology and operational ownership require separate evidence.
- SQLite and in-process capabilities are not a hostile-code sandbox or a validated multi-host production architecture.
- Production is **NOT APPROVED** until the release blockers have independently reviewed evidence and explicit approval.

See [S04 Security Pass/Block Matrix](docs/APAA_S04_SECURITY_PASS_BLOCK_MATRIX.md), [S04 Final Security Closure Plan](docs/APAA_S04_FINAL_SECURITY_CLOSURE_PLAN.md), [P31 Final Evidence Inventory](docs/APAA_S09_C01_P31_FINAL_EVIDENCE_INVENTORY_AND_CLOSURE_GATE.md), [P32 Android-first qualification](docs/APAA_S09_C01_P32_ANDROID_FIRST_BULK_QUALIFICATION.md), and the [authenticated Android test setup runbook](docs/APAA_S09_C01_AUTHENTICATED_ANDROID_TEST_SETUP.md).

## Development rules

1. Keep the default build free and offline.
2. Never implement payment, purchase, checkout, trading or money movement.
3. Require explicit, action-specific user approval for consequential mutations.
4. Keep external providers disabled by default; no automatic paid fallback.
5. Keep real-world execution handlers disabled until separately designed, sandboxed and reviewed.
6. Keep pull requests open and Draft until their CI and security review are complete; do not merge or deploy without explicit authorization.

## Current work — S09 C01

The active APAA security-hardening work is tracked in [Pull Request #11](https://github.com/glad4u7-crypto/TLP-Write-Test/pull/11), on branch `feature/apaa-s09-c01-p16-oci-lifecycle` targeting `feature/agent-v0.3-zero-cost-core`.

Latest exact PR head verified: `6f8cc1e32e6464983dc9468487be2ed51c4f4791` (2026-11-16). All four required PR-triggered workflows completed **PASS** on this exact head: [Agent Foundation CI #1022](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43828000688), [Python Demo CI #1097](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43828000755), [P20 Rootless Podman Runtime Qualification #151](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43828000804), and [P23 Rootless Podman Executor Integration #133](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43828000800). Agent Foundation included the automated Android/desktop Chromium emulation matrix; P20/P23 ran disposable rootless Podman CI qualification. These are repository and disposable-CI results only, not physical Android, owner-controlled real-host, protected signer, independent anti-rollback, complete sink-side egress, or independent security-review evidence. The P32 report records the detailed job results. Subsequent commits updating the P32 report and README are documentation-only; no new CI result is implied for those later commits.

S09 C01 remains **OPEN / NOT COMPLETE** until every mandatory P31 real-host gate is independently evidenced and approved. PR #11 remains Draft/Open/Unmerged. Auto-Run remains OFF; browser/worker execution remains disabled; do not merge or deploy without explicit owner authorization.

## Product direction — Android primary, PC optional

Android is the owner's primary device and the main development, usability and hands-on verification priority. APAA must be useful from Android without requiring the owner to own, configure, test or use a PC.

PC/desktop browser compatibility for Windows and Linux is preserved as an optional future path. If the owner later chooses to use a PC, the same platform-neutral core and account model should support it. Choosing not to use a PC must not block Android development or Android use. A desktop wrapper is optional and not a prerequisite.

- **Android now:** responsive, touch-first browser experience; physical Android Chrome verification remains outstanding.
- **PC later if wanted:** retain desktop browser compatibility and keyboard/mouse layouts; physical PC verification is needed only before claiming PC release readiness.
- **Shared core:** identity, owner-controlled access, project/task models, approval gateway, policy engine, audit trail and provider interfaces remain platform-neutral.
- **Consistent security:** owner-first access, Ask First, Auto-Run OFF, no payment/purchase actions, no paid providers by default, and no browser/worker/device-control activation without separate authorization.
- **Data portability:** versioned data and secure migration/sync design are required before claiming cross-device continuity.

See [Android-primary, PC-optional architecture](docs/APAA_CROSS_PLATFORM_ANDROID_PC_ARCHITECTURE.md) and [Android-first product architecture](docs/APAA_ANDROID_FIRST_PRODUCT_ARCHITECTURE.md).

## Android-first responsive interface (in progress)

- The Streamlit workspace uses a centered, narrow-friendly page layout and starts with the sidebar collapsed for small-screen usability.
- Shared responsive styles provide 44px minimum touch targets, 16px form text to reduce mobile browser zoom, horizontally scrollable tabs, and narrow-screen spacing/typography.
- Styling is isolated in `core/mobile_ui.py`; it changes presentation only and does not grant task execution authority.
- Automated style contract tests live in `tests/test_mobile_ui.py`; Pixel 7-profile browser emulation is covered in CI.
- This remains a responsive web prototype, not a PWA install package or native Android APK. Physical Android Chrome verification is required before marking Android usability fully complete.
