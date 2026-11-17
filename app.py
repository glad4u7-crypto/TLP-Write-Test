import hashlib
import json
import hmac
import os
import secrets
import sqlite3
import time
import tempfile
from pathlib import Path
import streamlit as st
from core.mobile_ui import apply_mobile_ui
from streamlit.errors import StreamlitSecretNotFoundError

from core.models import Task
from core.planner import PlanStatus, StepCategory, create_structured_plan, task_plan_from_dict
from core.projects import ProjectRegistry
from core.persistent_projects import PersistentProjectRegistry
from core.project_access import ProjectAccessControl
from core.project_access_controller import OwnerProjectAccessController
from core.sqlite_project_store import SQLiteProjectStore
from core.approvals import ApprovalAuthority
from core.audit import JsonlAuditLog
from core.project_actions import build_project_gateway
from core.streamlit_auth import principal_from_oidc_claims
from core.identity import AuthorizationDenied, Principal
from core.session_security import bind_session_identity, clear_session_identity, session_identity_key
from core.storage import TenantKey
from core.personal_diagnostics import inspect_personal_runtime, diagnostics_summary
from core.personal_backup import create_personal_backup, restore_personal_backup, PersonalBackupError
from core.personal_runtime import (
    PERSONAL_OWNER_TENANT,
    load_or_create_approval_signing_key,
    personal_runtime_paths,
)
from core.personal_auth import LocalOwnerAuthStore
from core.read_only_adapters import ReadOnlyAdapterRegistry, ReadOnlyAdapterError
from core.capabilities import ReadCapability, ReadRequest
from core.safe_network_providers import (
    DuckDuckGoSearchProvider,
    PublicWebPageReadProvider,
    YouTubePublicSearchProvider,
    SafeNetworkError,
)
from core.sqlite_security_store import SQLiteSecurityStore, SQLiteExecutionAuditLog
from core.memory import SQLiteMemoryStore
from core.project_checkpoint_access import OwnerProjectCheckpointAccess
from core.ui_mutations import execute_audited_ui_mutation
from core.trusted_identity_directory import SQLiteTrustedIdentityDirectory
from core.global_owner import GlobalOwnerConfigurationError, is_global_owner
from core.global_owner_config import (
    invalidate_owner_bound_session_state,
    load_global_owner_from_settings,
)

st.set_page_config(
    page_title="Autonomous AI Agent",
    page_icon="🤖",
    layout="centered",
    initial_sidebar_state="collapsed",
)
apply_mobile_ui(st)
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
        "Personal local mode: this instance is for one owner on this device. "
        "Remote/LAN access is blocked; keep the app bound to loopback."
    )
    try:
        server_address = str(st.get_option("server.address") or "").strip().lower()
    except Exception:
        server_address = ""
    if server_address not in {"", "localhost", "127.0.0.1", "::1"}:
        st.error("Personal local mode requires a loopback-only Streamlit server address.")
        st.stop()

    # Local Owner authentication is mandatory before any Principal, approval
    # authority, gateway, project, memory or task capability is initialized.
    personal_data_dir = os.environ.get(
        "APAA_PERSONAL_DATA_DIR", str(Path.home() / ".apaa_personal")
    )
    personal_paths = personal_runtime_paths(personal_data_dir)
    try:
        local_owner_auth = LocalOwnerAuthStore(
            personal_paths.owner_auth_db
        )
    except (ValueError, OSError, sqlite3.Error) as exc:
        clear_session_identity(st.session_state)
        st.error(f"Owner authentication storage is not safe: {exc}")
        st.stop()

    now = time.time()
    authenticated_at = st.session_state.get("apaa_local_authenticated_at")
    last_activity = st.session_state.get("apaa_local_last_activity")
    session_expired = (
        authenticated_at is not None
        and last_activity is not None
        and (
            now - float(last_activity) >= 15 * 60
            or now - float(authenticated_at) >= 12 * 60 * 60
        )
    )
    if session_expired:
        clear_session_identity(st.session_state)
        for key in (
            "apaa_local_authenticated_at", "apaa_local_last_activity",
            "approval_session_scope", "approval_authority",
            "execution_gateway", "execution_gateway_owner",
            "pending_project", "structured_task_plan", "structured_task_source",
            "structured_task_clarification", "selected_project_id",
            "project_registry", "project_registry_tenant",
        ):
            st.session_state.pop(key, None)
        st.warning("Your APAA Owner session expired. Sign in again to continue.")

    if not local_owner_auth.is_configured():
        st.warning("First-time Owner setup. Create your private APAA passphrase.")
        with st.form("apaa_owner_first_run_setup"):
            new_owner_passphrase = st.text_input(
                "Create Owner passphrase", type="password", max_chars=1024
            )
            confirm_owner_passphrase = st.text_input(
                "Confirm Owner passphrase", type="password", max_chars=1024
            )
            setup_owner = st.form_submit_button("Create Owner protection")
        if setup_owner:
            try:
                local_owner_auth.configure(
                    new_owner_passphrase, confirm_owner_passphrase
                )
                st.success("Owner protection created. Sign in to open APAA.")
                st.rerun()
            except (ValueError, OSError, sqlite3.Error) as exc:
                st.error(f"Owner protection could not be saved safely: {exc}")
        st.stop()

    if (
        authenticated_at is None
        or last_activity is None
        or session_expired
    ):
        st.warning("APAA is locked. Only the configured Owner can unlock this session.")
        with st.form("apaa_owner_login"):
            owner_passphrase = st.text_input(
                "Owner passphrase", type="password", max_chars=1024
            )
            unlock_owner = st.form_submit_button("Unlock APAA", type="primary")
        if unlock_owner:
            try:
                if local_owner_auth.authenticate(owner_passphrase):
                    st.session_state["apaa_local_authenticated_at"] = now
                    st.session_state["apaa_local_last_activity"] = now
                    # The identity binder creates a fresh approval scope only
                    # after it has cleared any orphaned prior-session state.
                    st.rerun()
                st.error("Owner authentication failed or is temporarily locked.")
            except (ValueError, OSError, sqlite3.Error) as exc:
                st.error(f"Owner authentication could not be completed safely: {exc}")
        st.stop()

    # Refresh idle time only after a request reaches this authenticated gate.
    st.session_state["apaa_local_last_activity"] = now

    def _logout_local_owner():
        try:
            local_owner_auth.record_event("logout")
        except (ValueError, OSError, sqlite3.Error):
            # Logout must still revoke the in-memory session if audit storage fails.
            pass
        clear_session_identity(st.session_state)
        for key in (
            "apaa_local_authenticated_at", "apaa_local_last_activity",
            "approval_session_scope", "approval_authority",
            "execution_gateway", "execution_gateway_owner",
            "pending_project", "structured_task_plan", "structured_task_source",
            "structured_task_clarification", "selected_project_id",
            "project_registry", "project_registry_tenant",
        ):
            st.session_state.pop(key, None)

    st.sidebar.success("Owner session active · local device")
    with st.sidebar.expander("Change Owner passphrase"):
        with st.form("apaa_owner_change_passphrase"):
            current_owner_passphrase = st.text_input(
                "Current Owner passphrase", type="password", max_chars=1024
            )
            replacement_owner_passphrase = st.text_input(
                "New Owner passphrase", type="password", max_chars=1024
            )
            confirm_replacement_passphrase = st.text_input(
                "Confirm new Owner passphrase", type="password", max_chars=1024
            )
            change_owner_passphrase = st.form_submit_button("Change passphrase")
        if change_owner_passphrase:
            try:
                changed = local_owner_auth.change_passphrase(
                    current_owner_passphrase,
                    replacement_owner_passphrase,
                    confirm_replacement_passphrase,
                )
                if changed:
                    clear_session_identity(st.session_state)
                    for key in (
                        "apaa_local_authenticated_at", "apaa_local_last_activity",
                        "approval_session_scope", "approval_authority",
                        "execution_gateway", "execution_gateway_owner",
                    ):
                        st.session_state.pop(key, None)
                    st.success("Owner passphrase changed. Sign in again with the new passphrase.")
                    st.rerun()
                st.error("Passphrase change failed. Check the current passphrase or login lockout.")
            except (ValueError, OSError, sqlite3.Error) as exc:
                st.error(f"Passphrase change could not be completed safely: {exc}")

    with st.sidebar.expander("Owner security events"):
        for event_type, occurred_at in local_owner_auth.list_events(limit=25):
            st.caption(f"{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(occurred_at))} · {event_type}")

    st.sidebar.button("Log out", on_click=_logout_local_owner)


