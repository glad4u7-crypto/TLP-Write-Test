from pathlib import Path
from types import SimpleNamespace

import streamlit as st
from streamlit.testing.v1 import AppTest


def _click_button_by_label(app: AppTest, label: str) -> None:
    """Click a uniquely named button without relying on layout traversal order."""
    matches = [button for button in app.button if button.label == label]
    assert len(matches) == 1, f"Expected exactly one button named {label!r}"
    matches[0].click().run()


def _authenticated_test_user(monkeypatch):
    claims = {
        "is_logged_in": True,
        "iss": "https://accounts.example.test",
        "sub": "app-smoke-test-user",
        "iat": 1_000,
        "exp": 4_000_000_000,
    }
    monkeypatch.setattr(
        st,
        "user",
        SimpleNamespace(is_logged_in=True, to_dict=lambda: claims),
    )


def test_streamlit_app_renders_in_safe_local_prototype_mode():
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py").run()
    assert not app.exception
    assert any("Autonomous AI Agent" in item.value for item in app.title)
    assert any("Local prototype mode" in item.value for item in app.warning)
    assert any("External API: Disabled" in item.value for item in app.markdown)


def test_streamlit_app_stops_when_auth_is_required_but_oidc_is_unconfigured(
    monkeypatch,
):
    monkeypatch.setattr(st, "secrets", {"apaa": {"require_auth": True}})
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py").run()
    assert not app.exception
    assert any("Authentication is required" in item.value for item in app.error)
    assert not app.button


def test_authenticated_app_fails_closed_for_short_signing_secret(monkeypatch):
    monkeypatch.setattr(
        st,
        "secrets",
        {
            "auth": {"redirect_uri": "https://example.test/oauth2callback"},
            "apaa": {
                "require_auth": True,
                "approval_signing_secret_hex": "ab" * 31,
            },
        },
    )
    _authenticated_test_user(monkeypatch)
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py").run()
    assert not app.exception
    assert any(
        "Durable security storage is not configured safely" in item.value
        for item in app.error
    )
    # Logout is rendered before durable-store initialization; no project/task
    # action may appear after the fail-closed stop.
    assert [button.label for button in app.button] == ["Log out"]


def test_authenticated_app_fails_closed_for_unsafe_security_database_path(
    tmp_path, monkeypatch
):
    outside = tmp_path / "outside.sqlite3"
    outside.write_bytes(b"must-not-be-opened")
    linked_dir = tmp_path / "linked"
    try:
        linked_dir.symlink_to(tmp_path, target_is_directory=True)
    except OSError:
        import pytest
        pytest.skip("directory symlink creation is unavailable")

    monkeypatch.setattr(
        st,
        "secrets",
        {
            "auth": {"redirect_uri": "https://example.test/oauth2callback"},
            "apaa": {
                "require_auth": True,
                "approval_signing_secret_hex": "ab" * 32,
                "security_db_path": str(linked_dir / "security.sqlite3"),
                "project_db_path": str(tmp_path / "projects" / "projects.sqlite3"),
            },
        },
    )
    _authenticated_test_user(monkeypatch)
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py").run()
    assert not app.exception
    assert any(
        "Durable security storage is not configured safely" in item.value
        for item in app.error
    )
    assert [button.label for button in app.button] == ["Log out"]
    assert outside.read_bytes() == b"must-not-be-opened"


def test_project_creation_requires_review_then_explicit_confirmation():
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py").run()
    assert not app.exception
    app.text_input[0].set_value("UI approval test")
    app.text_area[0].set_value("Must not create before confirmation")
    app.form_submit_button[0].click().run()
    assert not app.exception
    assert len(app.session_state["project_registry"].list_projects()) == 0
    assert "pending_project" in app.session_state
    _click_button_by_label(app, "Confirm and create project")
    assert not app.exception
    projects = app.session_state["project_registry"].list_projects()
    assert len(projects) == 1
    assert projects[0].name == "UI approval test"
    assert "pending_project" not in app.session_state


def test_project_review_can_be_cancelled_without_side_effect():
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py").run()
    assert not app.exception
    app.text_input[0].set_value("Cancelled project")
    app.text_area[0].set_value("Should not persist")
    app.form_submit_button[0].click().run()
    assert "pending_project" in app.session_state
    _click_button_by_label(app, "Cancel")
    assert not app.exception
    assert len(app.session_state["project_registry"].list_projects()) == 0
    assert "pending_project" not in app.session_state


def test_authenticated_app_fails_closed_when_project_database_initialization_fails(
    tmp_path, monkeypatch
):
    security_dir = tmp_path / "private-security"
    linked_dir = tmp_path / "linked-projects"
    security_dir.mkdir(mode=0o700)
    try:
        linked_dir.symlink_to(tmp_path, target_is_directory=True)
    except OSError:
        import pytest
        pytest.skip("directory symlink creation is unavailable")

    security_db = security_dir / "security.sqlite3"
    project_db = linked_dir / "projects.sqlite3"
    monkeypatch.setattr(
        st,
        "secrets",
        {
            "auth": {"redirect_uri": "https://example.test/oauth2callback"},
            "apaa": {
                "require_auth": True,
                "approval_signing_secret_hex": "cd" * 32,
                "security_db_path": str(security_db),
                "project_db_path": str(project_db),
            },
        },
    )
    _authenticated_test_user(monkeypatch)

    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py").run()

    assert not app.exception
    assert any(
        "Durable security storage is not configured safely" in item.value
        for item in app.error
    )
    assert [button.label for button in app.button] == ["Log out"]
    # The security store initialized first, but a project-store failure must
    # still stop the app before any authenticated project/task controls render.
    assert security_db.is_file()
    assert not project_db.exists()


