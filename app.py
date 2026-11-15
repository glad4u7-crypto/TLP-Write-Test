import hashlib
import hmac
import os
import secrets
import sqlite3
import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError

from core.brain import AIBrain
from core.projects import ProjectRegistry
from core.persistent_projects import PersistentProjectRegistry
from core.sqlite_project_store import SQLiteProjectStore
from core.approvals import ApprovalAuthority
from core.audit import JsonlAuditLog
from core.project_actions import build_project_gateway
from core.providers.rule_based import RuleBasedProvider
from core.streamlit_auth import principal_from_oidc_claims
from core.identity import AuthorizationDenied
from core.session_security import bind_session_identity, clear_session_identity
from core.storage import TenantKey
from core.sqlite_security_store import SQLiteSecurityStore, SQLiteExecutionAuditLog

st.set_page_config(page_title="Autonomous AI Agent", page_icon="🤖", layout="wide")
st.title("Autonomous AI Agent")
st.caption("Version 0.4.0 · Zero-cost core + Project Manager")

# OIDC is optional for local single-user development, but deployments should
# set [apaa].require_auth = true in secrets.toml. Never accept identity from UI input.
try:
    apaa_settings = st.secrets.get("apaa", {})
    auth_configured = "auth" in st.secrets
except StreamlitSecretNotFoundError:
    # AppTest and local development may intentionally run without secrets.toml.
    apaa_settings = {}
    auth_configured = False
auth_required = bool(apaa_settings.get("require_auth", False))

if auth_required:
    if not auth_configured:
        st.error(
            "Authentication is required, but no [auth] OIDC configuration was found. "
            "Configure .streamlit/secrets.toml before using this deployment."
        )
        st.stop()
    if not st.user.is_logged_in:
        # Authentication loss/expiry is a session boundary just like explicit
        # logout. Do not retain capabilities or private drafts while signed out.
        clear_session_identity(st.session_state)
        st.warning("Sign in with the configured OpenID Connect provider to continue.")
        st.button("Log in", on_click=st.login, type="primary")
        st.stop()
    try:
        oidc_claims = st.user.to_dict()
        principal = principal_from_oidc_claims(oidc_claims)
    except (ValueError, PermissionError) as exc:
        # Invalid/expired claims must not leave a prior authenticated context
        # available if this browser session later authenticates again.
        clear_session_identity(st.session_state)
        st.error(f"Authentication could not be verified: {exc}")
        st.stop()
    st.sidebar.success(f"Signed in · {principal.subject}")
    def _logout_and_clear_session_state():
        clear_session_identity(st.session_state)
        st.logout()

    st.sidebar.button("Log out", on_click=_logout_and_clear_session_state)
else:
    principal = None
    st.warning(
        "Local prototype mode: authentication is not enforced. "
        "Do not expose this instance publicly. Set [apaa].require_auth = true "
        "after configuring OIDC."
    )

# Clear identity-bound drafts, approval authority and gateway if a different
# authenticated account starts using this same Streamlit session.
session_identity = f"{principal.issuer}\\n{principal.subject}" if principal is not None else "local-prototype"
bind_session_identity(st.session_state, session_identity)
if "approval_session_scope" not in st.session_state:
    st.session_state["approval_session_scope"] = secrets.token_urlsafe(32)

if "project_registry" not in st.session_state:
    st.session_state["project_registry"] = ProjectRegistry()
if "selected_project_id" not in st.session_state:
    st.session_state["selected_project_id"] = ""

registry = st.session_state["project_registry"]

# Keep the approval authority and gateway server-side in this Streamlit session.
# The planner/task text never receives either object.
tenant = TenantKey(principal.issuer, principal.subject) if principal is not None else None
if principal is not None:
    # Authenticated deployments must explicitly configure a protected stable
    # secret. Never silently fall back to an ephemeral in-memory authority.
    try:
        signing_secret_hex = apaa_settings.get("approval_signing_secret_hex", "")
        signing_secret = bytes.fromhex(signing_secret_hex) if isinstance(signing_secret_hex, str) else b""
        if len(signing_secret) < 32:
            raise ValueError("approval_signing_secret_hex must decode to at least 32 bytes.")
        security_db_path = apaa_settings.get(
            "security_db_path", ".apaa_security/security.sqlite3"
        )
        project_db_path = apaa_settings.get(
            "project_db_path", ".apaa_projects/projects.sqlite3"
        )
        security_store = SQLiteSecurityStore(security_db_path)
        project_store = SQLiteProjectStore(project_db_path)
    except (ValueError, OSError, TypeError, sqlite3.Error) as exc:
        # A failed durable-store startup must not leave capabilities or
        # tenant-bound objects from an earlier successful run in this session.
        # Clear all identity-bound state so a later retry starts from a clean
        # authenticated context rather than reusing stale authority/gateway.
        clear_session_identity(st.session_state)
        st.error(f"Durable security storage is not configured safely: {exc}")
        st.stop()
    # Bind cached approval capabilities to the active signing secret and
    # durable nonce-store location. Keep only a keyed, non-reversible identifier
    # in session state; never retain or log the signing secret itself.
    authority_config_material = (
        "apaa-approval-authority-config-v1\\n"
        + os.path.abspath(os.fspath(security_db_path))
    ).encode("utf-8")
    authority_config_id = hmac.new(
        signing_secret, authority_config_material, hashlib.sha256
    ).hexdigest()
    if st.session_state.get("approval_authority_config_id") != authority_config_id:
        # Secret or nonce-store rotation invalidates receipts from the prior
        # configuration, even if the new store has never seen their nonces.
        st.session_state.pop("approval_authority", None)
        st.session_state.pop("execution_gateway", None)
        st.session_state.pop("execution_gateway_owner", None)
        st.session_state["approval_session_scope"] = secrets.token_urlsafe(32)
        st.session_state["approval_authority_config_id"] = authority_config_id
    if "approval_authority" not in st.session_state:
        st.session_state["approval_authority"] = ApprovalAuthority(
            nonce_store=security_store, signing_secret=signing_secret
        )
    audit_log = SQLiteExecutionAuditLog(security_store, tenant)
    if (
        "project_registry" not in st.session_state
        or st.session_state.get("project_registry_tenant") != session_identity
    ):
        st.session_state["project_registry"] = PersistentProjectRegistry(project_store, tenant)
        st.session_state["project_registry_tenant"] = session_identity
