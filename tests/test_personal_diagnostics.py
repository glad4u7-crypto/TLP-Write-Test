from __future__ import annotations

import os
from pathlib import Path
import sqlite3

from core.personal_diagnostics import diagnostics_summary, inspect_personal_runtime
from core.personal_runtime import personal_runtime_paths


def _private_dir(path: Path) -> Path:
    path.mkdir(mode=0o700)
    if os.name == "posix":
        path.chmod(0o700)
    return path


def test_uninitialized_runtime_is_info_and_is_not_created(tmp_path):
    target = tmp_path / "not-created"
    results = inspect_personal_runtime(target)
    assert [(item.code, item.status) for item in results] == [("data_dir", "INFO")]
    assert not target.exists()


def test_healthy_runtime_checks_databases_and_key_without_exposing_key(tmp_path):
    root = _private_dir(tmp_path / "owner-data")
    paths = personal_runtime_paths(root)
    for field in ("projects_db", "security_db", "owner_auth_db", "memory_db"):
        db_path = getattr(paths, field)
        with sqlite3.connect(db_path) as db:
            db.execute("CREATE TABLE sample (value TEXT)")
            db.execute("INSERT INTO sample VALUES ('private')")
    paths.signing_key.write_bytes(b"x" * 32)
    paths.signing_key.chmod(0o600)
    paths.audit_log.write_text('{"event":"test"}\n', encoding="utf-8")

    results = inspect_personal_runtime(root)
    by_code = {item.code: item for item in results}
    assert by_code["data_dir"].status == "PASS"
    assert all(by_code[field].status == "PASS" for field in (
        "projects_db", "security_db", "owner_auth_db", "memory_db"
    ))
    assert by_code["signing_key"].status == "PASS"
    assert by_code["audit_log"].status == "PASS"
    assert "xxxxxxxx" not in " ".join(item.detail for item in results)


def test_corrupt_sqlite_database_fails_closed(tmp_path):
    root = _private_dir(tmp_path / "owner-data")
    paths = personal_runtime_paths(root)
    paths.projects_db.write_bytes(b"not a sqlite database")
    results = inspect_personal_runtime(root)
    by_code = {item.code: item for item in results}
    assert by_code["projects_db"].status == "FAIL"


def test_symlink_database_is_rejected(tmp_path):
    root = _private_dir(tmp_path / "owner-data")
    paths = personal_runtime_paths(root)
    outside = tmp_path / "outside.sqlite3"
    with sqlite3.connect(outside) as db:
        db.execute("CREATE TABLE sample (value TEXT)")
    paths.projects_db.symlink_to(outside)
    results = inspect_personal_runtime(root)
    by_code = {item.code: item for item in results}
    assert by_code["projects_db"].status == "FAIL"


def test_insecure_data_directory_fails_closed_on_posix(tmp_path):
    root = tmp_path / "owner-data"
    root.mkdir(mode=0o755)
    if os.name == "posix":
        root.chmod(0o755)
        results = inspect_personal_runtime(root)
        assert results[0].status == "FAIL"


def test_diagnostics_summary_counts_statuses():
    results = inspect_personal_runtime(Path("/path/that/does/not/exist"))
    assert diagnostics_summary(results) == (0, 0, 1)
