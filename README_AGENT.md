# Autonomous AI Agent

**Version:** 0.4.0 (zero-cost foundation)  
**Status:** Development branch; not production-ready.

A reusable general-purpose agent workspace. TradeLab Pro can later be connected as one separately managed project.

## Zero-cost policy

The default application uses a deterministic built-in planner. It requires no API key, makes no external model requests, and does not require a paid service.

- No OpenAI API calls.
- No Gemini or other external AI API calls in the current mode.
- No paid hosting, GPU, credits, or auto-recharge.
- No automatic switch to a paid provider.
- If a free platform limit is reached, the workflow must pause rather than incur a charge.

Future provider integrations may be added behind the existing provider interface, but they must remain disabled by default and require explicit user opt-in. Paid providers additionally require separate explicit cost approval.

## Current features

- Streamlit agent dashboard.
- Session-based Project Manager: create, list, and select projects.
- Deterministic offline task planner.
- Provider-neutral interface reserved for future opt-in integrations.
- Explicit approval policy foundation for mutating actions.

**Project storage note:** Projects currently live only in the active Streamlit session. They are not yet durable across a new session, browser reset, or app restart. This avoids a paid database dependency.

## Run locally

    python -m pip install -r requirements.txt
    streamlit run app.py

## Test

    python -m pytest -q

## Current safety limits

- The built-in planner is not a generative LLM.
- No network model requests are made by the default dashboard.
- No autonomous shell/code execution, GitHub writes, or external project mutations.
- No credentials are required or committed.
- Future external mutations require explicit approval and an audit record.
- Work is developed on a feature branch and reviewed before merging.

See docs/ARCHITECTURE.md for scope and roadmap.
