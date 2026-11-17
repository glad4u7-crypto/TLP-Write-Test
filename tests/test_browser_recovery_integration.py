import time

import pytest

from core.browser_execution import BrowserExecutionCoordinator, BrowserExecutionError
from core.browser_recovery import SQLiteBrowserRecoveryLedger


def private_ledger(tmp_path):
    directory = tmp_path / "recovery"
    directory.mkdir(mode=0o700)
    directory.chmod(0o700)
    return SQLiteBrowserRecoveryLedger(directory / "jobs.sqlite3")


def raw_job(job_id="job_bcs04_001"):
    return {
        "job_id": job_id,
        "url": "https://example.com/",
        "allowed_origins": ["https://example.com"],
        "action": "read_page_title",
        "expires_at": int(time.time()) + 180,
        "max_response_bytes": 4096,
        "max_runtime_seconds": 5,
    }


class Worker:
    def __init__(self):
        self.runs = 0
        self.terminated = []

    def run(self, job, **kwargs):
        self.runs += 1
        return {"title": "Example Domain"}

    def terminate(self, session_id):
        self.terminated.append(session_id)
        return True


def test_coordinator_uses_durable_claim_to_prevent_completed_job_replay(tmp_path):
    ledger = private_ledger(tmp_path)
    worker = Worker()
    coordinator = BrowserExecutionCoordinator(worker, audit=lambda event: None, recovery_ledger=ledger)
    resolver = lambda host: ["93.184.216.34"]

    assert coordinator.execute(raw_job(), resolver=resolver) == {"title": "Example Domain"}
    with pytest.raises(BrowserExecutionError, match="already consumed|durably claimed"):
        coordinator.execute(raw_job(), resolver=resolver)

    assert worker.runs == 1
    assert ledger.get("job_bcs04_001")["state"] == "completed"


def test_audit_write_failure_latches_dispatch_before_worker_start(tmp_path):
    ledger = private_ledger(tmp_path)
    worker = Worker()

    def broken_audit(event):
        raise OSError("simulated audit storage outage")

    coordinator = BrowserExecutionCoordinator(worker, audit=broken_audit, recovery_ledger=ledger)
    with pytest.raises(BrowserExecutionError, match="Audit write failed|audit"):
        coordinator.execute(raw_job("job_auditfail01"), resolver=lambda host: ["93.184.216.34"])

    assert worker.runs == 0
    assert ledger.dispatch_blocked() is True
    assert ledger.get("job_auditfail01")["state"] == "failed"
    with pytest.raises(BrowserExecutionError, match="blocked"):
        coordinator.execute(raw_job("job_auditfail02"), resolver=lambda host: ["93.184.216.34"])
    assert worker.runs == 0


def test_audit_records_do_not_contain_raw_job_or_session_identifiers(tmp_path):
    ledger = private_ledger(tmp_path)
    worker = Worker()
    events = []
    coordinator = BrowserExecutionCoordinator(worker, audit=events.append, recovery_ledger=ledger)
    job_id = "job_sensitiveid01"

    coordinator.execute(raw_job(job_id), resolver=lambda host: ["93.184.216.34"])

    assert events
    assert all("job_id" not in event and "session_id" not in event for event in events)
    assert all(job_id not in repr(event) for event in events)
    assert all(len(event["job_ref"]) == 24 and len(event["session_ref"]) == 24 for event in events)