# Clear identity-bound drafts, approval authority and gateway if a different
# authenticated account starts using this same Streamlit session.
session_identity = session_identity_key(principal.issuer, principal.subject) if principal is not None else "local-prototype"
bind_session_identity(st.session_state, session_identity)

# Global-owner provisioning is optional but never inferred from a login.
# Only the server-side [apaa].global_owner mapping is accepted. Invalid
# configuration disables the owner capability without granting a fallback.
global_owner_config = None
global_owner_config_invalid = False
if principal is not None:
    try:
        global_owner_config = load_global_owner_from_settings(apaa_settings)
    except GlobalOwnerConfigurationError:
        global_owner_config_invalid = True
        st.error(
            "Global Owner configuration is invalid. Global administration is "
            "disabled; ordinary project access remains subject to existing ACLs."
        )

# Authenticated deployments are private owner-only instances, not open
# multi-user OIDC applications. A missing or invalid owner binding must stop
# the entire app before any project, memory, or task surface is rendered.
if auth_required:
    if global_owner_config_invalid or global_owner_config is None:
        clear_session_identity(st.session_state)
        st.error(
            "This private APAA instance has no valid owner identity configured. "
            "Access is blocked until the owner issuer and subject are provisioned."
        )
        st.stop()
    if not is_global_owner(principal, global_owner_config):
        clear_session_identity(st.session_state)
        st.error("This APAA instance is private and is available only to its configured owner.")
        st.stop()

# A provisioning change (including removal or invalidation) drops any cached
# owner-only capabilities. The raw owner subject is never stored in session.
global_owner_generation = (
    global_owner_config.generation if global_owner_config is not None else None
)
if "global_owner_generation" in st.session_state:
    if st.session_state["global_owner_generation"] != global_owner_generation:
        invalidate_owner_bound_session_state(st.session_state)
st.session_state["global_owner_generation"] = global_owner_generation

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
        active_security_store = security_store
        project_store = SQLiteProjectStore(project_db_path)
        project_access_control = ProjectAccessControl(project_store)
        project_access_controller = OwnerProjectAccessController(project_access_control)
        # Optional closed-directory enrollment. This is deliberately inert
        # unless the owner explicitly configures an issuer allowlist. Only the
        # Principal produced above by Streamlit's validated OIDC claims enters.
        trusted_identity_issuers = apaa_settings.get("trusted_identity_issuers", [])
        if not isinstance(trusted_identity_issuers, (list, tuple)) or any(
            not isinstance(item, str) or not item.strip()
            for item in trusted_identity_issuers
        ):
            raise ValueError("trusted_identity_issuers must be an explicit list of non-empty issuer URLs.")
        if principal.issuer in trusted_identity_issuers:
            identity_db_path = apaa_settings.get(
                "trusted_identity_directory_db_path", ".apaa_identity/identity.sqlite3"
            )
            trusted_identity_directory = SQLiteTrustedIdentityDirectory(
                identity_db_path, allowed_issuers=set(trusted_identity_issuers)
            )
            if st.session_state.get("trusted_directory_enrolled_session") != session_identity:
                provider_display_label = oidc_claims.get("name")
                if not isinstance(provider_display_label, str):
                    provider_display_label = None
                trusted_identity_directory.record_authenticated_principal(
                    principal, provider_display_label=provider_display_label
                )
                st.session_state["trusted_directory_enrolled_session"] = session_identity
        else:
            trusted_identity_directory = None
        memory_db_path = apaa_settings.get("memory_db_path", ".apaa_memory/memory.sqlite3")
        memory_store = SQLiteMemoryStore(memory_db_path)
        checkpoint_access = OwnerProjectCheckpointAccess(memory_store, project_store, principal)
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
        or getattr(st.session_state.get("project_registry"), "_access_control", None) is None
    ):
        st.session_state["project_registry"] = PersistentProjectRegistry(
            project_store, tenant, access_control=project_access_control
        )
        st.session_state["project_registry_tenant"] = session_identity
