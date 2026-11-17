import os
from concurrent.futures import ThreadPoolExecutor

import pytest

from core.browser_recovery import (
    BrowserDispatchBlocked,
    DuplicateBrowserJob,
    RecoveryLedgerError,
    SQLiteBrowserRecoveryLedger,
)


def make_ledger(tmp_path, name="browser.sqlite3"):
    directory = tmp_path / "private"
    directory.mkdir(mode=0o700, exist_ok=True)
    directory.chmod(0o700)
    return SQLiteBrowserRecoveryLedger(directory / name)


def test_claim_is_durable_and_duplicate_ids_never_replay_after_completion(tmp_path):
    ledger = make_ledger(tmp_path)
    ledger.claim("job_12345678", "a" * 64, session_id="s" * 32)
    ledger.transition("job_12345678", "running")
    ledger.transition("job_12345678", "completed", outcome_code="success")

    restarted = SQLiteBrowserRecoveryLedger(ledger.path)
    with pytest.raises(DuplicateBrowserJob):
        restarted.claim("job_12345678", "a" * 64, session_id="t" * 32)
    assert restarted.get("job_12345678")["state"] == "completed"


def test_concurrent_claim_has_exactly_one_winner(tmp_path):
    ledger = make_ledger(tmp_path)

    def claim(_):
        try:
            ledger.claim("job_concurrent01", "b" * 64, session_id="x" * 32)
            return "accepted"
        except DuplicateBrowserJob:
            return "duplicate"

    with ThreadPoolExecutor(max_workers=12) as pool:
        results = list(pool.map(claim, range(24)))
    assert results.count("accepted") == 1
    assert results.count("duplicate") == 23


def test_restart_marks_running_job_interrupted_without_replay(tmp_path):
    ledger = make_ledger(tmp_path)
    ledger.claim("job_restart001", "c" * 64, session_id="r" * 32)
    ledger.transition("job_restart001", "running")

    restarted = SQLiteBrowserRecoveryLedger(ledger.path)
    assert restarted.recover_interrupted() == ["job_restart001"]
    assert restarted.get("job_restart001")["state"] == "interrupted"
    with pytest.raises(DuplicateBrowserJob):
        restarted.claim("job_restart001", "c" * 64, session_id="z" * 32)


def test_accepted_but_not_started_job_is_recovered_as_interrupted(tmp_path):
    ledger = make_ledger(tmp_path)
    ledger.claim("job_accepted01", "d" * 64, session_id="a" * 32)
    assert ledger.recover_interrupted() == ["job_accepted01"]
    assert ledger.get("job_accepted01")["outcome_code"] == "process_restart"


def test_terminal_state_cannot_be_reopened(tmp_path):
    ledger = make_ledger(tmp_path)
    ledger.claim("job_terminal01", "e" * 64, session_id="b" * 32)
    ledger.transition("job_terminal01", "failed", outcome_code="worker_error")
    with pytest.raises(RecoveryLedgerError, match="terminal"):
        ledger.transition("job_terminal01", "running")


def test_dispatch_block_is_durable_and_fails_closed(tmp_path):
    ledger = make_ledger(tmp_path)
    ledger.latch_dispatch_block()
    restarted = SQLiteBrowserRecoveryLedger(ledger.path)
    assert restarted.dispatch_blocked() is True
    with pytest.raises(BrowserDispatchBlocked):
        restarted.claim("job_blocked001", "f" * 64, session_id="c" * 32)


def test_bad_digest_and_unsafe_database_permissions_are_rejected(tmp_path):
    ledger = make_ledger(tmp_path)
    with pytest.raises(ValueError, match="SHA-256"):
        ledger.claim("job_bad_digest", "not-a-digest", session_id="d" * 32)
    if os.name == "posix":
        assert ledger.path.stat().st_mode & 0o777 == 0o600


def test_unknown_job_transition_is_rejected(tmp_path):
    ledger = make_ledger(tmp_path)
    with pytest.raises(RecoveryLedgerError, match="does not exist"):
        ledger.transition("job_missing001", "completed")


def test_concurrent_terminal_transitions_are_serialized(tmp_path):
    ledger = make_ledger(tmp_path)
    ledger.claim("job_race_state01", "1" * 64, session_id="r" * 32)
    ledger.transition("job_race_state01", "running")

    def finish(state):
        try:
            ledger.transition("job_race_state01", state, outcome_code=state)
            return state
        except RecoveryLedgerError:
            return "rejected"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(finish, ("completed", "failed")))

    assert results.count("rejected") == 1
    assert ledger.get("job_race_state01")["state"] in {"completed", "failed"}


def test_action_history_records_every_state_without_session_or_payload(tmp_path):
    ledger = make_ledger(tmp_path)
    ledger.claim("job_history0001", "a" * 64, session_id="private-session-identifier-123")
    ledger.transition("job_history0001", "running")
    ledger.transition("job_history0001", "failed", outcome_code="worker_error")

    history = ledger.list_history("job_history0001")
    assert [row["state"] for row in history] == ["accepted", "running", "failed"]
    assert all("session" not in repr(row).lower() for row in history)
    assert "private-session-identifier-123" not in repr(history)
    assert ledger.verify_history() == history[-1]["entry_hash"]


