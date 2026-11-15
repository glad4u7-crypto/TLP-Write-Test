import json
import os
from concurrent.futures import ThreadPoolExecutor

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


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="symlinks unavailable")
def test_jsonl_audit_log_rejects_symlink_target(tmp_path):
    target = tmp_path / "outside.jsonl"
    target.write_text("")
    link = tmp_path / "audit.jsonl"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("symlink creation is not permitted in this environment")

    log = JsonlAuditLog(link)
    with pytest.raises(AuditIntegrityError):
        log.append(create_audit_event("write_file", False, "denied"))
    assert target.read_text() == ""


def test_jsonl_audit_log_restricts_file_permissions(tmp_path):
    log = JsonlAuditLog(tmp_path / "private" / "events.jsonl")
    log.append(create_audit_event("write_file", False, "denied"))

    if os.name == "posix":
        assert (tmp_path / "private" / "events.jsonl").stat().st_mode & 0o777 == 0o600


def test_multiple_log_instances_serialize_concurrent_appends(tmp_path):
    path = tmp_path / "shared" / "events.jsonl"
    logs = [JsonlAuditLog(path) for _ in range(8)]

    def append_one(index):
        return logs[index % len(logs)].append(
            create_audit_event("write_file", False, f"event-{index}")
        )

    with ThreadPoolExecutor(max_workers=16) as pool:
        hashes = list(pool.map(append_one, range(64)))

    verifier = JsonlAuditLog(path)
    assert len(hashes) == 64
    assert verifier.verify() == hashes[-1] or verifier.verify() in hashes
    records = path.read_text(encoding="utf-8").splitlines()
    assert len(records) == 64