else:
    # Personal Edition local runtime: stable owner-only files survive app restarts.
    personal_data_dir = os.environ.get(
        "APAA_PERSONAL_DATA_DIR", str(Path.home() / ".apaa_personal")
    )
    personal_paths = personal_runtime_paths(personal_data_dir)
    try:
        signing_secret = load_or_create_approval_signing_key(personal_paths.data_dir)
        personal_security_store = SQLiteSecurityStore(personal_paths.security_db)
        active_security_store = personal_security_store
        personal_project_store = SQLiteProjectStore(personal_paths.projects_db)
    except (ValueError, OSError, TypeError, sqlite3.Error) as exc:
        clear_session_identity(st.session_state)
        st.error(f"Personal runtime could not start safely: {exc}")
        st.stop()
    tenant = PERSONAL_OWNER_TENANT
    # This Principal is created only by trusted local server code after the
    # loopback-only boundary check; it is not derived from browser/task input
    # and must never be reused for a network-exposed deployment.
    local_owner_principal = Principal(
        subject=tenant.subject, issuer=tenant.issuer, authenticated=True,
        roles=("owner",),
    )
    try:
        memory_store = SQLiteMemoryStore(personal_paths.memory_db)
        checkpoint_access = OwnerProjectCheckpointAccess(
            memory_store, personal_project_store, local_owner_principal
        )
    except (ValueError, OSError, TypeError, sqlite3.Error, PermissionError) as exc:
        clear_session_identity(st.session_state)
        st.error(f"Personal memory storage could not start safely: {exc}")
        st.stop()
    authority_config_material = (
        "apaa-personal-approval-authority-v1\\n"
        + os.path.abspath(os.fspath(personal_paths.security_db))
    ).encode("utf-8")
    authority_config_id = hmac.new(
        signing_secret, authority_config_material, hashlib.sha256
    ).hexdigest()
    if st.session_state.get("approval_authority_config_id") != authority_config_id:
        st.session_state.pop("approval_authority", None)
        st.session_state.pop("execution_gateway", None)
        st.session_state.pop("execution_gateway_owner", None)
        st.session_state["approval_session_scope"] = secrets.token_urlsafe(32)
        st.session_state["approval_authority_config_id"] = authority_config_id
    if "approval_authority" not in st.session_state:
        st.session_state["approval_authority"] = ApprovalAuthority(
            nonce_store=personal_security_store, signing_secret=signing_secret
        )
    audit_log = SQLiteExecutionAuditLog(personal_security_store, tenant)
    if (
        "project_registry" not in st.session_state
        or st.session_state.get("project_registry_tenant") != "personal-local-owner"
        or not isinstance(st.session_state.get("project_registry"), PersistentProjectRegistry)
    ):
        st.session_state["project_registry"] = PersistentProjectRegistry(
            personal_project_store, tenant
        )
        st.session_state["project_registry_tenant"] = "personal-local-owner"

if "selected_project_id" not in st.session_state:
    st.session_state["selected_project_id"] = ""

registry = st.session_state["project_registry"]
# Checkpoint UI uses the identity created by trusted OIDC middleware or by the
# loopback-only local runtime; never derive this principal from client input.
checkpoint_principal = principal if principal is not None else local_owner_principal
gateway_owner = session_identity
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
        idempotency_store=active_security_store,
    )
    st.session_state["execution_gateway_owner"] = gateway_owner

def visible_projects():
    if principal is not None:
        return registry.list_projects_for_principal(principal)
    return [
        project for project in registry.list_projects()
        if project.owner_subject == PERSONAL_OWNER_TENANT.subject
        and project.owner_issuer == PERSONAL_OWNER_TENANT.issuer
    ]

