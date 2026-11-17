from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest

from core.personal_auth import LocalOwnerAuthStore


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"
PASSPHRASE = "test-only owner passphrase"


def _click(app, label):
    matches = [button for button in app.button if button.label == label]
    assert len(matches) == 1
    matches[0].click().run()
    assert not app.exception


def _locked_app(tmp_path, monkeypatch):
    data_dir = tmp_path / ".apaa_personal"
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("APAA_PERSONAL_DATA_DIR", str(data_dir))
    return AppTest.from_file(str(APP_PATH), default_timeout=15).run()


def _unlocked_app(tmp_path, monkeypatch):
    data_dir = tmp_path / ".apaa_personal"
    auth = LocalOwnerAuthStore(data_dir / "owner-auth.sqlite3")
    auth.configure(PASSPHRASE, PASSPHRASE)
    app = _locked_app(tmp_path, monkeypatch)
    app.text_input[0].set_value(PASSPHRASE)
    _click(app, "Unlock APAA")
    return app


def test_first_run_requires_owner_setup_before_runtime_is_available(tmp_path, monkeypatch):
    app = _locked_app(tmp_path, monkeypatch)
    assert not app.exception
    assert any("First-time Owner setup" in item.value for item in app.warning)
    assert "approval_authority" not in app.session_state
    assert "execution_gateway" not in app.session_state
    app.text_input[0].set_value(PASSPHRASE)
    app.text_input[1].set_value(PASSPHRASE)
    _click(app, "Create Owner protection")
    assert "approval_authority" not in app.session_state
    assert any("APAA is locked" in item.value for item in app.warning)


def test_owner_login_unlocks_runtime_and_logout_clears_capabilities(tmp_path, monkeypatch):
    app = _unlocked_app(tmp_path, monkeypatch)
    assert not app.exception
    assert "approval_authority" in app.session_state
    assert "execution_gateway" in app.session_state
    assert "apaa_local_authenticated_at" in app.session_state
    _click(app, "Log out")
    assert not app.exception
    assert "approval_authority" not in app.session_state
    assert "execution_gateway" not in app.session_state
    assert "pending_project" not in app.session_state
    assert "apaa_local_authenticated_at" not in app.session_state
    assert any("APAA is locked" in item.value for item in app.warning)


def test_idle_session_expiry_clears_pending_approval_and_owner_runtime(tmp_path, monkeypatch):
    app = _unlocked_app(tmp_path, monkeypatch)
    app.session_state["pending_project"] = {
        "name": "must be discarded", "description": "stale draft"
    }
    app.session_state["apaa_local_last_activity"] -= 16 * 60
    app.run()
    assert not app.exception
    assert "approval_authority" not in app.session_state
    assert "execution_gateway" not in app.session_state
    assert "pending_project" not in app.session_state
    assert "apaa_local_authenticated_at" not in app.session_state
    assert any("session expired" in item.value for item in app.warning)


def test_absolute_session_expiry_clears_owner_runtime(tmp_path, monkeypatch):
    app = _unlocked_app(tmp_path, monkeypatch)
    app.session_state["apaa_local_authenticated_at"] -= 13 * 60 * 60
    app.run()
    assert not app.exception
    assert "approval_authority" not in app.session_state
    assert "execution_gateway" not in app.session_state
    assert "apaa_local_authenticated_at" not in app.session_state
    assert any("session expired" in item.value for item in app.warning)


def test_failed_owner_login_does_not_initialize_agent_capabilities(tmp_path, monkeypatch):
    auth = LocalOwnerAuthStore(tmp_path / ".apaa_personal" / "owner-auth.sqlite3")
    auth.configure(PASSPHRASE, PASSPHRASE)
    app = _locked_app(tmp_path, monkeypatch)
    app.text_input[0].set_value("wrong owner passphrase")
    _click(app, "Unlock APAA")
    assert "approval_authority" not in app.session_state
    assert "execution_gateway" not in app.session_state
    assert any("authentication failed" in item.value.lower() for item in app.error)
