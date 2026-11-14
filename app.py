import streamlit as st

from core.brain import AIBrain
from core.providers.rule_based import RuleBasedProvider

st.set_page_config(page_title="Autonomous AI Agent", page_icon="🤖", layout="wide")
st.title("Autonomous AI Agent")
st.caption("Version 0.3.0 · Zero-cost core")

st.info(
    "Zero-cost mode is active. This version uses local deterministic planning "
    "logic and does not call an external AI API."
)

with st.sidebar:
    st.subheader("Workspace")
    st.write("No project connected yet.")
    st.subheader("AI Provider")
    st.write("Built-in rule-based provider")
    st.write("External API: Disabled")
    st.subheader("Safety")
    st.success("No paid API requests")
    st.success("External execution disabled")

st.subheader("Task workspace")
task = st.text_area(
    "Describe a task",
    placeholder="Example: Review a Python project and suggest a safe implementation plan.",
)

if st.button("Prepare free plan", type="primary", disabled=not task.strip()):
    try:
        brain = AIBrain(RuleBasedProvider())
        st.session_state["free_plan"] = brain.respond(task)
        st.session_state["draft_task"] = task.strip()
    except ValueError as exc:
        st.error(str(exc))

if st.session_state.get("draft_task"):
    st.write("**Prepared task**")
    st.write(st.session_state["draft_task"])

if st.session_state.get("free_plan"):
    st.subheader("Built-in planning result")
    st.markdown(st.session_state["free_plan"])

st.caption(
    "No external AI API is configured or called. Future provider integrations "
    "must remain opt-in and must never activate paid services automatically."
)
