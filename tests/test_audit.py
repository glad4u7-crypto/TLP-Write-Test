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
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert len(records) == 64
    assert len(set(hashes)) == 64
    assert verifier.verify() == records[-1]["entry_hash"]

@pytest.mark.skipif(os.name != "posix", reason="POSIX directory permissions required")
def test_jsonl_audit_log_rejects_shared_parent_directory(tmp_path):
    shared_dir = tmp_path / "shared-audit"
    shared_dir.mkdir(mode=0o700)
    shared_dir.chmod(0o755)
    log = JsonlAuditLog(shared_dir / "events.jsonl")

    with pytest.raises(AuditIntegrityError, match="owner-only"):
        log.append(create_audit_event("write_file", False, "denied"))

    assert not (shared_dir / "events.jsonl").exists()


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="symlinks unavailable")
def test_jsonl_audit_log_rejects_symlinked_parent_directory(tmp_path):
    target_dir = tmp_path / "actual-audit"
    target_dir.mkdir(mode=0o700)
    link_dir = tmp_path / "linked-audit"
    try:
        link_dir.symlink_to(target_dir, target_is_directory=True)
    except OSError:
        pytest.skip("directory symlink creation is not permitted in this environment")

    log = JsonlAuditLog(link_dir / "events.jsonl")
    with pytest.raises(AuditIntegrityError, match="parent path.*symlinks"):
        log.append(create_audit_event("write_file", False, "denied"))

    assert not (target_dir / "events.jsonl").exists()


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="symlinks unavailable")
def test_jsonl_audit_log_verify_rejects_symlinked_parent_directory(tmp_path):
    target_dir = tmp_path / "actual-audit-verify"
    target_dir.mkdir(mode=0o700)
    link_dir = tmp_path / "linked-audit-verify"
    try:
        link_dir.symlink_to(target_dir, target_is_directory=True)
    except OSError:
        pytest.skip("directory symlink creation is not permitted in this environment")

    log = JsonlAuditLog(link_dir / "events.jsonl")
    with pytest.raises(AuditIntegrityError, match="parent path.*symlinks"):
        log.verify()




def test_jsonl_audit_path_is_anchored_when_working_directory_changes(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    log = JsonlAuditLog("relative-audit/events.jsonl")
    expected_path = tmp_path / "relative-audit" / "events.jsonl"
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()

    monkeypatch.chdir(elsewhere)
    log.append(create_audit_event("path.anchor", False, "cwd changed"))

    assert expected_path.is_file()
    assert not (elsewhere / "relative-audit" / "events.jsonl").exists()



@pytest.mark.skipif(not hasattr(os, "symlink"), reason="symlinks unavailable")
def test_jsonl_audit_rejects_parent_directory_symlink_replacement_after_init(tmp_path):
    original_parent = tmp_path / "private-audit"
    original_parent.mkdir(mode=0o700)
    log = JsonlAuditLog(original_parent / "events.jsonl")
    log.append(create_audit_event("before.rename", False, "baseline"))

    moved_parent = tmp_path / "moved-private-audit"
    original_parent.rename(moved_parent)
    try:
        original_parent.symlink_to(moved_parent, target_is_directory=True)
    except OSError:
        moved_parent.rename(original_parent)
        pytest.skip("directory symlink creation is not permitted in this environment")

    with pytest.raises(AuditIntegrityError, match="parent path.*symlinks"):
        log.append(create_audit_event("after.rename", False, "must reject"))
    assert len((moved_parent / "events.jsonl").read_text(encoding="utf-8").splitlines()) == 1


def test_jsonl_audit_log_fails_closed_on_truncated_trailing_record(tmp_path):
    path = tmp_path / "events.jsonl"
    log = JsonlAuditLog(path)
    log.append(create_audit_event("before.crash", False, "complete record"))
    with path.open("a", encoding="utf-8") as stream:
        stream.write('{"event":{"action":"partial')
        stream.flush()
        os.fsync(stream.fileno())

    with pytest.raises(AuditIntegrityError, match="cannot be read|parsed"):
        log.verify()
    with pytest.raises(AuditIntegrityError):
        log.append(create_audit_event("after.crash", False, "must not append"))
