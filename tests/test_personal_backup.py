from __future__ import annotations

import json
import sqlite3
import zipfile

import pytest

from core.audit import create_audit_event
from core.identity import Principal
from core.memory import SQLiteMemoryStore
from core.personal_auth import LocalOwnerAuthStore
from core.personal_backup import (
    PersonalBackupError,
    create_personal_backup,
    restore_personal_backup,
)
from core.personal_runtime import (
    PERSONAL_OWNER_TENANT,
    load_or_create_approval_signing_key,
    personal_runtime_paths,
)
from core.project_checkpoint_access import OwnerProjectCheckpointAccess
from core.sqlite_project_store import SQLiteProjectStore
from core.sqlite_security_store import SQLiteExecutionAuditLog, SQLiteSecurityStore


def _seed_runtime(data_dir):
    paths = personal_runtime_paths(data_dir)
    LocalOwnerAuthStore(paths.owner_auth_db).configure(
        "test-only owner passphrase", "test-only owner passphrase"
    )
    original_key = load_or_create_approval_signing_key(paths.data_dir)
    projects = SQLiteProjectStore(paths.projects_db)
    project = projects.create(
        PERSONAL_OWNER_TENANT, name="Backup workspace", description="Persist me"
    )
    memory = SQLiteMemoryStore(paths.memory_db)
    memory.add_memory(
        PERSONAL_OWNER_TENANT, category="project", content="Backup memory",
        tags=["backup"], consent=True,
    )
    memory.save_checkpoint(
        PERSONAL_OWNER_TENANT, project_id=project.project_id,
        label="P73", summary="Saved state", next_action="Restore and verify",
        consent=True,
    )
    security = SQLiteSecurityStore(paths.security_db)
    audit = SQLiteExecutionAuditLog(security, PERSONAL_OWNER_TENANT)
    audit.append(create_audit_event("create_project", True, "action_executed"))
    return paths, original_key, project, audit


def test_backup_restore_recovers_projects_memory_checkpoints_and_audit(tmp_path):
    source_dir = tmp_path / "source"
    paths, original_key, project, audit = _seed_runtime(source_dir)
    backup_dir = tmp_path / "exports"
    backup = create_personal_backup(source_dir, backup_dir / "owner.apaa-backup")

    with zipfile.ZipFile(backup) as archive:
        assert set(archive.namelist()) == {
            "projects.sqlite3", "security.sqlite3", "owner-auth.sqlite3", "memory.sqlite3", "manifest.json"
        }
        assert "approval-signing.key" not in archive.namelist()

    restore_parent = tmp_path / "restore-parent"
    restore_parent.mkdir(mode=0o700)
    restored_dir = restore_personal_backup(backup, restore_parent / "restored")
    restored = personal_runtime_paths(restored_dir)

    projects = SQLiteProjectStore(restored.projects_db)
    assert projects.get_for_tenant(PERSONAL_OWNER_TENANT, project.project_id) == project
    memory = SQLiteMemoryStore(restored.memory_db)
    assert [item.content for item in memory.list_memories(PERSONAL_OWNER_TENANT)] == [
        "Backup memory"
    ]
    owner = Principal(
        subject=PERSONAL_OWNER_TENANT.subject,
        issuer=PERSONAL_OWNER_TENANT.issuer,
        authenticated=True,
        roles=("owner",),
    )
    checkpoints = OwnerProjectCheckpointAccess(memory, projects, owner)
    checkpoint = checkpoints.latest_checkpoint(project.project_id)
    assert checkpoint is not None
    assert checkpoint.summary == "Saved state"

    security = SQLiteSecurityStore(restored.security_db)
    restored_audit = SQLiteExecutionAuditLog(security, PERSONAL_OWNER_TENANT)
    assert restored_audit.verify() == audit.verify()
    restored_key = load_or_create_approval_signing_key(restored_dir)
    restored_owner_auth = LocalOwnerAuthStore(restored.owner_auth_db)
    assert restored_owner_auth.authenticate("test-only owner passphrase") is True
    assert restored_owner_auth.authenticate("incorrect owner passphrase") is False
    assert restored_key != original_key
    assert (restored_dir / "approval-signing.key").stat().st_mode & 0o077 == 0
    assert restored_dir.stat().st_mode & 0o077 == 0


