# Autonomous AI Agent

**Version:** 0.2.0 (AI Brain integration preview)  
**Status:** Development branch; not production-ready.

A reusable agent workspace intended to support multiple projects, with TradeLab Pro as one possible connected project.

## Run locally

    python -m pip install -r requirements.txt
    streamlit run app.py

## Configure the AI provider

Set OPENAI_API_KEY in the runtime environment. Optionally set AGENT_MODEL (default: gpt-6-luna). Never commit API keys or place them in source code. In Streamlit Community Cloud, add the key through the app's Secrets settings.

The dashboard sends a request only after the user presses **Ask AI Brain**. API usage may incur charges. The integration uses the OpenAI Responses API and Python standard-library HTTP support; no extra SDK dependency is required.

## Test

    python -m pytest -q

## Current safety limits

- The AI Brain can generate text and planning suggestions only.
- No autonomous shell/code execution, GitHub writes, or external project mutations.
- No credentials committed.
- External mutations require a future explicit approval and execution layer.
- Work is developed on a feature branch and reviewed before merging.

See docs/ARCHITECTURE.md for scope and roadmap.
