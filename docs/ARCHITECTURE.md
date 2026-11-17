# Autonomous AI Agent — Architecture (v0.2.0 preview)

## Product boundary
This repository contains a reusable, general-purpose agent application. TradeLab Pro is a separately managed project and may later be connected as one project workspace.

## Implemented foundation
- Streamlit dashboard shell (app.py).
- Task and status models (core/models.py).
- Deterministic starter planner (core/planner.py).
- Explicit approval gate for mutating actions (core/safety.py).
- AI Brain orchestration layer (core/brain.py).
- Provider-neutral ModelProvider contract (core/providers/base.py).
- First provider adapter: OpenAI Responses API using Python standard-library HTTP (core/providers/openai_responses.py).
- Unit tests, compile check, and a dedicated GitHub Actions workflow.

## AI provider boundary
The dashboard sends a model request only after a user presses Ask AI Brain. The API key is read from OPENAI_API_KEY at runtime or Streamlit Secrets; AGENT_MODEL optionally selects the model and defaults to gpt-6-luna. The key must never be committed. Provider errors are sanitized so response bodies and credentials are not exposed in the UI. The Brain depends only on the provider contract, not on a specific vendor adapter.

## Safety boundary
The AI Brain generates text and planning suggestions only. This version does not execute shell commands, invoke agent tools, modify other repositories, or merge pull requests. Any future external mutation must pass an explicit approval gate and be audited.

## Next modules
Additional provider adapters, project connectors, tool registry, persistent memory, execution queue, audit log, and approval UI. Each must be introduced with tests and documented permissions.
