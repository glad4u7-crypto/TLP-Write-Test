from __future__ import annotations

import pytest

from core.ui_mutations import UIActionAuditError, execute_audited_ui_mutation


class RecordingAudit:
    def __init__(self):
        self.events = []
        self.fail_at = None

    def append(self, event):
        if self.fail_at == len(self.events):
            raise OSError("audit store unavailable")
        self.events.append(event)


def test_ui_mutation_records_intent_and_completion_without_payload():
    audit = RecordingAudit()
    calls = []
    result = execute_audited_ui_mutation(
        audit, "memory.add", True, lambda: calls.append("saved") or "ok"
    )
    assert result == "ok"
    assert calls == ["saved"]
    assert [event.reason for event in audit.events] == [
        "ui_mutation_pending", "ui_mutation_completed"
    ]
    assert all(not hasattr(event, "payload") for event in audit.events)


def test_ui_mutation_is_blocked_when_intent_audit_cannot_be_written():
    audit = RecordingAudit()
    audit.fail_at = 0
    calls = []
    with pytest.raises(UIActionAuditError, match="change was blocked"):
        execute_audited_ui_mutation(
            audit, "memory.delete", True, lambda: calls.append("deleted")
        )
    assert calls == []
    assert audit.events == []


def test_ui_mutation_records_failure_without_claiming_success():
    audit = RecordingAudit()

    def fail():
        raise ValueError("invalid user data")

    with pytest.raises(ValueError, match="invalid user data"):
        execute_audited_ui_mutation(audit, "memory.add", True, fail)
    assert [event.reason for event in audit.events] == [
        "ui_mutation_pending", "ui_mutation_failed"
    ]
    assert not any(event.executed for event in audit.events)


def test_ui_mutation_reports_completion_audit_failure_for_manual_review():
    audit = RecordingAudit()
    audit.fail_at = 1
    calls = []
    with pytest.raises(UIActionAuditError, match="may have completed"):
        execute_audited_ui_mutation(
            audit, "memory.delete", True, lambda: calls.append("deleted")
        )
    assert calls == ["deleted"]
    assert [event.reason for event in audit.events] == ["ui_mutation_pending"]



def test_sqlite_audit_distinguishes_pending_and_completed_ui_mutations(tmp_path):
    import sqlite3

    from core.personal_runtime import PERSONAL_OWNER_TENANT
    from core.sqlite_security_store import SQLiteExecutionAuditLog, SQLiteSecurityStore

    store = SQLiteSecurityStore(tmp_path / "security.sqlite3")
    audit = SQLiteExecutionAuditLog(store, PERSONAL_OWNER_TENANT)
    execute_audited_ui_mutation(audit, "memory.add", True, lambda: "saved")

    with sqlite3.connect(tmp_path / "security.sqlite3") as db:
        rows = db.execute(
            "SELECT result, reason_code FROM durable_audit_events ORDER BY sequence"
        ).fetchall()
    assert rows == [
        ("pending", "ui_mutation_pending"),
        ("success", "ui_mutation_completed"),
    ]
    assert store.verify_audit_chain()



@pytest.mark.parametrize("action", ["payment.transfer", "trading.place_order", "run_shell"])
def test_ui_mutation_cannot_bypass_global_or_unknown_action_denials(action):
    audit = RecordingAudit()
    calls = []
    with pytest.raises(UIActionAuditError):
        execute_audited_ui_mutation(
            audit, action, True, lambda: calls.append("must-not-run")
        )
    assert calls == []
    assert audit.events == []



def test_ui_mutation_requires_explicit_owner_approval_before_audit_or_dispatch():
    audit = RecordingAudit()
    calls = []
    with pytest.raises(UIActionAuditError, match="requires approval"):
        execute_audited_ui_mutation(
            audit, "memory.add", False, lambda: calls.append("must-not-run")
        )
    assert calls == []
    assert audit.events == []


def test_ui_mutation_rejects_non_boolean_approval_argument():
    audit = RecordingAudit()
    with pytest.raises(ValueError, match="boolean"):
        execute_audited_ui_mutation(audit, "memory.add", "yes", lambda: None)
    assert audit.events == []


def test_action_history_is_tenant_scoped_payload_free_and_hash_verified(tmp_path):
    import sqlite3

    from core.personal_runtime import PERSONAL_OWNER_TENANT
    from core.sqlite_security_store import SQLiteExecutionAuditLog, SQLiteSecurityStore

    database = tmp_path / "security.sqlite3"
    store = SQLiteSecurityStore(database)
    audit = SQLiteExecutionAuditLog(store, PERSONAL_OWNER_TENANT)
    execute_audited_ui_mutation(
        audit, "memory.add", True,
        lambda: {"private_content": "must never enter audit history"},
    )

    events = audit.list_recent_events(limit=10)
    assert [event["reason_code"] for event in events] == [
        "ui_mutation_completed", "ui_mutation_pending"
    ]
    assert all(event["action"] == "memory.add" for event in events)
    assert all(event["result"] in {"pending", "success"} for event in events)
    assert "private_content" not in repr(events)
    assert all("entry_hash" in event for event in events)

    with sqlite3.connect(database) as db:
        db.execute(
            "UPDATE durable_audit_events SET reason_code = ? WHERE sequence = 1",
            ("tampered",),
        )
        db.commit()
    with pytest.raises(ValueError, match="hash"):
        audit.list_recent_events(limit=10)


def test_action_history_rejects_invalid_limit_and_fingerprint(tmp_path):
    from core.personal_runtime import PERSONAL_OWNER_TENANT
    from core.sqlite_security_store import SQLiteExecutionAuditLog, SQLiteSecurityStore

    audit = SQLiteExecutionAuditLog(
        SQLiteSecurityStore(tmp_path / "security.sqlite3"), PERSONAL_OWNER_TENANT
    )
    with pytest.raises(ValueError, match="limit"):
        audit.list_recent_events(limit=0)
