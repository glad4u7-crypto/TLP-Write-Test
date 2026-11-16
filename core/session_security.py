"""Session security helpers for identity transitions."""

from collections.abc import MutableMapping
import json


_IDENTITY_BOUND_KEYS = (
    "pending_project",
    "selected_project_id",
    "project_registry",
    "project_registry_tenant",
    "approval_authority",
    "execution_gateway",
    "execution_gateway_owner",
    "free_plan",
    "draft_task",
    "structured_task_plan",
    "structured_task_source",
    "structured_task_clarification",
    "structured_task_input",
    "approval_session_scope",
    "approval_authority_config_id",
    "trusted_directory_enrolled_session",
    "global_owner_generation",
    "global_owner_principal",
    "global_owner_authorized",
    "global_owner_admin_context",
    "global_owner_pending_action",
    "global_owner_approval_receipt",
)


def bind_session_identity(
    session_state: MutableMapping,
    identity_subject: str,
) -> bool:
    """Bind this Streamlit session to an identity.

    Returns True when an existing identity changed. If the identity marker is
    missing but identity-bound state remains, clear that orphaned state too.
    This fails closed if session state is partially reset or restored.
    """
    if not isinstance(identity_subject, str) or not identity_subject.strip():
        raise ValueError("A non-empty authenticated identity subject is required.")

    previous = session_state.get("active_identity_subject")
    has_orphaned_identity_state = (
        previous is None
        and any(key in session_state for key in _IDENTITY_BOUND_KEYS)
    )
    changed = (
        (previous is not None and previous != identity_subject)
        or has_orphaned_identity_state
    )
    if changed:
        for key in _IDENTITY_BOUND_KEYS:
            session_state.pop(key, None)
    session_state["active_identity_subject"] = identity_subject
    return changed


def clear_session_identity(session_state: MutableMapping) -> None:
    """Remove all identity-bound state immediately when the user logs out."""
    for key in _IDENTITY_BOUND_KEYS:
        session_state.pop(key, None)
    session_state.pop("active_identity_subject", None)


def session_identity_key(issuer: str, subject: str) -> str:
    """Encode issuer and subject without ambiguous delimiter collisions."""
    if not isinstance(issuer, str) or not issuer or not isinstance(subject, str) or not subject:
        raise ValueError("A non-empty issuer and subject are required.")
    return json.dumps([issuer, subject], ensure_ascii=True, separators=(",", ":"))
