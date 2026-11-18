import time
import tempfile
from dataclasses import asdict
from pathlib import Path

import pytest

from core.approvals import ApprovalAuthority
from core.browser_execution import BrowserExecutionCoordinator, BrowserExecutionError
from core.browser_recovery import SQLiteBrowserRecoveryLedger
from core.browser_security import validate_browser_job
from core.identity import Principal
from core.storage import TenantKey
from core.sqlite_security_store import SQLiteSecurityStore


def private_ledger(tmp_path):
    directory = tmp_path / "recovery"
    directory.mkdir(mode=0o700)
    directory.chmod(0o700)
    return SQLiteBrowserRecoveryLedger(directory / "jobs.sqlite3"), directory



class ApprovedCoordinator(BrowserExecutionCoordinator):
    def __init__(self, worker, *, audit, recovery_ledger, private_dir, owner_session_check=lambda: True):
        self._test_tenant = TenantKey("https://apaa.test", "owner-1")
        self._test_principal = Principal("owner-1", "https://apaa.test", True, ("owner",))
        self._test_session = "owner-session-recovery-001"
        self._test_authority = ApprovalAuthority(
            nonce_store=SQLiteSecurityStore(private_dir / "security.sqlite3"),
            signing_secret=b"APAA recovery integration approval secret 32 bytes",
        )
        super().__init__(
            worker, audit=audit, recovery_ledger=recovery_ledger,
            approval_authority=self._test_authority,
            owner_principal=self._test_principal, owner_tenant=self._test_tenant,
            session_scope=self._test_session, owner_session_check=owner_session_check,
        )

    def execute(self, raw_job, *, resolver, approval_receipt=None):
        if approval_receipt is None:
            try:
                job = validate_browser_job(raw_job)
                payload = asdict(job)
                payload["allowed_origins"] = list(job.allowed_origins)
                ttl = min(60, job.expires_at - int(time.time()))
                approval_receipt = self._test_authority.issue(
                    "browser_read", payload, ttl_seconds=ttl,
                    tenant=self._test_tenant, session_scope=self._test_session,
                )
            except (TypeError, ValueError):
                pass
        return super().execute(raw_job, resolver=resolver, approval_receipt=approval_receipt)


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
    ledger, private_dir = private_ledger(tmp_path)
    worker = Worker()
    coordinator = ApprovedCoordinator(worker, audit=lambda event: None, recovery_ledger=ledger, private_dir=private_dir)
    resolver = lambda host: ["93.184.216.34"]

    assert coordinator.execute(raw_job(), resolver=resolver) == {"title": "Example Domain"}
    with pytest.raises(BrowserExecutionError, match="already consumed|durably claimed"):
        coordinator.execute(raw_job(), resolver=resolver)

    assert worker.runs == 1
    assert ledger.get("job_bcs04_001")["state"] == "completed"


def test_audit_write_failure_latches_dispatch_before_worker_start(tmp_path):
    ledger, private_dir = private_ledger(tmp_path)
    worker = Worker()

    def broken_audit(event):
        raise OSError("simulated audit storage outage")

    coordinator = ApprovedCoordinator(worker, audit=broken_audit, recovery_ledger=ledger, private_dir=private_dir)
    with pytest.raises(BrowserExecutionError, match="Audit write failed|audit"):
        coordinator.execute(raw_job("job_auditfail01"), resolver=lambda host: ["93.184.216.34"])

    assert worker.runs == 0
    assert ledger.dispatch_blocked() is True
    assert ledger.get("job_auditfail01")["state"] == "failed"
    with pytest.raises(BrowserExecutionError, match="blocked"):
        coordinator.execute(raw_job("job_auditfail02"), resolver=lambda host: ["93.184.216.34"])
    assert worker.runs == 0


def test_audit_records_do_not_contain_raw_job_or_session_identifiers(tmp_path):
    ledger, private_dir = private_ledger(tmp_path)
    worker = Worker()
    events = []
    coordinator = ApprovedCoordinator(worker, audit=events.append, recovery_ledger=ledger, private_dir=private_dir)
    job_id = "job_sensitiveid01"

    coordinator.execute(raw_job(job_id), resolver=lambda host: ["93.184.216.34"])

    assert events
    assert all("job_id" not in event and "session_id" not in event for event in events)
    assert all(job_id not in repr(event) for event in events)
    assert all(len(event["job_ref"]) == 24 and len(event["session_ref"]) == 24 for event in events)


def test_unconfirmed_cancellation_marks_job_interrupted_and_blocks_dispatch(tmp_path):
    import threading

    ledger, private_dir = private_ledger(tmp_path)
    started = threading.Event()
    release = threading.Event()

    class UnconfirmedWorker(Worker):
        def run(self, job, **kwargs):
            started.set()
            release.wait(timeout=3)
            kwargs["cancellation"].raise_if_cancelled()
            return {"title": "unexpected"}

        def terminate(self, session_id):
            return False

    worker = UnconfirmedWorker()
    events = []
    coordinator = ApprovedCoordinator(worker, audit=events.append, recovery_ledger=ledger, private_dir=private_dir)
    errors = []

    def execute():
        try:
            coordinator.execute(raw_job("job_cancel_unconfirmed01"), resolver=lambda host: ["93.184.216.34"])
        except Exception as exc:
            errors.append(exc)

    thread = threading.Thread(target=execute)
    thread.start()
    assert started.wait(timeout=2)
    with pytest.raises(BrowserExecutionError, match="termination failed"):
        coordinator.cancel("job_cancel_unconfirmed01")
    release.set()
    thread.join(timeout=3)

    assert not thread.is_alive()
    assert ledger.get("job_cancel_unconfirmed01")["state"] == "interrupted"
    assert ledger.dispatch_blocked() is True
    assert any(event["event"] == "job_cancel_unconfirmed" for event in events)


def test_restart_recovery_latches_dispatch_when_orphan_review_is_required(tmp_path):
    ledger, private_dir = private_ledger(tmp_path)
    ledger.claim("job_crash_orphan001", "2" * 64, session_id="orphan-session-0001")
    ledger.transition("job_crash_orphan001", "running")

    worker = Worker()
    coordinator = ApprovedCoordinator(worker, audit=lambda event: None, recovery_ledger=ledger, private_dir=private_dir)
    interrupted = coordinator.recover_interrupted_jobs()

    assert interrupted == ["job_crash_orphan001"]
    assert ledger.get("job_crash_orphan001")["state"] == "interrupted"
    assert ledger.dispatch_blocked() is True
    with pytest.raises(BrowserExecutionError, match="blocked"):
        coordinator.execute(raw_job("job_after_crash001"), resolver=lambda host: ["93.184.216.34"])
    assert worker.runs == 0
