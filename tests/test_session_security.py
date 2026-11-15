import pytest

from core.session_security import bind_session_identity


def test_first_identity_binding_does_not_report_switch():
    state = {}
    assert bind_session_identity(state, "alice") is False
    assert state["active_identity_subject"] == "alice"


def test_identity_switch_clears_pending_approval_and_user_specific_state():
    state = {
        "active_identity_subject": "https://issuer.example\\nalice",
        "pending_project": {"name": "Alice draft", "description": ""},
        "selected_project_id": "alice-project",
        "approval_authority": object(),
        "execution_gateway": object(),
        "execution_gateway_owner": "alice",
        "free_plan": "Alice plan",
        "draft_task": "Alice private task",
        "project_registry": object(),
    }

    assert bind_session_identity(state, "https://issuer.example\\nbob") is True

    assert state["active_identity_subject"] == "https://issuer.example\\nbob"
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


def test_same_subject_from_different_issuer_is_a_distinct_identity():
    state = {
        "active_identity_subject": "https://issuer-one.example\\nalice",
        "pending_project": {"name": "Issuer one private draft"},
        "approval_authority": object(),
    }

    assert bind_session_identity(
        state, "https://issuer-two.example\\nalice"
    ) is True
    assert "pending_project" not in state
    assert "approval_authority" not in state


def test_missing_identity_marker_clears_orphaned_identity_state():
    state = {
        "pending_project": {"name": "Orphaned draft"},
        "approval_authority": object(),
        "execution_gateway": object(),
        "project_registry": object(),
    }

    assert bind_session_identity(state, "new-user") is True
    assert state["active_identity_subject"] == "new-user"
    assert not any(
        key in state
        for key in (
            "pending_project",
            "approval_authority",
            "execution_gateway",
            "project_registry",
        )
    )


def test_same_identity_does_not_clear_pending_work():
    state = {
        "active_identity_subject": "alice",
        "pending_project": {"name": "draft"},
    }
    assert bind_session_identity(state, "alice") is False
    assert "pending_project" in state


@pytest.mark.parametrize("subject", ["", " ", None, 123])
def test_identity_binding_rejects_invalid_subject(subject):
    with pytest.raises(ValueError):
        bind_session_identity({}, subject)


def test_logout_clears_all_identity_bound_state_immediately():
    from core.session_security import clear_session_identity

    state = {
        "active_identity_subject": "https://issuer.example\\nalice",
        "pending_project": {"name": "private draft"},
        "approval_session_scope": "old-session-secret",
        "approval_authority": object(),
        "execution_gateway": object(),
        "execution_gateway_owner": "alice",
        "project_registry": object(),
        "project_registry_tenant": "alice",
        "selected_project_id": "private-project",
        "free_plan": "private plan",
        "draft_task": "private task",
    }

    clear_session_identity(state)

    assert state == {}
