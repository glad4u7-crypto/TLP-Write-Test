from pathlib import Path

from streamlit.testing.v1 import AppTest


def _click_button_by_label(app: AppTest, label: str) -> None:
    """Click a uniquely named button without relying on layout traversal order."""
    matches = [button for button in app.button if button.label == label]
    assert len(matches) == 1, f"Expected exactly one button named {label!r}"
    matches[0].click().run()


def test_streamlit_app_renders_in_safe_local_prototype_mode():
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py").run()
    assert not app.exception
    assert any("Autonomous AI Agent" in item.value for item in app.title)
    assert any("Local prototype mode" in item.value for item in app.warning)
    assert any("External API: Disabled" in item.value for item in app.markdown)


def test_streamlit_app_stops_when_auth_is_required_but_oidc_is_unconfigured(
    tmp_path, monkeypatch
):
    streamlit_dir = tmp_path / ".streamlit"
    streamlit_dir.mkdir()
    (streamlit_dir / "secrets.toml").write_text(
        "[apaa]\nrequire_auth = true\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py").run()

    assert not app.exception
    assert any(
        "Authentication is required" in item.value
        for item in app.error
    )
    assert not app.button


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