else:
    if "approval_authority" not in st.session_state:
        st.session_state["approval_authority"] = ApprovalAuthority()
    audit_log = JsonlAuditLog(".apaa_audit/execution.jsonl")
    if "project_registry" not in st.session_state:
        st.session_state["project_registry"] = ProjectRegistry()
    st.session_state["project_registry_tenant"] = "local-prototype"
if "selected_project_id" not in st.session_state:
    st.session_state["selected_project_id"] = ""

registry = st.session_state["project_registry"]
gateway_owner = (
    f"{principal.issuer}\\n{principal.subject}"
    if principal is not None else "local-prototype"
)
if (
    "execution_gateway" not in st.session_state
    or st.session_state.get("execution_gateway_owner") != gateway_owner
):
    st.session_state["execution_gateway"] = build_project_gateway(
        registry,
        st.session_state["approval_authority"],
        audit_log=audit_log,
        principal=principal,
        session_scope=st.session_state["approval_session_scope"],
    )
    st.session_state["execution_gateway_owner"] = gateway_owner

def visible_projects():
    if principal is not None:
        return registry.list_projects_for_owner(principal)
    return [
        project for project in registry.list_projects()
        if project.owner_subject == "local-prototype"
    ]

def visible_project(project_id):
    if principal is not None:
        try:
            return registry.get_for_owner(project_id, principal)
        except AuthorizationDenied:
            return None
    project = registry.get(project_id)
    return project if project and project.owner_subject == "local-prototype" else None

st.info(
    "Zero-cost mode is active. The built-in planner is deterministic and "
    "does not call an external AI API. No paid service is configured."
)

with st.sidebar:
    st.subheader("Workspace")
    projects = visible_projects()
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
        selected = visible_project(selected_id)
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
st.caption("Authenticated projects are saved in tenant-scoped SQLite storage. Local prototype projects remain session-only.")
with st.form("prepare_project_form", clear_on_submit=True):
    project_name = st.text_input("Project name", max_chars=80)
    project_description = st.text_area("Project description", max_chars=500)
    prepare_project = st.form_submit_button("Review project details")

if prepare_project:
    if not project_name.strip():
        st.error("Project name must not be empty.")
    elif len(project_name.strip()) > 80 or len(project_description.strip()) > 500:
        st.error("Project details exceed the allowed length.")
    else:
        st.session_state["pending_project"] = {
            "name": project_name.strip(),
            "description": project_description.strip(),
        }

pending_project = st.session_state.get("pending_project")
if pending_project:
    st.subheader("Review before creating")
    st.write(f"**Project name:** {pending_project['name']}")
    st.write(f"**Description:** {pending_project['description'] or 'No description'}")
    st.warning("The project will be created only after you explicitly confirm these exact details.")
    confirm_col, cancel_col = st.columns(2)
    with confirm_col:
        confirm_project = st.button("Confirm and create project", type="primary")
    with cancel_col:
        cancel_project = st.button("Cancel")
    if cancel_project:
        st.session_state.pop("pending_project", None)
        st.rerun()
    if confirm_project:
        # Only this explicit UI event can issue the short-lived receipt.
        payload = {
            "name": pending_project["name"],
            "description": pending_project["description"],
        }
        receipt = st.session_state["approval_authority"].issue(
            "create_project", payload, tenant=tenant,
            session_scope=st.session_state["approval_session_scope"]
        )
        result = st.session_state["execution_gateway"].execute(
            "create_project",
            payload,
            approval_receipt=receipt,
            tenant=tenant,
        )
        if result.executed:
            project = result.output
            st.session_state["selected_project_id"] = project.project_id
            st.session_state.pop("pending_project", None)
            st.success(f"Created project through the approval gateway: {project.name}")
            st.rerun()
        else:
            st.error(result.reason)

if visible_projects():
    selected = visible_project(st.session_state["selected_project_id"])
    if selected:
        st.write(f"**Selected project:** {selected.name}")
        st.write(selected.description or "No description provided.")
        st.caption(f"Project ID: {selected.project_id}")
else:
    st.write("Create your first project to start organizing agent tasks.")

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
