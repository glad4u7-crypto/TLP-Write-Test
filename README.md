# Autonomous Personal AI Agent (APAA)

A safety-first, zero-cost foundation for a personal digital-task agent. The current build is an early prototype, not yet a fully autonomous device-control system.

## Current capabilities

- Streamlit workspace for creating and selecting projects.
- Deterministic built-in task planner; no external AI model is called.
- In-memory project registry (projects reset when the app session ends).
- Action authorization primitives with exact-action approval checks.
- Project creation uses a two-step review/confirm UI and the approval-gated execution gateway.
- ZIP repository inspection utilities with defensive archive validation.
- GitHub Actions CI for Python compilation and automated tests.

## Zero-cost and provider safety

- The application uses `RuleBasedProvider` by default.
- The dashboard does not instantiate or call the OpenAI provider.
- The OpenAI adapter is disabled by default. Its constructor requires both `external_enabled=True` and `paid_cost_approved=True` before it can make a request.
- Environment variables alone cannot enable the external provider.
- No API key is required for the current application.
- Payment, purchase, subscription, paid-service and external-provider action names are denied by the safety gate.
- No payment, purchase, recharge, or paid fallback feature is implemented.

Do not set provider approval flags or add provider credentials for the current zero-cost build.

## Run locally

Requires Python 3.10 or newer.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
streamlit run app.py
```

On Windows, activate the virtual environment with `.venv\\Scripts\\activate`.

## Verify

```bash
python -m compileall -q app.py core tests
python -m pytest -q
```

## Current limitations

- The UI is a Streamlit web prototype; a native Android application has not been built yet.
- Project data is currently stored only in Streamlit session state.
- The planner is deterministic and does not perform real browser, device, email, or file-system actions.
- The authorization module is a policy primitive; it must be wired into a separately reviewed execution engine before real actions are enabled.
- External provider support is an optional future extension and must remain disabled unless the user explicitly opts in and separately approves the specific provider and cost.

## Development rules

1. Keep the default build free and offline.
2. Never implement payment or purchase execution.
3. Require specific user approval for each consequential action.
4. Keep external providers disabled by default; no automatic paid fallback.
5. Do not merge a pull request until CI and the security review are complete.
6. Build and test on a feature branch before considering changes to `main`.

## Current development branch

`feature/agent-v0.3-zero-cost-core`

The active work is tracked in [Pull Request #2](https://github.com/glad4u7-crypto/TLP-Write-Test/pull/2). It remains a draft and is not merged.
