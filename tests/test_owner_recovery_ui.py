from pathlib import Path

from streamlit.testing.v1 import AppTest

from core.personal_auth import LocalOwnerAuthStore
from core.personal_runtime import PERSONAL_OWNER_TENANT, personal_runtime_paths
from core.sqlite_security_store import SQLiteSecurityStore

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"
PASSPHRASE = "test-only owner passphrase"


def _app_with_uncertain_execution(tmp_path, monkeypatch):
    data_dir = tmp_path / ".apaa_personal"
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("APAA_PERSONAL_DATA_DIR", str(data_dir))
    auth = LocalOwnerAuthStore(data_dir / "owner-auth.sqlite3")
    auth.configure(PASSPHRASE, PASSPHRASE)
    paths = personal_runtime_paths(data_dir)
    store = SQLiteSecurityStore(paths.security_db)
    key = "owner-recovery-request-0001"
    assert store.claim_execution(
        PERSONAL_OWNER_TENANT, key, "project.create", "a" * 64
    ) == "claimed"
    assert store.finish_execution(PERSONAL_OWNER_TENANT, key, "uncertain")
    app = AppTest.from_file(str(APP_PATH), default_timeout=20).run()
    app.text_input[0].set_value(PASSPHRASE)
    unlock = [button for button in app.button if button.label == "Unlock APAA"]
    assert len(unlock) == 1
    unlock[0].click().run()
    assert not app.exception
    return app, store, key


def test_owner_recovery_ui_requires_confirmation_and_never_reexecutes(tmp_path, monkeypatch):
    app, store, key = _app_with_uncertain_execution(tmp_path, monkeypatch)
    assert any("Owner Recovery" in item.label for item in app.expander)
    confirm = [
        item for item in app.checkbox
        if item.label == "I reviewed the external outcome and confirm this decision"
    ]
    assert len(confirm) == 1
    buttons = [item for item in app.button if item.label == "Confirm completed"]
    assert len(buttons) == 1 and buttons[0].disabled
    confirm[0].set_value(True)
    app.run()
    buttons = [item for item in app.button if item.label == "Confirm completed"]
    assert len(buttons) == 1 and not buttons[0].disabled
    buttons[0].click().run()
    assert not app.exception
    assert store.list_unresolved_executions(PERSONAL_OWNER_TENANT) == ()
    assert store.verify_audit_chain()
