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
        audit, "memory.add", lambda: calls.append("saved") or "ok"
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
            audit, "memory.delete", lambda: calls.append("deleted")
        )
    assert calls == []
    assert audit.events == []


def test_ui_mutation_records_failure_without_claiming_success():
    audit = RecordingAudit()

    def fail():
        raise ValueError("invalid user data")

    with pytest.raises(ValueError, match="invalid user data"):
        execute_audited_ui_mutation(audit, "memory.add", fail)
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
            audit, "memory.delete", lambda: calls.append("deleted")
        )
    assert calls == ["deleted"]
    assert [event.reason for event in audit.events] == ["ui_mutation_pending"]
