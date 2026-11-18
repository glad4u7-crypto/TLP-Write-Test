import time
from pathlib import Path

import pytest

from core.approvals import ApprovalAuthority
from core.audit import JsonlAuditLog
from core.browser_control import BrowserControlBoundary, BrowserControlSecurityError
from core.browser_execution import BrowserExecutionCoordinator
from core.browser_recovery import SQLiteBrowserRecoveryLedger
from core.identity import Principal
from core.sqlite_security_store import SQLiteSecurityStore
from core.storage import TenantKey


class Worker:
    def __init__(self):
        self.calls = []

    def run(self, job, **kwargs):
        self.calls.append(job)
        return {"title": "Example Domain"}

    def terminate(self, session_id):
        return True


def _context(private_dir: Path):
    tenant = TenantKey("https://apaa.test", "owner-1")
    principal = Principal("owner-1", "https://apaa.test", True, ("owner",))
    scope = "owner-session-control-001"
    authority = ApprovalAuthority(
        nonce_store=SQLiteSecurityStore(private_dir / "security.sqlite3"),
        signing_secret=b"APAA browser control integration secret 32 bytes",
    )
    active = {"value": True}
    check_session = lambda: active["value"]
    audit = JsonlAuditLog(private_dir / "audit.jsonl")
    boundary = BrowserControlBoundary(
        owner_principal=principal, owner_tenant=tenant, owner_verified=True,
        session_scope=scope, approval_authority=authority,
        audit_log=audit, owner_session_check=check_session,
    )
    ledger = SQLiteBrowserRecoveryLedger(private_dir / "browser.sqlite3")
    worker = Worker()
    coordinator = BrowserExecutionCoordinator(
        worker, audit=lambda event: None, recovery_ledger=ledger,
        approval_authority=authority, owner_principal=principal,
        owner_tenant=tenant, session_scope=scope,
        owner_session_check=check_session,
    )
    job = {
        "job_id": "job_control_bridge_001",
        "url": "https://example.com/",
        "allowed_origins": ["https://example.com"],
        "action": "read_page_title",
        "expires_at": int(time.time()) + 180,
        "max_response_bytes": 4096,
        "max_runtime_seconds": 5,
    }
    return boundary, coordinator, worker, ledger, audit, active, job


def test_owner_control_boundary_issues_and_passes_exact_receipt_to_coordinator(tmp_path):
    private_dir = tmp_path / "private"
    private_dir.mkdir(mode=0o700)
    private_dir.chmod(0o700)
    boundary, coordinator, worker, ledger, audit, _active, job = _context(private_dir)

    receipt = boundary.request_approval(job, owner_confirmed=True)
    result = boundary.dispatch_with_approved_coordinator(
        job, approval_receipt=receipt, coordinator=coordinator,
        resolver=lambda host: ["93.184.216.34"],
    )

    assert result == {"title": "Example Domain"}
    assert len(worker.calls) == 1
    assert len(ledger.list_approval_correlations(job["job_id"])) == 1
    assert audit.verify() != JsonlAuditLog.GENESIS


def test_owner_control_boundary_rejects_coordinator_with_different_session_context(tmp_path):
    private_dir = tmp_path / "private"
    private_dir.mkdir(mode=0o700)
    private_dir.chmod(0o700)
    boundary, coordinator, worker, _ledger, _audit, _active, job = _context(private_dir)
    receipt = boundary.request_approval(job, owner_confirmed=True)

    other_dir = tmp_path / "other"
    other_dir.mkdir(mode=0o700)
    other_dir.chmod(0o700)
    other_authority = ApprovalAuthority(
        nonce_store=SQLiteSecurityStore(other_dir / "security.sqlite3"),
        signing_secret=b"APAA different browser control secret 32 bytes",
    )
    other_tenant = TenantKey("https://apaa.test", "owner-1")
    other_principal = Principal("owner-1", "https://apaa.test", True, ("owner",))
    other_session_check = lambda: True
    other_coordinator = BrowserExecutionCoordinator(
        Worker(), audit=lambda event: None,
        recovery_ledger=SQLiteBrowserRecoveryLedger(other_dir / "browser.sqlite3"),
        approval_authority=other_authority, owner_principal=other_principal,
        owner_tenant=other_tenant, session_scope="other-owner-session-001",
        owner_session_check=other_session_check,
    )

    with pytest.raises(BrowserControlSecurityError, match="context does not match"):
        boundary.dispatch_with_approved_coordinator(
            job, approval_receipt=receipt, coordinator=other_coordinator,
            resolver=lambda host: ["93.184.216.34"],
        )
    assert worker.calls == []


def test_owner_control_boundary_rechecks_session_before_coordinator_dispatch(tmp_path):
    private_dir = tmp_path / "private"
    private_dir.mkdir(mode=0o700)
    private_dir.chmod(0o700)
    boundary, coordinator, worker, _ledger, _audit, active, job = _context(private_dir)
    receipt = boundary.request_approval(job, owner_confirmed=True)
    active["value"] = False

    with pytest.raises(BrowserControlSecurityError, match="inactive or expired"):
        boundary.dispatch_with_approved_coordinator(
            job, approval_receipt=receipt, coordinator=coordinator,
            resolver=lambda host: ["93.184.216.34"],
        )
    assert worker.calls == []


def test_owner_control_boundary_requires_explicit_confirmation_and_durable_nonce_store(tmp_path):
    private_dir = tmp_path / "private"
    private_dir.mkdir(mode=0o700)
    private_dir.chmod(0o700)
    boundary, coordinator, worker, _ledger, _audit, _active, job = _context(private_dir)

    with pytest.raises(BrowserControlSecurityError, match="explicit Owner confirmation"):
        boundary.request_approval(job, owner_confirmed=False)

    # The production bridge verifies the authority is durable before delegating.
    boundary._approval_authority = ApprovalAuthority(
        signing_secret=b"APAA in-memory approval secret at least 32 bytes",
    )
    with pytest.raises(BrowserControlSecurityError, match="Durable approval nonce"):
        boundary.dispatch_with_approved_coordinator(
            job, approval_receipt=None, coordinator=coordinator,
            resolver=lambda host: ["93.184.216.34"],
        )
    assert worker.calls == []
