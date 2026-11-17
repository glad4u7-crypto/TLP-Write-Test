"""Cross-instance concurrency tests for one-time approval correlation."""

from concurrent.futures import ThreadPoolExecutor
import threading

from core.browser_recovery import RecoveryLedgerError, SQLiteBrowserRecoveryLedger


def _make_ledger(tmp_path):
    directory = tmp_path / "private"
    directory.mkdir(mode=0o700)
    directory.chmod(0o700)
    return SQLiteBrowserRecoveryLedger(directory / "browser.sqlite3")


def test_same_approval_reference_cannot_win_two_concurrent_job_correlations(tmp_path):
    first = _make_ledger(tmp_path)
    second = SQLiteBrowserRecoveryLedger(first.path)

    first.claim("job_concurrent_01", "a" * 64, session_id="worker-session-000001")
    first.claim("job_concurrent_02", "b" * 64, session_id="worker-session-000002")

    barrier = threading.Barrier(2)

    def correlate(ledger, job_id, digest):
        barrier.wait(timeout=3)
        try:
            ledger.record_approval_correlation(
                job_id,
                approval_ref="c" * 64,
                owner_ref="d" * 64,
                session_ref="e" * 64,
                request_digest=digest,
            )
            return "accepted"
        except RecoveryLedgerError:
            return "rejected"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(
            lambda args: correlate(*args),
            [
                (first, "job_concurrent_01", "a" * 64),
                (second, "job_concurrent_02", "b" * 64),
            ],
        ))

    assert sorted(results) == ["accepted", "rejected"]
    rows = first.list_approval_correlations()
    assert len(rows) == 1
    assert rows[0]["approval_ref"] == "c" * 64
    assert rows[0]["job_id"] in {"job_concurrent_01", "job_concurrent_02"}
    assert first.verify_history() == first.list_history()[-1]["entry_hash"]
