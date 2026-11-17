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

The OpenAI adapter is dormant extension code. The current dashboard imports and calls only RuleBasedProvider. It is not part of the zero-cost execution path and must not be enabled without separate review and approval.

## Implemented foundation

- Streamlit dashboard shell with zero-cost default (app.py).
- Task and status models (core/models.py).
- Deterministic starter planner (core/planner.py).
- Basic safety policy helper (core/safety.py).
- Metadata-only Tool Registry (core/tool_registry.py); no handlers or execution adapters.
- Session-scoped approval queue (core/approval.py) with explicit approve/reject, expiry, payload fingerprint and visible payload preview. Decisions do not execute actions.
- AI Brain orchestration layer (core/brain.py).
- Provider-neutral ModelProvider contract (core/providers/base.py).
- Built-in offline RuleBasedProvider (core/providers/rule_based.py).
- Project model and in-memory CRUD registry (core/projects.py).
- Project Manager UI in Streamlit, scoped to the current browser session.
- Read-only ZIP Repository Inspector with path validation, archive limits, sensitive-file skipping, and pattern-based findings.
- Unit tests, compile check, and GitHub Actions workflow.

## Repository Inspector boundary

The inspector accepts ZIP bytes and reads selected text members in memory. It never extracts files to disk, imports uploaded modules, executes code, calls external services, or persists uploaded content. It rejects unsafe paths, symbolic links, encrypted entries, duplicate file paths, suspicious compression ratios, and archives over configured limits. Sensitive configuration files are skipped. Its findings are heuristic indicators, not proof of vulnerabilities or a complete security audit.

Limits: 10 MB compressed upload, 500 entries, 20 MB total uncompressed size, 256 KB per inspected text file, and maximum compression ratio 100:1.

## Current storage limitation

Projects are held in Streamlit session state. They are not durable across a new session, browser reset, or app restart. This avoids requiring a paid database. A later zero-cost persistence option must be evaluated and tested before being enabled.

## Safety boundary

The built-in planner generates deterministic planning text only. This version does not execute shell commands, invoke external model APIs, modify other repositories, or merge pull requests. Any future external mutation must pass an explicit approval gate and be audited.

## Next modules

Persistent project storage, persistent memory, execution queue, and durable audit log. Any future executor requires a separate threat model, exact typed action contracts, least-privilege permissions, one-time authorization consumption, and independent security review. Tool Registry and the non-executing approval UI now exist as a foundation only.
