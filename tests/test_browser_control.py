from __future__ import annotations

import pytest

from core.approvals import ApprovalAuthority
from core.browser_control import (
    BROWSER_APPROVAL_ACTION,
    BrowserControlBoundary,
    BrowserControlSecurityError,
)
from core.identity import Principal
from core.personal_runtime import PERSONAL_OWNER_TENANT
from core.sqlite_security_store import SQLiteExecutionAuditLog, SQLiteSecurityStore


def _boundary(tmp_path, *, active=lambda: True, owner_verified=True):
    security = SQLiteSecurityStore(tmp_path / "security.sqlite3")
    authority = ApprovalAuthority(
        nonce_store=security,
        signing_secret=b"browser-control-test-signing-key-32-bytes",
    )
    audit = SQLiteExecutionAuditLog(security, PERSONAL_OWNER_TENANT)
    owner = Principal(
        subject=PERSONAL_OWNER_TENANT.subject,
        issuer=PERSONAL_OWNER_TENANT.issuer,
        authenticated=True,
        roles=("owner",),
    )
    boundary = BrowserControlBoundary(
        owner_principal=owner,
        owner_tenant=PERSONAL_OWNER_TENANT,
        owner_verified=owner_verified,
        session_scope="owner-session-test-001",
        approval_authority=authority,
        audit_log=audit,
        owner_session_check=active,
    )
    return boundary, security, audit


def _job(now=1000):
    return {
        "job_id": "browser-job-0001",
        "url": "https://example.com/",
        "allowed_origins": ["https://example.com"],
        "action": "read_page_title",
        "expires_at": now + 90,
        "max_response_bytes": 4096,
        "max_runtime_seconds": 10,
    }


def test_browser_boundary_requires_trusted_owner_verification(tmp_path):
    with pytest.raises(BrowserControlSecurityError):
        _boundary(tmp_path, owner_verified=False)


def test_browser_boundary_rejects_inactive_owner_session(tmp_path):
    boundary, _, _ = _boundary(tmp_path, active=lambda: False)
    with pytest.raises(BrowserControlSecurityError):
        boundary.request_approval(_job(), owner_confirmed=True, now=1000)


def test_browser_boundary_requires_explicit_fresh_owner_confirmation(tmp_path):
    boundary, _, _ = _boundary(tmp_path)
    with pytest.raises(BrowserControlSecurityError):
        boundary.request_approval(_job(), owner_confirmed=False, now=1000)


def test_browser_approval_is_bound_to_exact_job_and_audits_rejection(tmp_path):
    boundary, security, audit = _boundary(tmp_path)
    job = _job()
    receipt = boundary.request_approval(job, owner_confirmed=True, now=1000)
    assert receipt.action == BROWSER_APPROVAL_ACTION

    changed = dict(job, url="https://example.com/changed")
    result = boundary.dispatch(changed, approval_receipt=receipt, now=1001)
    assert result.executed is False
    assert "approval" in result.reason.lower()
    assert security.verify_audit_chain() is True
    assert audit.verify() != audit.GENESIS


def test_browser_receipt_is_consumed_once_and_handler_remains_disabled(tmp_path):
    boundary, security, audit = _boundary(tmp_path)
    job = _job()
    receipt = boundary.request_approval(job, owner_confirmed=True, now=1000)

    first = boundary.dispatch(job, approval_receipt=receipt, now=1001)
    second = boundary.dispatch(job, approval_receipt=receipt, now=1002)

    assert boundary.browser_handler_enabled is False
    assert first.executed is False
    assert "handler is registered" in first.reason.lower()
    assert second.executed is False
    assert "approval" in second.reason.lower()
    assert security.verify_audit_chain() is True
    assert audit.verify() != audit.GENESIS
    events = audit.list_recent_events(limit=10)
    assert any(event["action"] == BROWSER_APPROVAL_ACTION for event in events)


def test_browser_boundary_rejects_expired_job_and_unsafe_destination(tmp_path):
    boundary, _, _ = _boundary(tmp_path)
    with pytest.raises(ValueError):
        boundary.request_approval(_job(), owner_confirmed=True, now=1090)
    unsafe = dict(_job(), url="http://127.0.0.1/")
    with pytest.raises(ValueError):
        boundary.request_approval(unsafe, owner_confirmed=True, now=1000)


def test_browser_boundary_rejects_owner_tenant_mismatch(tmp_path):
    security = SQLiteSecurityStore(tmp_path / "security.sqlite3")
    authority = ApprovalAuthority(
        nonce_store=security,
        signing_secret=b"browser-control-test-signing-key-32-bytes",
    )
    audit = SQLiteExecutionAuditLog(security, PERSONAL_OWNER_TENANT)
    other = Principal(
        subject="someone-else",
        issuer=PERSONAL_OWNER_TENANT.issuer,
        authenticated=True,
        roles=("owner",),
    )
    with pytest.raises(BrowserControlSecurityError):
        BrowserControlBoundary(
            owner_principal=other,
            owner_tenant=PERSONAL_OWNER_TENANT,
            owner_verified=True,
            session_scope="owner-session-test-001",
            approval_authority=authority,
            audit_log=audit,
            owner_session_check=lambda: True,
        )


def test_browser_read_can_never_use_auto_run_even_if_listed():
    from core.safety import authorize_action

    decision = authorize_action(
        BROWSER_APPROVAL_ACTION,
        auto_run=True,
        auto_run_actions=(BROWSER_APPROVAL_ACTION,),
    )
    assert decision.allowed is False
    assert "fresh explicit Owner approval" in decision.reason
