import os

import streamlit as st

from core.brain import AIBrain
from core.providers.openai_responses import OpenAIResponsesProvider, ProviderError


def get_setting(name: str, default: str = "") -> str:
    value = os.getenv(name)
    if value:
        return value.strip()
    try:
        return str(st.secrets.get(name, default)).strip()
    except Exception:
        return default


st.set_page_config(page_title="Autonomous AI Agent", page_icon="🤖", layout="wide")
st.title("Autonomous AI Agent")
st.caption("Version 0.2.0 · AI Brain integration preview")
st.info("The AI Brain can answer and help plan. It cannot execute tools or modify projects in this version.")
api_key = get_setting("OPENAI_API_KEY")
model_name = get_setting("AGENT_MODEL", "gpt-6-luna")
with st.sidebar:
    st.subheader("Workspace")
    st.write("No project connected yet.")
    st.subheader("AI Provider")
    st.write("OpenAI Responses API")
    st.write("Model: " + model_name)
    st.write("API key: " + ("Configured" if api_key else "Not configured"))
    st.subheader("Safety")
    st.success("External execution disabled")

st.subheader("Task workspace")
task = st.text_area("Describe a task", placeholder="Example: Review a Python project and suggest a safe implementation plan.")
prepare_col, ask_col = st.columns(2)
with prepare_col:
    if st.button("Prepare task", type="secondary", disabled=not task.strip()):
        st.session_state["draft_task"] = task.strip()
        st.success("Task draft saved in this session. No external actions were executed.")
with ask_col:
    if st.button("Ask AI Brain", type="primary", disabled=not task.strip()):
        if not api_key:
            st.warning("Set OPENAI_API_KEY in the application environment or Streamlit Secrets before using the AI Brain.")
        else:
            try:
                brain = AIBrain(OpenAIResponsesProvider(api_key=api_key, model=model_name))
                with st.spinner("Generating a response..."):
                    st.session_state["brain_response"] = brain.respond(task)
            except ProviderError as exc:
                st.error(str(exc))

if st.session_state.get("draft_task"):
    st.write("**Prepared task**")
    st.write(st.session_state["draft_task"])
if st.session_state.get("brain_response"):
    st.subheader("AI Brain response")
    st.markdown(st.session_state["brain_response"])
st.caption("AI requests are sent only when you press Ask AI Brain. API usage may incur charges.")
