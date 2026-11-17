import sqlite3

import pytest

from core.browser_recovery import RecoveryLedgerError, SQLiteBrowserRecoveryLedger


def make_ledger(tmp_path):
    directory = tmp_path / "private"
    directory.mkdir(mode=0o700)
    directory.chmod(0o700)
    return SQLiteBrowserRecoveryLedger(directory / "browser.sqlite3")


def test_owner_approval_correlation_is_durable_and_bound_to_claimed_job(tmp_path):
    ledger = make_ledger(tmp_path)
    digest = "a" * 64
    ledger.claim("job_approval0001", digest, session_id="worker-session-123456")
    entry = ledger.record_approval_correlation(
        "job_approval0001",
        approval_ref="b" * 64,
        owner_ref="c" * 64,
        session_ref="d" * 64,
        request_digest=digest,
    )

    assert len(entry) == 64
    rows = ledger.list_approval_correlations("job_approval0001")
    assert len(rows) == 1
    assert rows[0]["approval_ref"] == "b" * 64
    assert rows[0]["owner_ref"] == "c" * 64
    assert rows[0]["session_ref"] == "d" * 64
    assert rows[0]["request_digest"] == digest

    restarted = SQLiteBrowserRecoveryLedger(ledger.path)
    assert restarted.list_approval_correlations() == rows
    assert restarted.verify_history() == restarted.list_history()[-1]["entry_hash"]


def test_approval_correlation_requires_exact_newly_claimed_job(tmp_path):
    ledger = make_ledger(tmp_path)
    with pytest.raises(RecoveryLedgerError, match="newly accepted"):
        ledger.record_approval_correlation(
            "job_missing0001",
            approval_ref="b" * 64,
            owner_ref="c" * 64,
            session_ref="d" * 64,
            request_digest="a" * 64,
        )

    ledger.claim("job_approval0002", "a" * 64, session_id="worker-session-123456")
    with pytest.raises(RecoveryLedgerError, match="newly accepted"):
        ledger.record_approval_correlation(
            "job_approval0002",
            approval_ref="b" * 64,
            owner_ref="c" * 64,
            session_ref="d" * 64,
            request_digest="e" * 64,
        )


def test_approval_correlation_is_one_per_job_and_append_only(tmp_path):
    ledger = make_ledger(tmp_path)
    ledger.claim("job_approval0003", "a" * 64, session_id="worker-session-123456")
    kwargs = dict(
        approval_ref="b" * 64,
        owner_ref="c" * 64,
        session_ref="d" * 64,
        request_digest="a" * 64,
    )
    ledger.record_approval_correlation("job_approval0003", **kwargs)
    with pytest.raises(RecoveryLedgerError, match="already exists"):
        ledger.record_approval_correlation("job_approval0003", **kwargs)

    with sqlite3.connect(ledger.path) as db:
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            db.execute(
                "UPDATE browser_approval_correlations SET owner_ref=? WHERE job_id=?",
                ("e" * 64, "job_approval0003"),
            )
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            db.execute(
                "DELETE FROM browser_approval_correlations WHERE job_id=?",
                ("job_approval0003",),
            )


def test_same_approval_reference_cannot_be_correlated_to_two_jobs(tmp_path):
    ledger = make_ledger(tmp_path)
    ledger.claim("job_approval0006", "a" * 64, session_id="worker-session-123456")
    ledger.claim("job_approval0007", "e" * 64, session_id="another-worker-session-123")
    ledger.record_approval_correlation(
        "job_approval0006", approval_ref="b" * 64, owner_ref="c" * 64,
        session_ref="d" * 64, request_digest="a" * 64,
    )
    with pytest.raises(RecoveryLedgerError, match="already exists"):
        ledger.record_approval_correlation(
            "job_approval0007", approval_ref="b" * 64, owner_ref="c" * 64,
            session_ref="d" * 64, request_digest="e" * 64,
        )


def test_approval_correlation_tampering_blocks_history_verification_and_dispatch(tmp_path):
    ledger = make_ledger(tmp_path)
    ledger.claim("job_approval0004", "a" * 64, session_id="worker-session-123456")
    ledger.record_approval_correlation(
        "job_approval0004",
        approval_ref="b" * 64,
        owner_ref="c" * 64,
        session_ref="d" * 64,
        request_digest="a" * 64,
    )
    with sqlite3.connect(ledger.path) as db:
        db.execute("DROP TRIGGER browser_approval_no_update")
        db.execute(
            "UPDATE browser_approval_correlations SET approval_ref=? WHERE job_id=?",
            ("e" * 64, "job_approval0004"),
        )

    with pytest.raises(RecoveryLedgerError, match="approval correlation integrity"):
        ledger.verify_history()
    with pytest.raises(RecoveryLedgerError, match="approval correlation integrity"):
        ledger.claim("job_aftertamper01", "f" * 64, session_id="another-worker-session-123")

def test_approval_correlation_survives_verified_backup_and_restore(tmp_path):
    ledger = make_ledger(tmp_path)
    ledger.claim("job_approval0005", "a" * 64, session_id="worker-session-123456")
    ledger.record_approval_correlation(
        "job_approval0005",
        approval_ref="b" * 64,
        owner_ref="c" * 64,
        session_ref="d" * 64,
        request_digest="a" * 64,
    )
    backup = ledger.path.parent / "browser-backup.sqlite3"
    ledger.backup_to(backup)

    ledger.transition("job_approval0005", "failed", outcome_code="test_failure")
    ledger.restore_from(backup)

    rows = ledger.list_approval_correlations("job_approval0005")
    assert len(rows) == 1
    assert rows[0]["approval_ref"] == "b" * 64
    assert ledger.get("job_approval0005")["state"] == "accepted"
    assert ledger.verify_history() == ledger.list_history()[-1]["entry_hash"]
