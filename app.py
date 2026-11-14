import streamlit as st

from core.brain import AIBrain
from core.projects import ProjectRegistry
from core.providers.rule_based import RuleBasedProvider
from core.repository_inspector import InspectionError, inspect_zip

st.set_page_config(page_title="Autonomous AI Agent", page_icon="🤖", layout="wide")
st.title("Autonomous AI Agent")
st.caption("Version 0.4.0 · Zero-cost core + Project Manager")

if "project_registry" not in st.session_state:
    st.session_state["project_registry"] = ProjectRegistry()
if "selected_project_id" not in st.session_state:
    st.session_state["selected_project_id"] = ""

registry = st.session_state["project_registry"]

st.info(
    "Zero-cost mode is active. The built-in planner is deterministic and "
    "does not call an external AI API. No paid service is configured."
)

with st.sidebar:
    st.subheader("Workspace")
    projects = registry.list_projects()
    if projects:
        project_ids = [project.project_id for project in projects]
        current = st.session_state["selected_project_id"]
        index = project_ids.index(current) if current in project_ids else 0
        selected_id = st.selectbox(
            "Select project",
            options=project_ids,
            index=index,
            format_func=lambda value: registry.get(value).name,
        )
        st.session_state["selected_project_id"] = selected_id
        selected = registry.get(selected_id)
        if selected and selected.description:
            st.caption(selected.description)
    else:
        st.caption("No projects created yet.")

    st.subheader("AI Provider")
    st.write("Built-in rule-based provider")
    st.write("External API: Disabled")
    st.subheader("Safety")
    st.success("No paid API requests")
    st.success("External execution disabled")

st.header("Project Manager")
st.caption("Projects are currently held in this browser session; they are not yet saved permanently.")
with st.form("create_project_form", clear_on_submit=True):
    project_name = st.text_input("Project name", max_chars=80)
    project_description = st.text_area("Project description", max_chars=500)
    create_project = st.form_submit_button("Create project")

if create_project:
    try:
        project = registry.create(project_name, project_description)
        st.session_state["selected_project_id"] = project.project_id
        st.success(f"Created project: {project.name}")
        st.rerun()
    except ValueError as exc:
        st.error(str(exc))

if registry.list_projects():
    selected = registry.get(st.session_state["selected_project_id"])
    if selected:
        st.write(f"**Selected project:** {selected.name}")
        st.write(selected.description or "No description provided.")
        st.caption(f"Project ID: {selected.project_id}")
else:
    st.write("Create your first project to start organizing agent tasks.")

st.divider()
st.header("Repository Inspector")
st.caption(
    "Upload a ZIP archive for local, read-only inspection. Files are not extracted, "
    "executed, uploaded to an external service, or saved permanently."
)
st.warning(
    "Safety limits: ZIP up to 10 MB, at most 500 entries, 20 MB expanded size, "
    "and 256 KB per inspected text file. Sensitive configuration files are skipped."
)
uploaded_zip = st.file_uploader("Choose a repository ZIP file", type=["zip"], key="repository_zip")
if st.button("Inspect repository", disabled=uploaded_zip is None):
    try:
        report = inspect_zip(uploaded_zip.getvalue())
        st.success("Read-only inspection completed.")
        st.write(
            f"**Files:** {report.total_files} · "
            f"**Text files inspected:** {report.text_files} · "
            f"**Files skipped:** {report.skipped_files}"
        )
        st.dataframe(
            [
                {
                    "Path": item.path,
                    "Size (bytes)": item.size_bytes,
                    "Type": item.kind,
                    "Lines": item.line_count if item.line_count is not None else "—",
                }
                for item in report.files
            ],
            use_container_width=True,
        )
        st.subheader("Inspection findings")
        if report.findings:
            for finding in report.findings:
                st.warning(finding)
        else:
            st.info("No configured risk patterns or possible credentials were detected.")
        st.caption(
            "This is a deterministic pattern-based inspection, not a complete security audit. "
            "Findings require human review."
        )
    except InspectionError as exc:
        st.error(str(exc))

st.divider()
st.header("Task Workspace")
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
