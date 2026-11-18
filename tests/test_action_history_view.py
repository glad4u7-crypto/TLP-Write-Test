from dataclasses import dataclass
import sqlite3

import pytest

from core.action_history_view import read_owner_action_history
from core.browser_recovery import RecoveryLedgerError, SQLiteBrowserRecoveryLedger


@dataclass
class Principal:
    issuer: str
    subject: str


def make_owner_ledger(tmp_path):
    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    private.chmod(0o700)
    path = private / "browser.sqlite3"
    ledger = SQLiteBrowserRecoveryLedger(path)
    ledger.claim("job_ownerhist01", "a" * 64, session_id="private-session-123456")
    ledger.transition("job_ownerhist01", "running")
    ledger.transition("job_ownerhist01", "failed", outcome_code="worker_error")
    return path, ledger


def test_action_history_view_is_owner_only_and_payload_free(tmp_path):
    path, _ = make_owner_ledger(tmp_path)
    settings = {
        "owner_issuer": "https://issuer.example",
        "owner_subject": "owner-123",
        "browser_recovery_db_path": str(path),
    }
    with pytest.raises(PermissionError):
        read_owner_action_history(None, settings)
    with pytest.raises(PermissionError):
        read_owner_action_history(Principal("https://issuer.example", "other"), settings)

    rows = read_owner_action_history(Principal("https://issuer.example", "owner-123"), settings)
    assert [row["state"] for row in rows] == ["accepted", "running", "failed"]
    assert all("session" not in repr(row).lower() for row in rows)
    assert "private-session-123456" not in repr(rows)


def test_action_history_view_fails_closed_on_tampering(tmp_path):
    path, _ = make_owner_ledger(tmp_path)
    with sqlite3.connect(path) as db:
        db.execute("DROP TRIGGER browser_history_no_update")
        db.execute("UPDATE browser_job_history SET state='completed' WHERE sequence=1")
    settings = {
        "owner_issuer": "https://issuer.example",
        "owner_subject": "owner-123",
        "browser_recovery_db_path": str(path),
    }
    with pytest.raises(RecoveryLedgerError, match="integrity"):
        read_owner_action_history(Principal("https://issuer.example", "owner-123"), settings)


def test_action_history_view_requires_owner_private_existing_ledger(tmp_path):
    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    private.chmod(0o700)
    path = private / "missing.sqlite3"
    settings = {
        "owner_issuer": "https://issuer.example",
        "owner_subject": "owner-123",
        "browser_recovery_db_path": str(path),
    }
    with pytest.raises(RecoveryLedgerError):
        read_owner_action_history(Principal("https://issuer.example", "owner-123"), settings)
