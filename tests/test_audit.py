import json

import pytest

from core.audit import (
    AuditIntegrityError,
    JsonlAuditLog,
    create_audit_event,
)


def test_jsonl_audit_log_appends_and_verifies_chain(tmp_path):
    log = JsonlAuditLog(tmp_path / "audit" / "events.jsonl")
    first = create_audit_event("write_file", False, "approval missing")
    second = create_audit_event("write_file", True, "approved")

    first_hash = log.append(first)
    second_hash = log.append(second)

    assert first_hash != second_hash
    assert log.verify() == second_hash
    records = [
        json.loads(line)
        for line in (tmp_path / "audit" / "events.jsonl").read_text().splitlines()
    ]
    assert len(records) == 2
    assert "payload" not in repr(records)
    assert "secret" not in repr(records)


def test_jsonl_audit_log_detects_tampered_event(tmp_path):
    path = tmp_path / "events.jsonl"
    log = JsonlAuditLog(path)
    log.append(create_audit_event("write_file", False, "denied"))

    record = json.loads(path.read_text())
    record["event"]["reason"] = "tampered"
    path.write_text(json.dumps(record) + "\n")

    with pytest.raises(AuditIntegrityError):
        log.verify()


def test_jsonl_audit_log_detects_deleted_or_reordered_chain_entry(tmp_path):
    path = tmp_path / "events.jsonl"
    log = JsonlAuditLog(path)
    log.append(create_audit_event("write_file", False, "first"))
    log.append(create_audit_event("write_file", True, "second"))

    records = path.read_text().splitlines()
    path.write_text(records[1] + "\n")

    with pytest.raises(AuditIntegrityError):
        log.verify()


def test_jsonl_audit_log_rejects_non_event_objects(tmp_path):
    log = JsonlAuditLog(tmp_path / "events.jsonl")
    with pytest.raises(TypeError):
        log.append({"action": "write_file"})