def test_restore_rejects_tampered_backup_and_leaves_no_destination(tmp_path):
    source_dir = tmp_path / "source"
    _seed_runtime(source_dir)
    backup = create_personal_backup(source_dir, tmp_path / "exports" / "owner.apaa-backup")
    tampered = tmp_path / "exports" / "tampered.apaa-backup"
    with zipfile.ZipFile(backup, "r") as source, zipfile.ZipFile(tampered, "w") as target:
        for info in source.infolist():
            data = source.read(info.filename)
            if info.filename == "projects.sqlite3":
                data += b"tampered"
            target.writestr(info.filename, data)
    tampered.chmod(0o600)
    restore_parent = tmp_path / "restore-parent"
    restore_parent.mkdir(mode=0o700)
    destination = restore_parent / "restored"

    with pytest.raises(PersonalBackupError):
        restore_personal_backup(tampered, destination)
    assert not destination.exists()


def test_backup_refuses_corrupt_audit_chain(tmp_path):
    source_dir = tmp_path / "source"
    paths, _, _, _ = _seed_runtime(source_dir)
    with sqlite3.connect(paths.security_db) as db:
        db.execute(
            "UPDATE durable_audit_events SET entry_hash = ? WHERE sequence = 1",
            ("f" * 64,),
        )
    with pytest.raises(PersonalBackupError, match="audit chain"):
        create_personal_backup(source_dir, tmp_path / "exports" / "invalid.apaa-backup")


def test_restore_never_overwrites_an_existing_data_directory(tmp_path):
    source_dir = tmp_path / "source"
    _seed_runtime(source_dir)
    backup = create_personal_backup(source_dir, tmp_path / "exports" / "owner.apaa-backup")
    destination = tmp_path / "restore-parent" / "existing"
    destination.mkdir(parents=True, mode=0o700)
    marker = destination / "keep.txt"
    marker.write_text("do not overwrite", encoding="utf-8")

    with pytest.raises(PersonalBackupError, match="must not already exist"):
        restore_personal_backup(backup, destination)
    assert marker.read_text(encoding="utf-8") == "do not overwrite"


def test_restore_legacy_v1_backup_requires_fresh_owner_setup(tmp_path):
    source_dir = tmp_path / "source"
    _seed_runtime(source_dir)
    current_backup = create_personal_backup(
        source_dir, tmp_path / "exports" / "current.apaa-backup"
    )
    legacy_backup = tmp_path / "exports" / "legacy-v1.apaa-backup"
    with zipfile.ZipFile(current_backup, "r") as source:
        manifest = json.loads(source.read("manifest.json").decode("utf-8"))
        manifest["version"] = 1
        manifest["files"].pop("owner-auth.sqlite3")
        with zipfile.ZipFile(legacy_backup, "w", compression=zipfile.ZIP_DEFLATED) as target:
            for filename in ("projects.sqlite3", "security.sqlite3", "memory.sqlite3"):
                target.writestr(filename, source.read(filename))
            target.writestr(
                "manifest.json",
                json.dumps(manifest, sort_keys=True, separators=(",", ":")),
            )
    legacy_backup.chmod(0o600)
    restore_parent = tmp_path / "restore-parent"
    restore_parent.mkdir(mode=0o700)
    restored_dir = restore_personal_backup(
        legacy_backup, restore_parent / "legacy-restored"
    )
    restored_paths = personal_runtime_paths(restored_dir)
    owner_auth = LocalOwnerAuthStore(restored_paths.owner_auth_db)
    assert owner_auth.is_configured() is False
    owner_auth.configure("new owner passphrase after restore", "new owner passphrase after restore")
    assert owner_auth.authenticate("new owner passphrase after restore") is True
