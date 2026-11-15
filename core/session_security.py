"""Session security helpers for identity transitions."""

from collections.abc import MutableMapping


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
