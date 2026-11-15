import pytest

from core.session_security import bind_session_identity


def test_first_identity_binding_does_not_report_switch():
    state = {}
    assert bind_session_identity(state, "alice") is False
    assert state["active_identity_subject"] == "alice"


def test_identity_switch_clears_pending_approval_and_user_specific_state():
    state = {
        "active_identity_subject": "alice",
        "pending_project": {"name": "Alice draft", "description": ""},
        "selected_project_id": "alice-project",
        "approval_authority": object(),
        "execution_gateway": object(),
        "execution_gateway_owner": "alice",
        "free_plan": "Alice plan",
        "draft_task": "Alice private task",
        "project_registry": object(),
    }

    assert bind_session_identity(state, "bob") is True

    assert state["active_identity_subject"] == "bob"
    for key in (
        "pending_project",
        "selected_project_id",
        "approval_authority",
        "execution_gateway",
        "execution_gateway_owner",
        "free_plan",
        "draft_task",
        "project_registry",
        "project_registry_tenant",
    ):
        assert key not in state


def test_same_identity_does_not_clear_pending_work():
    state = {"active_identity_subject": "alice", "pending_project": {"name": "draft"}}
    assert bind_session_identity(state, "alice") is False
    assert "pending_project" in state


@pytest.mark.parametrize("subject", ["", " ", None, 123])
def test_identity_binding_rejects_invalid_subject(subject):
    with pytest.raises(ValueError):
        bind_session_identity({}, subject)
