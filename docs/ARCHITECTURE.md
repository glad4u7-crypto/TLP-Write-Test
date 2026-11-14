# Autonomous AI Agent — Architecture (v0.3.0 zero-cost core)

## Product boundary

This repository contains a reusable general-purpose agent application. TradeLab Pro remains a separately managed project and may later be connected as one project workspace.

## Zero-cost default

- The dashboard uses the built-in deterministic RuleBasedProvider.
- The default provider performs no network requests and requires no API key.
- OpenAI, Gemini, and all other external model providers are not invoked by the current application.
- The application must never switch to a paid provider automatically.
- When free platform quotas or resource limits are reached, work must pause safely; no paid upgrade, credit purchase, or auto-recharge is permitted.

## Provider extension point

The ModelProvider protocol remains the stable interface for future provider choices. New adapters may be developed later to give the user more control over model choice and capabilities. They must be separate modules, disabled by default, and require explicit user opt-in before any external data transfer. A paid provider additionally requires a separate explicit cost approval. No provider is activated merely because credentials happen to exist in an environment.

The previous OpenAI adapter is retained only as dormant historical/extension code. The current dashboard does not import or call it.

## Implemented foundation

- Streamlit dashboard shell with zero-cost default (app.py).
- Task and status models (core/models.py).
- Deterministic starter planner (core/planner.py).
- Explicit approval gate for mutating actions (core/safety.py).
- AI Brain orchestration layer (core/brain.py).
- Provider-neutral ModelProvider contract (core/providers/base.py).
- Built-in offline RuleBasedProvider (core/providers/rule_based.py).
- Unit tests, compile check, and dedicated GitHub Actions workflow.

## Safety boundary

The built-in planner generates deterministic planning text only. This version does not execute shell commands, invoke external model APIs, modify other repositories, or merge pull requests. Any future external mutation must pass an explicit approval gate and be audited.

## Next modules

Project manager, repository inspector, tool registry, persistent memory, execution queue, audit log, and approval UI. Each must be introduced with tests, least-privilege permissions, and documented zero-cost constraints.