def visible_project(project_id):
    if principal is not None:
        try:
            return registry.get_for_principal(project_id, principal)
        except AuthorizationDenied:
            return None
    project = registry.get(project_id)
    return (
        project
        if project
        and project.owner_subject == PERSONAL_OWNER_TENANT.subject
        and project.owner_issuer == PERSONAL_OWNER_TENANT.issuer
        else None
    )

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
            format_func=lambda value: next(project.name for project in projects if project.project_id == value),
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

    if not auth_required:
        with st.expander("Personal Runtime Health", expanded=False):
            st.caption(
                "Read-only preflight for this device's private APAA data. "
                "It never creates, repairs, or changes databases or keys."
            )
            if st.button("Run local health checks", key="apaa_run_local_diagnostics_button"):
                st.session_state["apaa_show_local_diagnostics"] = True
            if st.session_state.get("apaa_show_local_diagnostics"):
                try:
                    diagnostic_results = inspect_personal_runtime(personal_data_dir)
                    passed, failed, info = diagnostics_summary(diagnostic_results)
                    metric_cols = st.columns(3)
                    metric_cols[0].metric("PASS", passed)
                    metric_cols[1].metric("FAIL", failed)
                    metric_cols[2].metric("INFO", info)
                    for diagnostic in diagnostic_results:
                        message = f"{diagnostic.code}: {diagnostic.detail}"
                        if diagnostic.status == "PASS":
                            st.success(message)
                        elif diagnostic.status == "FAIL":
                            st.error(message)
                        else:
                            st.info(message)
                    if failed:
                        st.warning(
                            "One or more local runtime checks failed. APAA will not "
                            "automatically repair protected data; investigate before continuing."
                        )
                except (OSError, ValueError, sqlite3.Error) as exc:
                    st.error(f"Local diagnostics could not complete safely: {exc}")

    if not auth_required:
        with st.expander("Personal Backup & Restore", expanded=False):
            st.caption(
                "Create an owner-private snapshot or validate a backup into a new "
                "directory. Restore never overwrites the live data directory."
            )
            if st.button("Create backup", key="apaa_create_personal_backup"):
                try:
                    backup_parent = Path(personal_data_dir).expanduser().absolute().parent
                    with tempfile.TemporaryDirectory(
                        prefix=".apaa-backup-download-", dir=str(backup_parent)
                    ) as temporary_directory:
                        backup_file = Path(temporary_directory) / "apaa-personal-backup.zip"
                        create_personal_backup(personal_data_dir, backup_file)
                        backup_bytes = backup_file.read_bytes()
                    st.download_button(
                        "Download APAA backup",
                        data=backup_bytes,
                        file_name=f"apaa-personal-backup-{time.strftime('%Y%m%d-%H%M%S')}.zip",
                        mime="application/zip",
                        key="apaa_download_personal_backup",
                    )
                    st.warning(
                        "This archive contains private Owner data and is not encrypted. "
                        "Keep it in a private location; never share or upload it publicly. "
                        "The approval signing key is excluded."
                    )
                except (PersonalBackupError, OSError, ValueError, sqlite3.Error) as exc:
                    st.error(f"Backup could not be created safely: {exc}")

            uploaded_backup = st.file_uploader(
                "Choose an APAA backup archive",
                type=["zip"],
                key="apaa_restore_backup_upload",
            )
            if st.button(
                "Validate and restore into a new directory",
                key="apaa_restore_personal_backup",
                disabled=uploaded_backup is None,
            ):
                temporary_archive = None
                try:
                    if uploaded_backup is None:
                        st.error("Select a backup archive first.")
                    elif uploaded_backup.size > 512 * 1024 * 1024:
                        st.error("Backup archive exceeds the 512 MiB safety limit.")
                    else:
                        restore_parent = Path(personal_data_dir).expanduser().absolute().parent
                        with tempfile.NamedTemporaryFile(
                            prefix=".apaa-restore-upload-", suffix=".zip",
                            dir=str(restore_parent), delete=False,
                        ) as temporary_file:
                            temporary_archive = Path(temporary_file.name)
                            os.chmod(temporary_archive, 0o600)
                            temporary_file.write(uploaded_backup.getvalue())
                            temporary_file.flush()
                            os.fsync(temporary_file.fileno())
                        restored_directory = restore_parent / (
                            f"{Path(personal_data_dir).name}-restored-"
                            f"{int(time.time())}-{secrets.token_hex(4)}"
                        )
                        restore_personal_backup(temporary_archive, restored_directory)
                        st.success(
                            f"Backup verified and restored to a new private directory: "
                            f"{restored_directory}"
                        )
                        st.info(
                            "To use this restored copy, stop APAA first, then restart it "
                            "with APAA_PERSONAL_DATA_DIR set to the restored directory. "
                            "The current live data directory was not replaced."
                        )
                except (PersonalBackupError, OSError, ValueError, sqlite3.Error) as exc:
                    st.error(f"Restore was rejected safely: {exc}")
                finally:
                    if temporary_archive is not None:
                        try:
                            temporary_archive.unlink(missing_ok=True)
                        except OSError:
                            st.error("Temporary restore upload could not be removed; inspect the private data-directory parent.")

    with st.expander("Action history"):
        try:
            recent_actions = audit_log.list_recent_events(limit=25)
            if not recent_actions:
                st.caption("No audited actions have been recorded yet.")
            else:
                st.caption("Recent owner actions · audit hash chain verified")
                for event in recent_actions:
                    st.caption(
                        f"#{event['sequence']} · {event['timestamp']} · "
                        f"{event['action']} · {event['result']} · {event['reason_code']}"
                    )
        except (ValueError, OSError, sqlite3.Error) as exc:
            st.error(
                "Action history integrity could not be verified. "
                "New mutations remain fail-closed."
            )

    with st.expander("Owner Recovery · unresolved actions"):
        st.caption(
            "Read-only review of unresolved execution records. Pending actions "
            "are never retried or automatically classified. Only an uncertain "
            "record can be reconciled after your explicit confirmation."
        )
        try:
            unresolved = active_security_store.list_unresolved_executions(
                tenant, limit=25
            )
            if not unresolved:
                st.caption("No unresolved execution records.")
            else:
                for recovery_item in unresolved:
                    request_key = recovery_item["request_key"]
                    st.markdown(
                        f"**{recovery_item['action']}** · "
                        f"{recovery_item['status']}"
                    )
                    st.caption(
                        f"Created: {recovery_item['created_at']} · "
                        f"Updated: {recovery_item['updated_at']} · "
                        f"Reference: {request_key[:12]}"
                    )
                    if recovery_item["status"] == "pending":
                        st.warning(
                            "Outcome is still pending/unknown. This record cannot "
                            "be reconciled here; inspect the external system first."
                        )
                    elif recovery_item["status"] == "uncertain":
                        confirmed = st.checkbox(
                            "I reviewed the external outcome and confirm this decision",
                            key=f"owner_recovery_confirm_{request_key}",
                        )
                        left, right = st.columns(2)
                        with left:
                            mark_completed = st.button(
                                "Confirm completed",
                                key=f"owner_recovery_done_{request_key}",
                                disabled=not confirmed,
                            )
                        with right:
                            mark_cancelled = st.button(
                                "Confirm cancelled",
                                key=f"owner_recovery_cancel_{request_key}",
                                disabled=not confirmed,
                            )
                        if mark_completed or mark_cancelled:
                            resolution = "completed" if mark_completed else "cancelled"
                            try:
                                changed = active_security_store.resolve_uncertain_execution(
                                    tenant, request_key, resolution,
                                    owner_confirmed=True,
                                )
                                if changed:
                                    st.success(
                                        f"Owner reconciliation recorded: {resolution}. "
                                        "The action was not re-executed."
                                    )
                                    st.rerun()
                                st.error(
                                    "The record changed or was already reconciled. "
                                    "Refresh the recovery list."
                                )
                            except (ValueError, OSError, sqlite3.Error) as exc:
                                st.error(
                                    "Recovery could not be recorded safely. "
                                    f"No retry was attempted: {exc}"
                                )
                    st.divider()
        except (ValueError, OSError, sqlite3.Error) as exc:
            st.error(
                "Owner recovery records could not be verified. "
                "Reconciliation is disabled."
            )

    with st.expander("Public Web Research · Read-only"):
        st.caption(
            "Authenticated APAA-session public research only. Uses direct HTTPS and bounded "
            "text extraction. No login, cookies, browser automation, uploads, "
            "playlist changes, or website actions."
        )
        with st.form("apaa_public_readonly_research"):
            research_provider = st.selectbox(
                "Read-only provider",
                (
                    "Web Search · DuckDuckGo",
                    "Read public HTTPS page",
                    "YouTube public search",
                ),
            )
            research_input = st.text_input(
                "Search query or HTTPS page URL",
                max_chars=2048,
                help="For page reading, enter one public HTTPS URL. Private/local addresses are blocked.",
            )
            research_limit = st.selectbox("Maximum results", (5, 10, 15, 20), index=0)
            run_public_research = st.form_submit_button("Search / Read", type="primary")
        if run_public_research:
            try:
                provider_map = {
                    "Web Search · DuckDuckGo": (
                        ReadCapability.WEB_SEARCH, DuckDuckGoSearchProvider()
                    ),
                    "Read public HTTPS page": (
                        ReadCapability.WEB_PAGE_READ, PublicWebPageReadProvider()
                    ),
                    "YouTube public search": (
                        ReadCapability.YOUTUBE_SEARCH, YouTubePublicSearchProvider()
                    ),
                }
                selected_capability, selected_provider = provider_map[research_provider]
                if selected_capability is ReadCapability.WEB_PAGE_READ:
                    read_request = ReadRequest(
                        selected_capability, target=research_input
                    )
                else:
                    read_request = ReadRequest(
                        selected_capability, query=research_input,
                        max_results=research_limit,
                    )
                readonly_registry = ReadOnlyAdapterRegistry((selected_provider,))
                with st.spinner("Reading public information safely…"):
                    read_result = readonly_registry.read(read_request)
                st.caption(f"Source: {read_result.source_label}")
                if not read_result.items:
                    st.info("No public results were returned.")
                for read_item in read_result.items:
                    st.write(read_item.title)
                    if read_item.excerpt:
                        st.write(read_item.excerpt)
                    st.link_button("Open source", read_item.locator)
                if read_result.truncated:
                    st.caption("Results were bounded; some content may be omitted.")
            except (ValueError, OSError, ReadOnlyAdapterError, SafeNetworkError) as exc:
                st.error(f"Public read-only request blocked or unavailable: {exc}")

