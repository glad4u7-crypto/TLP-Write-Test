import os
import sqlite3

import pytest

from core.browser_recovery import RecoveryLedgerError, SQLiteBrowserRecoveryLedger


def make_ledger(tmp_path):
    directory = tmp_path / "private"
    directory.mkdir(mode=0o700)
    directory.chmod(0o700)
    ledger = SQLiteBrowserRecoveryLedger(directory / "browser.sqlite3")
    ledger.claim("job_restoreatomic1", "a" * 64, session_id="private-session-123456")
    ledger.transition("job_restoreatomic1", "running")
    return ledger


def test_corrupt_backup_is_rejected_and_live_database_is_unchanged(tmp_path):
    ledger = make_ledger(tmp_path)
    before = ledger.list_history()
    backup = ledger.path.parent / "corrupt.sqlite3"
    ledger.backup_to(backup)
    backup.write_bytes(b"not a sqlite database")
    backup.chmod(0o600)

    with pytest.raises((RecoveryLedgerError, sqlite3.DatabaseError)):
        ledger.restore_from(backup)

    assert ledger.get("job_restoreatomic1")["state"] == "running"
    assert ledger.list_history() == before
    assert ledger.verify_history() == before[-1]["entry_hash"]


def test_restore_with_missing_append_only_trigger_is_atomic(tmp_path):
    ledger = make_ledger(tmp_path)
    before = ledger.list_history()
    backup = ledger.path.parent / "missing-trigger.sqlite3"
    ledger.backup_to(backup)
    with sqlite3.connect(backup) as db:
        db.execute("DROP TRIGGER browser_history_no_delete")

    with pytest.raises(RecoveryLedgerError, match="append-only"):
        ledger.restore_from(backup)

    assert ledger.list_history() == before
    assert ledger.get("job_restoreatomic1")["state"] == "running"


def test_backup_is_private_and_failed_backup_does_not_leave_partial_file(tmp_path):
    ledger = make_ledger(tmp_path)
    backup = ledger.path.parent / "private-backup.sqlite3"
    ledger.backup_to(backup)
    if os.name == "posix":
        assert backup.stat().st_mode & 0o777 == 0o600
    assert SQLiteBrowserRecoveryLedger(backup).verify_history() == ledger.verify_history()
