# Autonomous AI Agent — Architecture (v0.1.0)

## Product boundary
This repository contains a reusable, general-purpose agent application. TradeLab Pro is a separately managed project and is not embedded in this codebase.

## v0.1 foundation
- Streamlit dashboard shell (app.py).
- Dependency-free task and status models (core/models.py).
- Deterministic starter planner (core/planner.py).
- Explicit approval gate for mutating actions (core/safety.py).
- Automated unit tests and a dedicated GitHub Actions workflow.

## Safety boundary
Version 0.1 does not execute shell commands, call external APIs, modify other repositories, store credentials, or autonomously merge pull requests. The dashboard only prepares a task draft in the current session. Mutating actions require explicit user approval in a future execution layer.

## Planned modules
Project connectors, tool registry, memory, model provider adapter, execution queue, audit log, and approval UI are future steps and must be introduced with tests and documented permissions.