# Directory visibility is a separate, explicit consent. It never grants access.
if principal is not None and trusted_identity_directory is not None:
    st.divider()
    st.header("Private identity directory")
    st.caption(
        "This controls whether other authenticated users from the same explicitly "
        "approved OIDC provider may find your account when an owner selects a "
        "read-only project collaborator. It does not share projects or grant access."
    )
    try:
        current_discoverability = trusted_identity_directory.is_discoverable(principal)
        with st.form("identity_discoverability_form"):
            allow_directory_discovery = st.checkbox(
                "Allow project owners to find my account in the private APAA directory",
                value=current_discoverability,
                help=(
                    "Off by default. Only your authenticated identity from the "
                    "same allowlisted OIDC issuer is discoverable; email and tokens "
                    "are not used as identity keys."
                ),
            )
            save_directory_choice = st.form_submit_button("Save directory privacy choice")
        if save_directory_choice:
            trusted_identity_directory.set_discoverability(
                principal, discoverable=allow_directory_discovery
            )
            st.success(
                "Directory privacy choice saved. This does not grant anyone project access."
            )
            st.rerun()
    except (ValueError, PermissionError, LookupError, OSError, sqlite3.Error) as exc:
        st.error(f"Directory privacy setting could not be loaded or saved: {exc}")

