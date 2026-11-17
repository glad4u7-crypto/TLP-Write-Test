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
        "approval_session_scope": "alice-approval-scope",
        "approval_authority_config_id": "alice-config-fingerprint",
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
        "approval_session_scope",
        "approval_authority_config_id",
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
        "approval_session_scope": "orphaned-scope",
        "approval_authority_config_id": "orphaned-config-fingerprint",
        "execution_gateway_owner": "old-user",
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
            "approval_session_scope",
            "approval_authority_config_id",
            "execution_gateway_owner",
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
        "approval_authority_config_id": "old-config-fingerprint",
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



def test_logout_invalidates_pre_logout_approval_receipt():
    from core.approvals import ApprovalAuthority
    from core.execution import ExecutionGateway
    from core.session_security import clear_session_identity

    calls = []
    state = {
        "active_identity_subject": "https://issuer.example\\nalice",
        "approval_session_scope": "session-before-logout",
    }
    old_authority = ApprovalAuthority()
    payload = {"path": "must-not-run.txt"}
    stale_receipt = old_authority.issue(
        "write_file", payload, session_scope=state["approval_session_scope"]
    )
    state["approval_authority"] = old_authority
    state["execution_gateway"] = ExecutionGateway(
        {"write_file": lambda data: calls.append(data) or "written"},
        approval_authority=old_authority,
        session_scope=state["approval_session_scope"],
    )

    clear_session_identity(state)
    assert state == {}

    # A post-logout session receives fresh capabilities and a fresh scope.
    bind_session_identity(state, "https://issuer.example\\nbob")
    new_authority = ApprovalAuthority()
    new_gateway = ExecutionGateway(
        {"write_file": lambda data: calls.append(data) or "written"},
        approval_authority=new_authority,
        session_scope="session-after-logout",
    )
    result = new_gateway.execute(
        "write_file", payload, approval_receipt=stale_receipt
    )

    assert result.executed is False
    assert calls == []


def test_session_identity_key_is_unambiguous_for_delimiter_like_identity_values():
    from core.session_security import session_identity_key

    first = session_identity_key("https://issuer.example/path\\nsubject", "alice")
    second = session_identity_key("https://issuer.example/path", "subject\\nalice")

    assert first != second


def test_session_identity_key_rejects_missing_identity_parts():
    from core.session_security import session_identity_key

    with pytest.raises(ValueError):
        session_identity_key("", "alice")
    with pytest.raises(ValueError):
        session_identity_key("https://issuer.example", "")


def test_every_literal_app_session_state_key_is_identity_cleanup_covered():
    import ast
    from pathlib import Path

    from core.session_security import _IDENTITY_BOUND_KEYS

    app_path = Path(__file__).resolve().parents[1] / "app.py"
    tree = ast.parse(app_path.read_text(encoding="utf-8"))

    def is_session_state(node):
        return (
            isinstance(node, ast.Attribute)
            and node.attr == "session_state"
            and isinstance(node.value, ast.Name)
            and node.value.id == "st"
        )

    referenced = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Subscript) and is_session_state(node.value):
            if isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str):
                referenced.add(node.slice.value)
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and is_session_state(node.func.value)
            and node.func.attr in {"get", "pop"}
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            referenced.add(node.args[0].value)

    # The active identity marker is cleared separately by clear_session_identity.
    assert referenced <= set(_IDENTITY_BOUND_KEYS) | {"active_identity_subject"}


def test_identity_switch_and_logout_clear_global_owner_capabilities():
    from core.session_security import clear_session_identity

    owner_keys = (
        "global_owner_generation",
        "global_owner_principal",
        "global_owner_authorized",
        "global_owner_admin_context",
        "global_owner_pending_action",
        "global_owner_approval_receipt",
    )
    state = {
        "active_identity_subject": "https://issuer.example\\nalice",
        **{key: object() for key in owner_keys},
    }

    assert bind_session_identity(state, "https://issuer.example\\nbob") is True
    assert not any(key in state for key in owner_keys)

    state.update({key: object() for key in owner_keys})
    clear_session_identity(state)
    assert state == {}


def test_first_local_owner_bind_preserves_verified_login_markers_but_clears_orphaned_capabilities():
    state = {
        "apaa_local_authenticated_at": 1000.0,
        "apaa_local_last_activity": 1000.0,
        "approval_session_scope": "stale-scope",
        "approval_authority": object(),
        "execution_gateway": object(),
        "pending_project": {"name": "stale draft"},
    }
    assert bind_session_identity(state, "local-prototype") is True
    assert state["apaa_local_authenticated_at"] == 1000.0
    assert state["apaa_local_last_activity"] == 1000.0
    assert "approval_session_scope" not in state
    assert "approval_authority" not in state
    assert "execution_gateway" not in state
    assert "pending_project" not in state
