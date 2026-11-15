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

The active APAA security-hardening work is tracked in [Pull Request #5](https://github.com/glad4u7-crypto/TLP-Write-Test/pull/5), on branch `feature/approval-ui-e2e-p06` targeting `feature/agent-v0.3-zero-cost-core`. It remains Open + Draft and is not merged or deployed.