# Owner controls are limited to project metadata read grants. No write,
# execution, file, memory, conversation, preference, or checkpoint access is shared.
if principal is not None and trusted_identity_directory is not None:
    owner_projects = registry.list_projects_for_owner(principal)
    if owner_projects:
        st.divider()
        st.header("Owner-controlled read-only project sharing")
        st.caption(
            "Only identities from the same allowlisted OIDC provider that opted "
            "into directory discovery can be selected. A grant exposes project "
            "metadata only; it does not grant editing, execution, files, memory, "
            "conversation history, preferences, or checkpoints."
        )
        selected_share_project = st.selectbox(
            "Project to manage sharing",
            options=[item.project_id for item in owner_projects],
            format_func=lambda value: next(
                item.name for item in owner_projects if item.project_id == value
            ),
            key="owner_share_project_id",
        )
        try:
            selectable_identities = trusted_identity_directory.list_owner_selectable_identities(
                selected_share_project, owner=principal,
                access_control=project_access_control,
            )
            if selectable_identities:
                identity_labels = {
                    item.directory_id: (
                        f"{item.display_label} · {item.directory_id[:8]}"
                        if item.display_label else f"Verified account · {item.directory_id[:8]}"
                    )
                    for item in selectable_identities
                }
                with st.form("owner_project_read_grant_form"):
                    selected_directory_id = st.selectbox(
                        "Opted-in account",
                        options=[item.directory_id for item in selectable_identities],
                        format_func=lambda value: identity_labels[value],
                    )
                    confirm_read_grant = st.checkbox(
                        "I confirm this account may view this project's metadata only"
                    )
                    submit_read_grant = st.form_submit_button(
                        "Grant read-only project access"
                    )
                if submit_read_grant:
                    if not confirm_read_grant:
                        st.error("Confirm the exact read-only permission before granting access.")
                    else:
                        selected_principal = trusted_identity_directory.resolve_owner_selection(
                            selected_share_project, selected_directory_id,
                            owner=principal, access_control=project_access_control,
                        )
                        project_access_controller.grant_read(
                            selected_share_project, actor=principal,
                            grantee=selected_principal,
                        )
                        st.success("Read-only project metadata access granted.")
                        st.rerun()
            else:
                st.caption(
                    "No opted-in identities are available. Other users must sign in "
                    "through the same approved provider and explicitly enable discovery."
                )

            active_grants = [
                grant for grant in project_access_controller.list_grants(
                    selected_share_project, actor=principal
                ) if grant.revoked_at is None
            ]
            if active_grants:
                st.subheader("Active read-only grants")
                revoke_principals = {}
                revoke_labels = {}
                for grant in active_grants:
                    grantee = Principal(
                        subject=grant.grantee_subject,
                        issuer=grant.grantee_issuer,
                        authenticated=True,
                        roles=(),
                    )
                    fingerprint = hashlib.sha256(
                        (repr((grant.grantee_issuer, grant.grantee_subject))).encode("utf-8")
                    ).hexdigest()
                    revoke_principals[fingerprint] = grantee
                    display_label = trusted_identity_directory.owner_grant_display_label(
                        selected_share_project, owner=principal,
                        grantee=grantee, access_control=project_access_control,
                    )
                    revoke_labels[fingerprint] = (
                        f"{display_label} · {fingerprint[:8]}"
                        if display_label else f"Account · {fingerprint[:8]}"
                    )
                with st.form("owner_project_read_revoke_form"):
                    selected_grant_fingerprint = st.selectbox(
                        "Account to revoke",
                        options=list(revoke_principals),
                        format_func=lambda value: revoke_labels[value],
                    )
                    confirm_read_revoke = st.checkbox(
                        "I confirm revoking this account's project metadata access"
                    )
                    submit_read_revoke = st.form_submit_button("Revoke read-only access")
                if submit_read_revoke:
                    if not confirm_read_revoke:
                        st.error("Confirm the exact revocation before continuing.")
                    else:
                        project_access_controller.revoke_read(
                            selected_share_project, actor=principal,
                            grantee=revoke_principals[selected_grant_fingerprint],
                        )
                        st.success("Project read-only access revoked.")
                        st.rerun()
            else:
                st.caption("This project has no active read-only collaborator grants.")
        except (ValueError, PermissionError, LookupError, OSError, sqlite3.Error) as exc:
            st.error(f"Project sharing controls are unavailable: {exc}")

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
            "idempotency_key": secrets.token_hex(24),
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
        idempotency_key = pending_project.get("idempotency_key")
        if not isinstance(idempotency_key, str) or not idempotency_key:
            st.error("This project review has no valid one-time request key. Review the details again.")
            st.stop()
        receipt = st.session_state["approval_authority"].issue(
            "create_project", payload, tenant=tenant,
            session_scope=st.session_state["approval_session_scope"]
        )
        result = st.session_state["execution_gateway"].execute(
            "create_project",
            payload,
            approval_receipt=receipt,
            tenant=tenant,
            idempotency_key=idempotency_key,
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
def execute_owner_ui_mutation(action, approved, payload, operation):
    """Route every Owner UI mutation through payload-bound approval + audit."""
    return execute_audited_ui_mutation(
        audit_log, action, approved, payload, operation,
        approval_authority=st.session_state["approval_authority"],
        tenant=tenant,
        session_scope=st.session_state["approval_session_scope"],
    )


st.header("Task Workspace")
task = st.text_area(
    "Describe a task",
    placeholder="Example: Review a Python project and suggest a safe implementation plan.",
    key="structured_task_input",
)

if st.button("Prepare structured plan", type="primary", disabled=not task.strip()):
    try:
        plan = create_structured_plan(Task(description=task))
        st.session_state["structured_task_plan"] = plan
        st.session_state["structured_task_source"] = plan.task_description
        st.session_state.pop("structured_task_clarification", None)
    except (TypeError, ValueError) as exc:
        st.error(str(exc))

plan = st.session_state.get("structured_task_plan")
if plan is not None:
    st.divider()
    st.subheader("Structured plan review")
    st.caption(f"Plan ID: {plan.plan_id} · Schema: {plan.schema_version}")
    st.write("**Task:** " + plan.task_description)

    if plan.status is PlanStatus.READY:
        st.success("READY · Reviewable plan prepared. Nothing has been executed.")
        selected_plan_project = visible_project(st.session_state.get("selected_project_id", ""))
        if selected_plan_project is not None and memory_store is not None:
            with st.form("save_task_plan_form"):
                save_plan_consent = st.checkbox(
                    "I explicitly approve saving this plan to the selected project"
                )
                save_plan_submit = st.form_submit_button("Save plan to project")
            if save_plan_submit:
                try:
                    execute_owner_ui_mutation(
                        "task_plan.save", save_plan_consent,
                        {
                            "project_id": selected_plan_project.project_id,
                            "plan_id": plan.plan_id,
                            "task_description": plan.task_description,
                            "plan": plan.to_dict(),
                        },
                        lambda payload: memory_store.save_task_plan(
                            tenant, project_id=payload["project_id"],
                            plan_id=payload["plan_id"],
                            task_description=payload["task_description"],
                            plan=payload["plan"], consent=True,
                        ),
                    )
                    st.success("Plan saved to the selected project.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Plan could not be saved: {exc}")
        else:
            st.info("Select an existing project to save this plan across restarts.")
        for step in plan.steps:
            st.markdown(f"**{step.step_id} — {step.title}**")
            st.write(step.purpose)
            st.caption(
                f"Category: {step.category.value.replace('_', ' ').title()} · "
                f"Expected output: {step.expected_output}"
            )
            if step.category is StepCategory.PROPOSED_MUTATION:
                st.warning(
                    "Proposed change only — requires separate, action-specific "
                    "human approval. This screen does not issue approval."
                )
    elif plan.status is PlanStatus.NEEDS_CLARIFICATION:
        st.warning("NEEDS CLARIFICATION · No plan steps were created.")
        for question in plan.clarification_questions:
            st.markdown(f"- {question}")
        clarification = st.text_area(
            "Add the missing details",
            key="structured_task_clarification",
            placeholder="Describe the exact item, desired result, and constraints.",
        )
        if st.button(
            "Prepare updated plan",
            disabled=not clarification.strip(),
        ):
            revised_task = (
                f"{st.session_state['structured_task_source']}. "
                f"Additional clarification: {clarification.strip()}"
            )
            try:
                revised_plan = create_structured_plan(Task(description=revised_task))
                st.session_state["structured_task_plan"] = revised_plan
                st.session_state["structured_task_source"] = revised_plan.task_description
                # Keep the old clarification widget value inert; it is not
                # consulted once the plan is READY and is cleared before a
                # subsequent new task is prepared or at identity boundaries.
                st.rerun()
            except (TypeError, ValueError) as exc:
                st.error(str(exc))
    else:
        st.error("BLOCKED · This request cannot be planned under the current safety policy.")
        for note in plan.safety_notes:
            st.write(f"- {note}")

    if plan.assumptions:
        st.caption("Assumptions: " + "; ".join(plan.assumptions))
    if plan.safety_notes:
        st.caption("Safety boundary")
        for note in plan.safety_notes:
            st.write(f"- {note}")

selected_plan_project = visible_project(st.session_state.get("selected_project_id", ""))
if selected_plan_project is not None and memory_store is not None:
    with st.expander("Saved task plans for this project", expanded=False):
        try:
            saved_plans = memory_store.list_task_plans(
                tenant, project_id=selected_plan_project.project_id, limit=50
            )
            if not saved_plans:
                st.caption("No saved task plans for this project.")
            else:
                saved_plan_ids = [item.plan_id for item in saved_plans]
                selected_saved_plan = st.selectbox(
                    "Choose a saved plan",
                    options=saved_plan_ids,
                    format_func=lambda value: next(
                        f"{item.task_description[:90]} · {item.updated_at[:19]}"
                        for item in saved_plans if item.plan_id == value
                    ),
                    key="apaa_saved_task_plan_selector",
                )
                if st.button("Load saved plan", key="apaa_load_saved_task_plan"):
                    saved_record = next(
                        item for item in saved_plans if item.plan_id == selected_saved_plan
                    )
                    try:
                        restored_plan = task_plan_from_dict(json.loads(saved_record.plan_json))
                        st.session_state["structured_task_plan"] = restored_plan
                        st.session_state["structured_task_source"] = restored_plan.task_description
                        st.session_state["structured_task_input"] = restored_plan.task_description
                        st.rerun()
                    except (TypeError, ValueError, json.JSONDecodeError) as exc:
                        st.error(f"Saved plan failed validation and was not loaded: {exc}")
        except (OSError, ValueError, sqlite3.Error) as exc:
            st.error(f"Saved task plans are unavailable: {exc}")

st.caption(
    "Planning is offline and deterministic. This review screen is read-only: "
    "it cannot approve, dispatch, or execute a task."
)
st.caption(
    "No external AI API is configured or called. Future provider integrations "
    "must remain opt-in and must never activate paid services automatically."
)


# Persistent memory is available in the authenticated owner runtime and in
# the loopback-only Personal Edition. Every write has a separate consent checkbox.
st.divider()
st.header("Memory & Knowledge")
if memory_store is None or checkpoint_access is None:
    st.info("Persistent memory is unavailable because its private store did not initialize.")
else:
    st.caption("Local SQLite storage · tenant-isolated · no external API · no automatic conversation capture")
    memory_tabs = st.tabs(["Memories", "Knowledge", "Conversation", "Preferences", "Checkpoints"])

    with memory_tabs[0]:
        st.subheader("Long-term memories")
        with st.form("memory_add_form", clear_on_submit=True):
            memory_category = st.selectbox("Memory category", ["fact", "preference", "project", "workflow", "learning", "other"])
            memory_content = st.text_area("Memory content", max_chars=10000)
            memory_tags = st.text_input("Tags (comma separated)")
            memory_pinned = st.checkbox("Pin this memory")
            memory_consent = st.checkbox("I explicitly agree to save this memory")
            memory_submit = st.form_submit_button("Save memory")
        if memory_submit:
            try:
                tags = [tag.strip() for tag in memory_tags.split(",") if tag.strip()]
                execute_owner_ui_mutation(
                    "memory.add", memory_consent,
                    {"category": memory_category, "content": memory_content, "tags": tags, "pinned": memory_pinned},
                    lambda p: memory_store.add_memory(
                        tenant, category=p["category"], content=p["content"], tags=p["tags"],
                        pinned=p["pinned"], consent=True,
                    ),
                )
                st.success("Memory saved.")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
        for item in memory_store.list_memories(tenant):
            with st.container(border=True):
                st.write(f"**{item.category.title()}** · {item.content}")
                st.caption(f"Tags: {', '.join(item.tags) or 'none'} · Saved: {item.created_at}")
                if st.button("Delete memory", key=f"delete_memory_{item.memory_id}"):
                    try:
                        execute_owner_ui_mutation(
                            "memory.delete", True, {"memory_id": item.memory_id},
                            lambda p: memory_store.delete_memory(tenant, p["memory_id"]),
                        )
                        st.rerun()
                    except Exception as exc:
                        st.error(str(exc))

    with memory_tabs[1]:
        st.subheader("Knowledge collection and retrieval")
        with st.form("knowledge_add_form", clear_on_submit=True):
            knowledge_title = st.text_input("Document title", max_chars=200)
            knowledge_content = st.text_area("Knowledge content", max_chars=100000)
            knowledge_tags = st.text_input("Knowledge tags (comma separated)")
            knowledge_consent = st.checkbox("I explicitly agree to save this knowledge document")
            knowledge_submit = st.form_submit_button("Add knowledge")
        if knowledge_submit:
            try:
                tags = [tag.strip() for tag in knowledge_tags.split(",") if tag.strip()]
                execute_owner_ui_mutation(
                    "knowledge.add", knowledge_consent,
                    {"title": knowledge_title, "content": knowledge_content, "tags": tags},
                    lambda p: memory_store.add_knowledge(
                        tenant, title=p["title"], content=p["content"],
                        tags=p["tags"], consent=True,
                    ),
                )
                st.success("Knowledge document saved.")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
        knowledge_query = st.text_input("Search saved memories and knowledge")
        if knowledge_query.strip():
            for result in memory_store.search(tenant, knowledge_query):
                st.write(f"**{result['kind']} · {result['title']}**")
                st.write(result["content"])
                st.caption(f"Score: {result['score']} · Source: {result['source']}")
        st.subheader("Saved knowledge documents")
        for document in memory_store.list_knowledge(tenant):
            with st.container(border=True):
                st.write(f"**{document.title}**")
                st.caption(f"Tags: {', '.join(document.tags) or 'none'} · Source: {document.source}")
                st.write(document.content[:1200] + ("…" if len(document.content) > 1200 else ""))
                if st.button("Delete knowledge document", key=f"delete_knowledge_{document.document_id}"):
                    try:
                        execute_owner_ui_mutation(
                            "knowledge.delete", True, {"document_id": document.document_id},
                            lambda p: memory_store.delete_knowledge(tenant, p["document_id"]),
                        )
                        st.rerun()
                    except Exception as exc:
                        st.error(str(exc))

    with memory_tabs[2]:
        st.subheader("Short-term conversation continuity")
        with st.form("conversation_turn_form", clear_on_submit=True):
            conversation_id = st.text_input("Conversation ID", max_chars=120)
            conversation_role = st.selectbox("Role", ["user", "assistant"])
            conversation_content = st.text_area("Turn content", max_chars=20000)
            conversation_consent = st.checkbox("I explicitly agree to save this turn")
            conversation_submit = st.form_submit_button("Save turn")
        if conversation_submit:
            try:
                execute_owner_ui_mutation(
                    "conversation.append_turn", conversation_consent,
                    {"conversation_id": conversation_id, "role": conversation_role, "content": conversation_content},
                    lambda p: memory_store.append_turn(
                        tenant, conversation_id=p["conversation_id"], role=p["role"],
                        content=p["content"], consent=True,
                    ),
                )
                st.success("Conversation turn saved.")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
        context_id = st.text_input("Load conversation ID", key="load_conversation_id")
        if context_id.strip():
            for turn in memory_store.conversation_context(tenant, context_id):
                st.write(f"**{turn.role.title()}** · {turn.content}")
            if st.button("Delete this conversation history", key="delete_conversation_history"):
                try:
                    execute_owner_ui_mutation(
                        "conversation.delete", True, {"conversation_id": context_id},
                        lambda p: memory_store.delete_conversation(tenant, p["conversation_id"]),
                    )
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))

    with memory_tabs[3]:
        st.subheader("Saved preferences")
        with st.form("preference_form", clear_on_submit=True):
            preference_key = st.text_input("Preference name", max_chars=80)
            preference_value = st.text_area("Preference value", max_chars=4000)
            preference_consent = st.checkbox("I explicitly agree to save this preference")
            preference_submit = st.form_submit_button("Save preference")
        if preference_submit:
            try:
                execute_owner_ui_mutation(
                    "preference.save", preference_consent,
                    {"key": preference_key, "value": preference_value},
                    lambda p: memory_store.save_preference(
                        tenant, key=p["key"], value=p["value"], consent=True,
                    ),
                )
                st.success("Preference saved.")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
        for key, value in memory_store.get_preferences(tenant).items():
            st.write(f"**{key}:** {value}")
            if st.button("Delete preference", key=f"delete_preference_{key}"):
                try:
                    execute_owner_ui_mutation(
                        "preference.delete", True, {"key": key},
                        lambda p: memory_store.delete_preference(tenant, p["key"]),
                    )
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))

    with memory_tabs[4]:
        st.subheader("Task checkpoint recovery")
        # Checkpoints remain private to the authenticated project owner.
        project_options = registry.list_projects_for_owner(checkpoint_principal)
        if project_options:
            with st.form("checkpoint_form", clear_on_submit=True):
                checkpoint_project = st.selectbox(
                    "Project", options=[p.project_id for p in project_options],
                    format_func=lambda value: next(p.name for p in project_options if p.project_id == value),
                )
                checkpoint_label = st.text_input("Checkpoint label", max_chars=160)
                checkpoint_summary = st.text_area("Completed work / current state", max_chars=10000)
                checkpoint_next = st.text_area("Next action", max_chars=2000)
                checkpoint_status = st.selectbox("Status", ["active", "blocked", "completed", "cancelled"])
                checkpoint_consent = st.checkbox("I explicitly agree to save this checkpoint")
                checkpoint_submit = st.form_submit_button("Save checkpoint")
            if checkpoint_submit:
                try:
                    execute_owner_ui_mutation(
                        "checkpoint.save", checkpoint_consent,
                        {"project_id": checkpoint_project, "label": checkpoint_label,
                         "summary": checkpoint_summary, "next_action": checkpoint_next,
                         "status": checkpoint_status},
                        lambda p: checkpoint_access.save_checkpoint(
                            project_id=p["project_id"], label=p["label"],
                            summary=p["summary"], next_action=p["next_action"],
                            status=p["status"], consent=True,
                        ),
                    )
                    st.success("Checkpoint saved.")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))
            selected_checkpoint_project = st.selectbox(
                "Recover latest checkpoint for project",
                options=[p.project_id for p in project_options],
                format_func=lambda value: next(p.name for p in project_options if p.project_id == value),
                key="recover_checkpoint_project",
            )
            recovered = checkpoint_access.latest_checkpoint(selected_checkpoint_project)
            if recovered:
                st.write(f"**{recovered.label} · {recovered.status}**")
                st.write(recovered.summary)
                st.info("Next action: " + recovered.next_action)
            else:
                st.caption("No checkpoint exists for this project yet.")
        else:
            st.caption("Create a project before saving a project checkpoint.")
