import streamlit as st

st.set_page_config(page_title="Autonomous AI Agent", page_icon="🤖", layout="wide")
st.title("Autonomous AI Agent")
st.caption("Version 0.1.0 · Foundation")
st.info("Foundation preview: the agent runtime is read-only in this first version.")
with st.sidebar:
    st.subheader("Workspace")
    st.write("No project connected yet.")
    st.subheader("Safety")
    st.success("Execution disabled by default")
st.subheader("Task workspace")
task = st.text_area("Describe a task", placeholder="Example: Review a Python project and summarize its structure.")
if st.button("Prepare task", type="primary", disabled=not task.strip()):
    st.session_state["draft_task"] = task.strip()
    st.success("Task draft saved in this session. No external actions were executed.")
if st.session_state.get("draft_task"):
    st.write("**Prepared task**")
    st.write(st.session_state["draft_task"])