def test_authenticated_store_failure_clears_capabilities_and_same_session_can_retry(
    tmp_path, monkeypatch
):
    security_dir = tmp_path / "security"
    project_dir = tmp_path / "projects"
    security_dir.mkdir(mode=0o700)
    project_dir.mkdir(mode=0o700)
    security_db = security_dir / "security.sqlite3"
    project_db = project_dir / "projects.sqlite3"
    secret = "ef" * 32
    base_secrets = {
        "auth": {"redirect_uri": "https://example.test/oauth2callback"},
        "apaa": {
            "require_auth": True,
            "approval_signing_secret_hex": secret,
            "security_db_path": str(security_db),
            "project_db_path": str(project_db),
        },
    }
    monkeypatch.setattr(st, "secrets", base_secrets)
    _authenticated_test_user(monkeypatch)

    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py").run()
    assert not app.exception
    original_authority = app.session_state["approval_authority"]
    assert "execution_gateway" in app.session_state

    # Break only project-store initialization after a previously successful
    # authenticated run, simulating an operator changing a bad path at runtime.
    linked_dir = tmp_path / "linked-projects"
    try:
        linked_dir.symlink_to(tmp_path, target_is_directory=True)
    except OSError:
        import pytest
        pytest.skip("directory symlink creation is unavailable")
    monkeypatch.setattr(
        st,
        "secrets",
        {
            "auth": {"redirect_uri": "https://example.test/oauth2callback"},
            "apaa": {
                "require_auth": True,
                "approval_signing_secret_hex": secret,
                "security_db_path": str(security_db),
                "project_db_path": str(linked_dir / "projects.sqlite3"),
            },
        },
    )
    app.run()

    assert not app.exception
    assert any(
        "Durable security storage is not configured safely" in item.value
        for item in app.error
    )
    for key in (
        "active_identity_subject",
        "approval_session_scope",
        "approval_authority_config_id",
        "approval_authority",
        "execution_gateway",
        "execution_gateway_owner",
        "project_registry",
        "project_registry_tenant",
        "pending_project",
        "selected_project_id",
        "free_plan",
        "draft_task",
    ):
        assert key not in app.session_state

    # Correcting the path in the same browser session must initialize fresh
    # tenant-bound objects; the previous authority must not be reused.
    monkeypatch.setattr(st, "secrets", base_secrets)
    app.run()
    assert not app.exception
    assert "approval_authority" in app.session_state
    assert app.session_state["approval_authority"] is not original_authority
    assert "execution_gateway" in app.session_state
    assert "project_registry_tenant" in app.session_state
    assert app.session_state["project_registry_tenant"]


def test_authenticated_approval_authority_rotates_on_secret_and_store_path_changes(
    tmp_path, monkeypatch
):
    from core.storage import TenantKey

    security_a_dir = tmp_path / "security-a"
    security_b_dir = tmp_path / "security-b"
    project_dir = tmp_path / "projects"
    for directory in (security_a_dir, security_b_dir, project_dir):
        directory.mkdir(mode=0o700)

    security_a = security_a_dir / "security.sqlite3"
    security_b = security_b_dir / "security.sqlite3"
    project_db = project_dir / "projects.sqlite3"
    secret_a = "11" * 32
    secret_b = "22" * 32

    def configure(secret, security_path):
        monkeypatch.setattr(
            st,
            "secrets",
            {
                "auth": {"redirect_uri": "https://example.test/oauth2callback"},
                "apaa": {
                    "require_auth": True,
                    "approval_signing_secret_hex": secret,
                    "security_db_path": str(security_path),
                    "project_db_path": str(project_db),
                },
            },
        )

    _authenticated_test_user(monkeypatch)
    configure(secret_a, security_a)
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py").run()
    assert not app.exception

    tenant = TenantKey("https://accounts.example.test", "app-smoke-test-user")
    payload = {"name": "rotation-check", "description": "must not execute"}
    authority_a = app.session_state["approval_authority"]
    gateway_a = app.session_state["execution_gateway"]
    scope_a = app.session_state["approval_session_scope"]
    receipt_a = authority_a.issue(
        "create_project", payload, tenant=tenant, session_scope=scope_a
    )
    config_id_a = app.session_state["approval_authority_config_id"]

    # Rotate only the signing secret while retaining the same nonce database.
    configure(secret_b, security_a)
    app.run()
    assert not app.exception
    authority_b = app.session_state["approval_authority"]
    gateway_b = app.session_state["execution_gateway"]
    scope_b = app.session_state["approval_session_scope"]
    assert authority_b is not authority_a
    assert gateway_b is not gateway_a
    assert scope_b != scope_a
    assert app.session_state["approval_authority_config_id"] != config_id_a
    assert authority_b.consume(
        receipt_a, "create_project", payload, tenant=tenant, session_scope=scope_b
    ) is False

    # A new database path with the same secret must also rotate the authority
    # and session scope; the fresh nonce store cannot revive an old receipt.
    receipt_b = authority_b.issue(
        "create_project", payload, tenant=tenant, session_scope=scope_b
    )
    configure(secret_b, security_b)
    app.run()
    assert not app.exception
    authority_c = app.session_state["approval_authority"]
    gateway_c = app.session_state["execution_gateway"]
    scope_c = app.session_state["approval_session_scope"]
    assert authority_c is not authority_b
    assert gateway_c is not gateway_b
    assert scope_c != scope_b
    assert authority_c.consume(
        receipt_b, "create_project", payload, tenant=tenant, session_scope=scope_c
    ) is False
