# Autonomous Personal AI Agent (APAA)

A safety-first, zero-cost foundation for a personal digital-task agent. The current product is a Streamlit web prototype; it is not yet a fully autonomous browser/device-control system or a native Android app.

## Current application

- Streamlit workspace and Project Manager.\n- Structured Task Workspace with READY / NEEDS_CLARIFICATION / BLOCKED review, ordered step details, clarification re-planning and visible mutation-approval labels; planning remains read-only.
- Deterministic built-in `RuleBasedProvider`; no external AI model or network API is called by the current dashboard.
- Optional OIDC authentication using Streamlit's verified identity claims. For any deployment exposed beyond a private local prototype, configure authentication as required with `[apaa].require_auth = true`.
- Authenticated project records use SQLite persistence scoped by the OIDC issuer + subject pair.
- Local unauthenticated prototype mode is explicitly warned as unsafe for public exposure; its project registry is session-only and its audit fallback is local JSONL.
- Explicit two-step project creation: review details, then confirm. The trusted UI/controller issues a short-lived, payload-bound, single-use approval receipt.
- Approval receipts are bound to the action, canonical payload, tenant and session scope; authenticated mode uses a configured stable signing secret and durable SQLite nonce storage.
- Execution gateway dispatches only explicitly registered handlers. The current UI registers project creation only; it does not expose arbitrary shell, browser, email, network, filesystem or device actions.
- Authenticated execution audit uses durable SQLite events; audit intent is persisted before handler dispatch and failure blocks dispatch. Local prototype mode uses a JSONL audit file.
- Tenant-scoped project CRUD and identity/session cleanup are covered by automated tests.
- Two existing GitHub Actions workflows provide dependency audit, compilation, and automated test/demo verification.

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

The existing CI workflows also run `pip-audit` and the demo smoke test.

## Known limitations and release blockers

- Streamlit web prototype only; a native Android application has not been built. The Task Workspace has been structured for responsive browser review but has not yet had real-device Android verification.
- The planner is deterministic planning logic, not a generative model.
- Only project creation is currently wired through the UI execution gateway. Structured task plans are not dispatched or executed.
- OIDC claim-adapter and authorization tests do not replace live identity-provider and real-browser testing.
- Browser cookies, CSRF, redirects, TLS/reverse-proxy configuration, branch protection, independent audit anchoring, encrypted off-site backups, retention/restore operations, host/container isolation, single-writer deployment topology and operational ownership require separate evidence.
- SQLite and in-process capabilities are not a hostile-code sandbox or a validated multi-host production architecture.
- Production is **NOT APPROVED** until the S04 release blockers have independently reviewed evidence and explicit approval.

See [S04 Security Pass/Block Matrix](docs/APAA_S04_SECURITY_PASS_BLOCK_MATRIX.md) and [S04 Final Security Closure Plan](docs/APAA_S04_FINAL_SECURITY_CLOSURE_PLAN.md).

## Development rules

1. Keep the default build free and offline.
2. Never implement payment, purchase, checkout, trading or money movement.
3. Require explicit, action-specific user approval for consequential mutations.
4. Keep external providers disabled by default; no automatic paid fallback.
5. Keep real-world execution handlers disabled until separately designed, sandboxed and reviewed.
6. Keep pull requests open and Draft until their CI and security review are complete; do not merge or deploy without explicit authorization.

## Current work

The active APAA security-hardening work is tracked in [Pull Request #11](https://github.com/glad4u7-crypto/TLP-Write-Test/pull/11), on branch `feature/apaa-s09-c01-p16-oci-lifecycle` targeting `feature/agent-v0.3-zero-cost-core`. At the verified head recorded on 2026-11-16 (`e4109f4bb382a29d1ce0fd4e10a176777c58119e`), the PR is Open + Draft + Unmerged. Four PR-triggered workflows associated with that exact commit completed successfully: Agent Foundation CI, Python Demo CI, P20 Rootless Podman Runtime Qualification and P23 Rootless Podman Executor Integration. These are repository/disposable-runner results only; they do not qualify an owner-controlled Linux host, protected signer, independent anti-rollback anchor, complete sink-side egress topology, physical Android/PC devices or independent security review. Keep C01 OPEN / NOT COMPLETE until every P31 gate is independently evidenced and approved. Auto-Run remains OFF; browser/worker execution remains disabled; do not merge or deploy without explicit owner authorization.


## Cross-platform product commitment: Android + PC

APAA is a cross-platform product, not an Android-only project. Android-first describes the current development and hands-on test priority; it does not remove PC support from the product target.

- **Android:** mobile browser-first experience, with responsive touch UI. Native Android packaging may be considered after the shared web experience and security boundaries are stable.
- **PC:** desktop browser experience for Windows and Linux, with keyboard/mouse-friendly responsive layouts. A desktop wrapper is optional future work, not a prerequisite for using APAA on PC.
- **Shared core:** identity, owner-controlled access, project/task models, approval gateway, policy engine, audit trail and provider interfaces must remain platform-neutral.
- **Platform adapters:** device/browser capabilities must be isolated behind explicit adapters and permission checks. A feature available on one platform must not silently become available on another.
- **Consistent security:** same owner-first access model, Ask First default, Auto-Run OFF, no payment/purchase actions, no paid providers by default, and no browser/worker/device-control activation without separate authorization.
- **Data portability:** use documented, versioned data formats and a migration/export plan so a user can move between Android and PC without losing project records.
- **Verification:** test responsive layouts at Android-sized and desktop-sized viewports in CI; separately require real Android-device and real PC-browser verification before platform-specific release claims.

The current Streamlit implementation is a prototype foundation. It is not yet a completed Android app, PWA package, Windows application, Linux desktop application, or verified cross-device sync product. Do not describe those deliverables as complete until built and tested.

## Android-first responsive interface (in progress)

- The Streamlit workspace now uses a centered, narrow-friendly page layout and starts with the sidebar collapsed for small-screen usability.
- Shared responsive styles provide 44px minimum touch targets, 16px form text to reduce mobile browser zoom, horizontally scrollable tabs, and narrow-screen spacing/typography.
- Styling is isolated in `core/mobile_ui.py`; it changes presentation only and does not grant task execution authority.
- Automated style contract tests live in `tests/test_mobile_ui.py`.
- This is still a responsive web prototype, not a PWA install package or native Android APK. Physical Android Chrome verification is a required hands-on exercise before marking this part complete.
