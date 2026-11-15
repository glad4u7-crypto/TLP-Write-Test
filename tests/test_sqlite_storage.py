import sqlite3

import pytest

from core.storage import ProjectStore, TenantKey
from core.sqlite_storage import SQLiteProjectStore


@pytest.fixture
def store(tmp_path):
    return SQLiteProjectStore(tmp_path / "projects.sqlite3")


def test_sqlite_store_implements_project_store_protocol(store):
    assert isinstance(store, ProjectStore)


def test_create_list_and_get_are_persistent_and_tenant_scoped(store, tmp_path):
    tenant = TenantKey("https://issuer-a.example", "alice")
    project = store.create(tenant, name="Private project", description="secret-free")
    reopened = SQLiteProjectStore(tmp_path / "projects.sqlite3")
    assert reopened.get_for_tenant(tenant, project.project_id) == project
    assert reopened.list_for_tenant(tenant) == [project]


def test_same_subject_from_different_issuer_cannot_read_project(store):
    owner = TenantKey("https://issuer-a.example", "alice")
    attacker = TenantKey("https://issuer-b.example", "alice")
    project = store.create(owner, name="Owner data")
    assert store.get_for_tenant(attacker, project.project_id) is None
    assert store.list_for_tenant(attacker) == []


def test_cross_tenant_update_and_delete_are_denied(store):
    owner = TenantKey("https://issuer-a.example", "alice")
    other = TenantKey("https://issuer-a.example", "bob")
    project = store.create(owner, name="Original")
    assert store.update_for_tenant(other, project.project_id, name="Hijack", description="") is None
    assert store.delete_for_tenant(other, project.project_id) is False
    assert store.get_for_tenant(owner, project.project_id).name == "Original"


def test_owner_can_update_and_delete(store):
    owner = TenantKey("https://issuer.example", "alice")
    project = store.create(owner, name="Before")
    updated = store.update_for_tenant(owner, project.project_id, name="After", description="updated")
    assert updated.name == "After"
    assert store.delete_for_tenant(owner, project.project_id) is True
    assert store.get_for_tenant(owner, project.project_id) is None


@pytest.mark.parametrize("name,description", [("", ""), ("x" * 81, ""), ("ok", "x" * 501)])
def test_invalid_project_fields_are_rejected(store, name, description):
    tenant = TenantKey("https://issuer.example", "alice")
    with pytest.raises(ValueError):
        store.create(tenant, name=name, description=description)


def test_sql_is_parameterized_and_no_owner_is_taken_from_payload(store):
    tenant = TenantKey("https://issuer.example", "alice")
    project = store.create(tenant, name="'; DROP TABLE projects; --")
    assert store.get_for_tenant(tenant, project.project_id) is not None
    assert len(store.list_for_tenant(tenant)) == 1


def test_project_database_file_permissions_are_restricted(tmp_path):
    import os

    path = tmp_path / "private" / "projects.sqlite3"
    SQLiteProjectStore(path)
    if os.name == "posix":
        assert path.stat().st_mode & 0o777 == 0o600


@pytest.mark.skipif(not hasattr(__import__("os"), "symlink"), reason="symlinks unavailable")
def test_project_database_rejects_symlink_target(tmp_path):
    target = tmp_path / "outside.sqlite3"
    target.write_bytes(b"do-not-open")
    link = tmp_path / "projects.sqlite3"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("symlink creation is not permitted in this environment")

    with pytest.raises(ValueError, match="non-symlink"):
        SQLiteProjectStore(link)
    assert target.read_bytes() == b"do-not-open"


@pytest.mark.skipif(not hasattr(__import__("os"), "symlink"), reason="symlinks unavailable")
def test_sqlite_store_preexisting_database_permissions_are_restricted(tmp_path):
    import os

    path = tmp_path / "existing.sqlite3"
    path.write_bytes(b"")
    if os.name == "posix":
        path.chmod(0o644)

    SQLiteProjectStore(path)

    if os.name == "posix":
        assert path.stat().st_mode & 0o777 == 0o600


def test_sqlite_store_rejects_symlinked_parent_directory(tmp_path):
    target_dir = tmp_path / "actual"
    target_dir.mkdir()
    link_dir = tmp_path / "linked"
    try:
        link_dir.symlink_to(target_dir, target_is_directory=True)
    except OSError:
        pytest.skip("directory symlink creation is not permitted in this environment")

    with pytest.raises(ValueError, match="parent path.*symlinks"):
        SQLiteProjectStore(link_dir / "projects.sqlite3")
    assert not (target_dir / "projects.sqlite3").exists()


@pytest.mark.skipif(__import__("os").name != "posix", reason="POSIX directory permissions required")
def test_legacy_project_database_rejects_shared_parent_directory(tmp_path):
    shared_dir = tmp_path / "shared"
    shared_dir.mkdir(mode=0o700)
    shared_dir.chmod(0o755)

    with pytest.raises(ValueError, match="parent directory must be owner-only"):
        SQLiteProjectStore(shared_dir / "projects.sqlite3")

    assert not (shared_dir / "projects.sqlite3").exists()


@pytest.mark.skipif(__import__("os").name != "posix", reason="POSIX file permissions required")
def test_legacy_sqlite_wal_sidecars_have_owner_only_permissions(tmp_path):
    import os

    path = tmp_path / "projects.sqlite3"
    store = SQLiteProjectStore(path)
    connection = store._connect()
    try:
        assert connection.execute("PRAGMA journal_mode=WAL").fetchone()[0].lower() == "wal"
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("CREATE TABLE sidecar_permission_probe (value TEXT)")

        for suffix in ("-wal", "-shm"):
            sidecar = path.with_name(path.name + suffix)
            assert sidecar.exists()
            assert sidecar.stat().st_mode & 0o777 == 0o600
        assert path.stat().st_mode & 0o777 == 0o600
    finally:
        connection.rollback()
        connection.close()


@pytest.mark.skipif(__import__("os").name != "posix", reason="POSIX file permissions required")
def test_legacy_sqlite_rollback_journal_has_owner_only_permissions(tmp_path):
    import os

    path = tmp_path / "rollback-journal.sqlite3"
    store = SQLiteProjectStore(path)
    connection = store._connect()
    try:
        assert connection.execute("PRAGMA journal_mode=DELETE").fetchone()[0].lower() == "delete"
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("CREATE TABLE rollback_journal_permission_probe (value TEXT)")

        journal = path.with_name(path.name + "-journal")
        assert journal.exists()
        assert journal.stat().st_mode & 0o777 == 0o600
        assert path.stat().st_mode & 0o777 == 0o600
    finally:
        connection.rollback()
        connection.close()
