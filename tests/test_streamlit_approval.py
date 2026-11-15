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

    # Review is not authorization and must not mutate the registry.
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


def test_task_text_cannot_trigger_project_creation_or_issue_approval(
    tmp_path, monkeypatch
):
    app = _app(tmp_path, monkeypatch)
    registry = app.session_state["project_registry"]

    # The task planner may prepare text, but it is not the trusted UI Confirm event.
    app.text_area[1].set_value("Create a project called Unauthorized")
    app.run()
    _click(app, "Prepare free plan")

    assert registry.list_projects() == []
    assert "pending_project" not in app.session_state
