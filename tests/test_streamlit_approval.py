"""Streamlit AppTest coverage for approval and per-session isolation."""
from pathlib import Path

from streamlit.testing.v1 import AppTest


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def _app(tmp_path, monkeypatch):
    tmp_path.mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(tmp_path)
    return AppTest.from_file(str(APP_PATH), default_timeout=15).run()


def _click(app, label):
    matches = [button for button in app.button if button.label == label]
    assert len(matches) == 1, f"Expected one button labelled {label!r}, got {len(matches)}"
    matches[0].click().run()
    assert not app.exception


def _prepare_project(app, name="P06 UI test", description="Approval integration test"):
    app.text_input[0].set_value(name)
    app.text_area[0].set_value(description)
    _click(app, "Review project details")


def test_streamlit_project_creation_requires_review_then_explicit_confirm(
    tmp_path, monkeypatch
):
    app = _app(tmp_path, monkeypatch)
    registry = app.session_state["project_registry"]

    _prepare_project(app)

    assert registry.list_projects() == []
    assert app.session_state["pending_project"] == {
        "name": "P06 UI test",
        "description": "Approval integration test",
    }

    _click(app, "Confirm and create project")

    projects = registry.list_projects()
    assert len(projects) == 1
    assert projects[0].name == "P06 UI test"
    assert projects[0].description == "Approval integration test"
    assert "pending_project" not in app.session_state


def test_streamlit_cancel_does_not_create_project(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch)
    registry = app.session_state["project_registry"]

    _prepare_project(app, name="Must be cancelled")
    assert registry.list_projects() == []

    _click(app, "Cancel")

    assert registry.list_projects() == []
    assert "pending_project" not in app.session_state


def test_streamlit_sessions_do_not_share_project_registry_or_approval_authority(
    tmp_path, monkeypatch
):
    first = _app(tmp_path / "first", monkeypatch)
    second = _app(tmp_path / "second", monkeypatch)

    first_registry = first.session_state["project_registry"]
    second_registry = second.session_state["project_registry"]
    first_authority = first.session_state["approval_authority"]
    second_authority = second.session_state["approval_authority"]

    assert first_registry is not second_registry
    assert first_authority is not second_authority

    _prepare_project(first, name="Only first session")
    _click(first, "Confirm and create project")

    assert len(first_registry.list_projects()) == 1
    assert second_registry.list_projects() == []


def test_cross_session_approval_receipt_is_rejected(tmp_path, monkeypatch):
    first = _app(tmp_path / "issuer", monkeypatch)
    second = _app(tmp_path / "consumer", monkeypatch)

    payload = {"name": "Cross session", "description": "Must not be authorized"}
    receipt = first.session_state["approval_authority"].issue(
        "create_project", payload
    )
    result = second.session_state["execution_gateway"].execute(
        "create_project", payload, approval_receipt=receipt
    )

    assert result.executed is False
    assert second.session_state["project_registry"].list_projects() == []
    assert first.session_state["project_registry"].list_projects() == []


def test_task_text_cannot_trigger_project_creation_or_issue_approval(
    tmp_path, monkeypatch
):
    app = _app(tmp_path, monkeypatch)
    registry = app.session_state["project_registry"]

    app.text_area[1].set_value("Create a project called Unauthorized")
    app.run()
    _click(app, "Prepare structured plan")

    assert registry.list_projects() == []
    assert "pending_project" not in app.session_state


def test_streamlit_replacing_reviewed_details_confirms_only_latest_payload(
    tmp_path, monkeypatch
):
    app = _app(tmp_path, monkeypatch)
    registry = app.session_state["project_registry"]

    _prepare_project(app, name="Old draft", description="Must never be created")
    assert registry.list_projects() == []

    # A second explicit review replaces the pending payload before approval.
    app.text_input[0].set_value("Latest draft")
    app.text_area[0].set_value("Only these reviewed details may be created")
    _click(app, "Review project details")

    assert app.session_state["pending_project"] == {
        "name": "Latest draft",
        "description": "Only these reviewed details may be created",
    }
    assert registry.list_projects() == []

    _click(app, "Confirm and create project")
    projects = registry.list_projects()
    assert len(projects) == 1
    assert projects[0].name == "Latest draft"
    assert projects[0].description == "Only these reviewed details may be created"
    assert "pending_project" not in app.session_state


def test_streamlit_second_rerun_after_confirmation_cannot_duplicate_project(
    tmp_path, monkeypatch
):
    app = _app(tmp_path, monkeypatch)
    registry = app.session_state["project_registry"]

    _prepare_project(app, name="Single confirmation")
    _click(app, "Confirm and create project")
    assert len(registry.list_projects()) == 1

    # A plain rerun has no new button event and must not dispatch again.
    app.run()
    assert len(registry.list_projects()) == 1
    assert "pending_project" not in app.session_state
