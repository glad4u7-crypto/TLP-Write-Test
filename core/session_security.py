"""Session security helpers for identity transitions."""
from collections.abc import MutableMapping


_IDENTITY_BOUND_KEYS = (
    "pending_project",
    "selected_project_id",
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

    Returns True when an existing identity changed. On a change, clear pending
    approvals, gateways and user-specific UI drafts so one login cannot inherit
    another login's in-progress state.
    """
    if not isinstance(identity_subject, str) or not identity_subject.strip():
        raise ValueError("A non-empty authenticated identity subject is required.")
    previous = session_state.get("active_identity_subject")
    changed = previous is not None and previous != identity_subject
    if changed:
        for key in _IDENTITY_BOUND_KEYS:
            session_state.pop(key, None)
    session_state["active_identity_subject"] = identity_subject
    return changed