def test_action_history_detects_recomputed_row_tampering_and_is_append_only(tmp_path):
    ledger = make_ledger(tmp_path)
    ledger.claim("job_historytamper", "b" * 64, session_id="x" * 32)

    import sqlite3
    with sqlite3.connect(ledger.path) as db:
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            db.execute("UPDATE browser_job_history SET state='completed' WHERE sequence=1")

        db.execute("DROP TRIGGER browser_history_no_update")
        db.execute("UPDATE browser_job_history SET state='completed' WHERE sequence=1")

    with pytest.raises(RecoveryLedgerError, match="integrity"):
        ledger.verify_history()
    with pytest.raises(RecoveryLedgerError, match="integrity"):
        ledger.claim("job_aftertamper01", "e" * 64, session_id="y" * 32)


def test_sqlite_backup_and_restore_preserve_history_and_recover_running_job(tmp_path):
    ledger = make_ledger(tmp_path)
    ledger.claim("job_backuprestore", "c" * 64, session_id="b" * 32)
    ledger.transition("job_backuprestore", "running")
    backup = ledger.path.parent / "browser-backup.sqlite3"

    assert ledger.backup_to(backup) == backup
    assert backup.stat().st_mode & 0o777 == 0o600

    ledger.transition("job_backuprestore", "completed", outcome_code="success")
    assert ledger.get("job_backuprestore")["state"] == "completed"

    ledger.restore_from(backup)
    assert ledger.get("job_backuprestore")["state"] == "running"
    assert [row["state"] for row in ledger.list_history("job_backuprestore")] == [
        "accepted", "running"
    ]
    assert ledger.recover_interrupted() == ["job_backuprestore"]
    assert ledger.get("job_backuprestore")["state"] == "interrupted"
    assert ledger.verify_history() == ledger.list_history()[-1]["entry_hash"]


def test_backup_refuses_to_overwrite_existing_destination(tmp_path):
    ledger = make_ledger(tmp_path)
    destination = ledger.path.parent / "existing-backup.sqlite3"
    destination.write_bytes(b"owner data")

    with pytest.raises(RecoveryLedgerError, match="already exists"):
        ledger.backup_to(destination)
    assert destination.read_bytes() == b"owner data"


def test_restore_rejects_backup_with_broken_history_without_replacing_live_state(tmp_path):
    ledger = make_ledger(tmp_path)
    ledger.claim("job_restoreguard1", "d" * 64, session_id="c" * 32)
    backup = ledger.path.parent / "broken-backup.sqlite3"
    ledger.backup_to(backup)

    import sqlite3
    with sqlite3.connect(backup) as db:
        db.execute("DROP TRIGGER browser_history_no_update")
        db.execute("UPDATE browser_job_history SET outcome_code='tampered' WHERE sequence=1")

    with pytest.raises(RecoveryLedgerError, match="integrity"):
        ledger.restore_from(backup)
    assert ledger.get("job_restoreguard1")["state"] == "accepted"
    assert ledger.verify_history() == ledger.list_history()[-1]["entry_hash"]


def test_history_verification_detects_tail_truncation(tmp_path):
    ledger = make_ledger(tmp_path)
    ledger.claim("job_tailtruncate1", "a" * 64, session_id="private-session-123456")
    ledger.transition("job_tailtruncate1", "running")

    import sqlite3
    with sqlite3.connect(ledger.path) as db:
        db.execute("DROP TRIGGER browser_history_no_delete")
        db.execute("DELETE FROM browser_job_history WHERE sequence=2")

    with pytest.raises(RecoveryLedgerError, match="history"):
        ledger.verify_history()
    with pytest.raises(RecoveryLedgerError, match="history"):
        ledger.claim("job_aftertruncate1", "b" * 64, session_id="another-session-123456")


def test_existing_ledger_is_migrated_with_a_verifiable_snapshot(tmp_path):
    import sqlite3

    directory = tmp_path / "private"
    directory.mkdir(mode=0o700)
    directory.chmod(0o700)
    path = directory / "legacy.sqlite3"
    with sqlite3.connect(path) as db:
        db.execute("""CREATE TABLE browser_jobs (
            job_id TEXT PRIMARY KEY,
            request_digest TEXT NOT NULL,
            state TEXT NOT NULL,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL,
            session_id TEXT,
            outcome_code TEXT
        )""")
        db.execute("""CREATE TABLE browser_control (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at REAL NOT NULL
        )""")
        db.execute(
            "INSERT INTO browser_jobs VALUES(?,?,?,?,?,?,?)",
            ("job_legacy0001", "c" * 64, "completed", 10.0, 12.0, "legacy-session-secret", "success"),
        )
    path.chmod(0o600)

    ledger = SQLiteBrowserRecoveryLedger(path)
    history = ledger.list_history("job_legacy0001")
    assert len(history) == 1
    assert history[0]["state"] == "completed"
    assert history[0]["occurred_at"] == 12.0
    assert ledger.verify_history() == history[0]["entry_hash"]


def test_outcome_code_rejects_free_form_sensitive_text(tmp_path):
    ledger = make_ledger(tmp_path)
    ledger.claim("job_outcomecheck1", "d" * 64, session_id="session-value-is-private")
    ledger.transition("job_outcomecheck1", "running")
    with pytest.raises(ValueError, match="non-sensitive"):
        ledger.transition("job_outcomecheck1", "failed", outcome_code="user@example.com")
    assert ledger.get("job_outcomecheck1")["state"] == "running"
    assert [row["state"] for row in ledger.list_history("job_outcomecheck1")] == [
        "accepted", "running"
    ]
