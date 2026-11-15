# Autonomous AI Agent — Architecture (v0.4.0 zero-cost foundation)

## Product boundary

This repository contains a reusable general-purpose agent application. TradeLab Pro remains a separately managed project and may later be connected as one project workspace.

## Zero-cost default

- The dashboard uses the built-in deterministic RuleBasedProvider.
- The default provider performs no network requests and requires no API key.
- OpenAI, Gemini, and all other external model providers are not invoked by the current application.
- The application must never switch to a paid provider automatically.
- When free platform quotas or resource limits are reached, the workflow must pause safely; no paid upgrade, credit purchase, or auto-recharge is permitted.

## Provider extension point

The ModelProvider protocol remains the stable interface for future provider choices. New adapters may be developed later to give the user more control over model choice and capabilities. They must be separate modules, disabled by default, and require explicit user opt-in before any external data transfer. A paid provider additionally requires a separate explicit cost approval. No provider is activated merely because credentials happen to exist in an environment.

The OpenAI adapter is dormant extension code. The current dashboard imports and calls only RuleBasedProvider.

## Implemented foundation

- Streamlit dashboard shell with zero-cost default (app.py).
- Task and status models (core/models.py).
- Deterministic starter planner (core/planner.py).
- Explicit approval gate for mutating actions (core/safety.py).
- HMAC-signed, short-lived, payload-bound approval receipts (core/approvals.py).
- Payload-free, in-memory execution audit events (core/audit.py), emitted by the gateway.
- Auto-Run allowlist is fixed at trusted gateway construction and empty by default; task calls cannot supply their own allowlist.
- Project creation routed through a trusted controller and ExecutionGateway after UI confirmation (core/project_actions.py).
- AI Brain orchestration layer (core/brain.py).
- Provider-neutral ModelProvider contract (core/providers/base.py).
- Built-in offline RuleBasedProvider (core/providers/rule_based.py).
- Project model and in-memory CRUD registry (core/projects.py).
- Project Manager UI in Streamlit, scoped to the current browser session.
- Unit tests, compile check, and GitHub Actions workflow.

## Current storage limitation

Projects are held in Streamlit session state. They are not durable across a new session, browser reset, or app restart. This avoids requiring a paid database. A later zero-cost persistence option must be evaluated and tested before being enabled.

## Safety boundary

The built-in planner generates deterministic planning text only. This version does not execute shell commands, invoke external model APIs, modify other repositories, or merge pull requests. Any future external mutation must pass an explicit approval gate and be audited.

## Next modules

Repository Inspector, Tool Registry, persistent memory, execution queue, audit log, and approval UI. Each must be introduced with tests, least-privilege permissions, and documented zero-cost constraints.
