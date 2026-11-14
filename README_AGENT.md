# Autonomous AI Agent

**Version:** 0.1.0 (foundation)  
**Status:** Development branch; not production-ready.

A reusable agent workspace intended to support multiple projects, with TradeLab Pro as one possible connected project.

## Run locally

    python -m pip install -r requirements.txt
    streamlit run app.py

## Test

    python -m pytest -q

## Current safety limits

- No autonomous code execution or external writes.
- No credentials committed; use environment variables in a later integration step.
- External mutations require explicit approval.
- Work is developed on a feature branch and reviewed before merging.

See docs/ARCHITECTURE.md for scope and roadmap.
