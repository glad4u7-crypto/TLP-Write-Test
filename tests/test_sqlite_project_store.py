from concurrent.futures import ThreadPoolExecutor
import multiprocessing
import sqlite3

import pytest

from core.storage import TenantKey
from core.sqlite_project_store import SQLiteProjectStore


@pytest.fixture
def tenants():
    return (
        TenantKey("https://issuer-one.example", "alice"),
        TenantKey("https://issuer-two.example", "alice"),
        TenantKey("https://issuer-one.example", "bob"),
    )


def test_project_crud_persists_after_store_reopen(tmp_path, tenants):
    path = tmp_path / "projects.sqlite3"
    alice, _, _ = tenants
    project = SQLiteProjectStore(path).create(
        alice, name="Persistent", description="survives restart"
    )
    reopened = SQLiteProjectStore(path)
    assert reopened.get_for_tenant(alice, project.project_id) == project
    updated = reopened.update_for_tenant(
        alice, project.project_id, name="Renamed", description="updated"
    )
    assert updated is not None and updated.name == "Renamed"
    assert SQLiteProjectStore(path).delete_for_tenant(alice, project.project_id)
    assert SQLiteProjectStore(path).get_for_tenant(alice, project.project_id) is None


def test_project_reads_and_mutations_are_isolated_by_issuer_and_subject(tmp_path, tenants):
    alice, other_issuer, bob = tenants
    store = SQLiteProjectStore(tmp_path / "tenant.sqlite3")
    project = store.create(alice, name="Alice", description="")
    assert store.get_for_tenant(other_issuer, project.project_id) is None
    assert store.get_for_tenant(bob, project.project_id) is None
    assert store.list_for_tenant(other_issuer) == []
    assert store.update_for_tenant(
        other_issuer, project.project_id, name="stolen", description=""
    ) is None
    assert not store.delete_for_tenant(bob, project.project_id)
    assert store.get_for_tenant(alice, project.project_id) == project


def test_projects_are_separated_by_tenant_in_lists(tmp_path, tenants):
    alice, other_issuer, bob = tenants
    store = SQLiteProjectStore(tmp_path / "list.sqlite3")
    p1 = store.create(alice, name="A", description="")
    p2 = store.create(other_issuer, name="B", description="")
    p3 = store.create(bob, name="C", description="")
    assert store.list_for_tenant(alice) == [p1]
    assert store.list_for_tenant(other_issuer) == [p2]
    assert store.list_for_tenant(bob) == [p3]


def test_invalid_tenant_and_project_fields_fail_closed(tmp_path):
    store = SQLiteProjectStore(tmp_path / "invalid.sqlite3")
    with pytest.raises(TypeError):
        store.list_for_tenant(("issuer", "alice"))
    tenant = TenantKey("https://issuer.example", "alice")
    with pytest.raises(ValueError):
        store.create(tenant, name=" ", description="")
    with pytest.raises(ValueError):
        store.create(tenant, name="x" * 81, description="")


def test_concurrent_creates_do_not_overwrite_projects(tmp_path, tenants):
    store = SQLiteProjectStore(tmp_path / "concurrent.sqlite3")
    tenant = tenants[0]
    def create(index):
        return store.create(tenant, name=f"Project {index}", description="")
    with ThreadPoolExecutor(max_workers=6) as pool:
        projects = list(pool.map(create, range(12)))
    assert len({project.project_id for project in projects}) == 12
    assert len(SQLiteProjectStore(tmp_path / "concurrent.sqlite3").list_for_tenant(tenant)) == 12


def test_project_database_file_permissions_are_restricted(tmp_path):
    import os

    path = tmp_path / "private" / "projects.sqlite3"
    SQLiteProjectStore(path)
    if os.name == "posix":
        assert path.stat().st_mode & 0o777 == 0o600


@pytest.mark.skipif(not hasattr(__import__("os"), "symlink"), reason="symlinks unavailable")
def test_project_database_preexisting_file_permissions_are_restricted(tmp_path):
    import os

    path = tmp_path / "project-existing.sqlite3"
    path.write_bytes(b"")
    if os.name == "posix":
        path.chmod(0o644)

    SQLiteProjectStore(path)

    if os.name == "posix":
        assert path.stat().st_mode & 0o777 == 0o600


@pytest.mark.skipif(__import__("os").name != "posix", reason="POSIX directory permissions required")
def test_project_database_rejects_shared_parent_directory(tmp_path):
    import os

    shared_dir = tmp_path / "shared"
    shared_dir.mkdir(mode=0o700)
    shared_dir.chmod(0o755)

    with pytest.raises(ValueError, match="parent directory must be owner-only"):
        SQLiteProjectStore(shared_dir / "projects.sqlite3")

    assert not (shared_dir / "projects.sqlite3").exists()


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


def test_project_database_rejects_symlinked_parent_directory(tmp_path):
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


@pytest.mark.skipif(__import__("os").name != "posix", reason="POSIX file permissions required")
def test_project_sqlite_wal_sidecars_have_owner_only_permissions(tmp_path):
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
def test_project_sqlite_rollback_journal_has_owner_only_permissions(tmp_path):
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


def test_project_update_and_delete_roll_back_when_sqlite_rejects_mutation(tmp_path, tenants):
    import sqlite3

    path = tmp_path / "mutation-rollback.sqlite3"
    store = SQLiteProjectStore(path)
    tenant = tenants[0]
    project = store.create(tenant, name="Original", description="preserve me")

    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TRIGGER reject_project_update
            BEFORE UPDATE ON projects
            BEGIN SELECT RAISE(ABORT, 'forced update failure'); END;
            CREATE TRIGGER reject_project_delete
            BEFORE DELETE ON projects
            BEGIN SELECT RAISE(ABORT, 'forced delete failure'); END;
            """
        )

    with pytest.raises(sqlite3.IntegrityError, match="forced update failure"):
        store.update_for_tenant(
            tenant, project.project_id, name="Changed", description="must roll back"
        )
    with pytest.raises(sqlite3.IntegrityError, match="forced delete failure"):
        store.delete_for_tenant(tenant, project.project_id)

    retained = SQLiteProjectStore(path).get_for_tenant(tenant, project.project_id)
    assert retained == project


def test_project_schema_initialization_rolls_back_on_ddl_failure(tmp_path, monkeypatch):
    import sqlite3

    path = tmp_path / "schema-init-rollback.sqlite3"
    original_connect = SQLiteProjectStore._connect

    def connect_with_denied_index(self):
        connection = original_connect(self)

        def authorizer(action, _arg1, _arg2, _database, _trigger):
            if action == sqlite3.SQLITE_CREATE_INDEX:
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK

        connection.set_authorizer(authorizer)
        return connection

    monkeypatch.setattr(SQLiteProjectStore, "_connect", connect_with_denied_index)

    with pytest.raises(sqlite3.DatabaseError):
        SQLiteProjectStore(path)

    # DDL and migration bookkeeping must be one transaction: a failed index
    # creation must not leave a partially initialized schema behind.
    with sqlite3.connect(path) as connection:
        tables = connection.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table', 'index') "
            "AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    assert tables == []


def _create_project_in_process(database_path, gate, ready_queue, result_queue, index):
    store = SQLiteProjectStore(database_path, timeout=20)
    tenant = TenantKey("https://issuer-process.example", "shared-owner")
    ready_queue.put(True)
    if not gate.wait(timeout=30):
        result_queue.put(("error", "start gate timed out"))
        return
    project = store.create(
        tenant,
        name=f"Process project {index}",
        description="created by an independent process",
    )
    result_queue.put(("ok", project.project_id))


def test_concurrent_process_project_creates_are_all_persisted(tmp_path):
    path = tmp_path / "multiprocess-projects.sqlite3"
    SQLiteProjectStore(path)
    context = multiprocessing.get_context("spawn")
    gate = context.Event()
    ready_queue = context.Queue()
    result_queue = context.Queue()
    processes = [
        context.Process(
            target=_create_project_in_process,
            args=(str(path), gate, ready_queue, result_queue, index),
        )
        for index in range(6)
    ]
    try:
        for process in processes:
            process.start()
        for _ in processes:
            ready_queue.get(timeout=45)
        gate.set()
        results = [result_queue.get(timeout=45) for _ in processes]
        for process in processes:
            process.join(timeout=45)
        assert all(not process.is_alive() for process in processes)
        assert all(process.exitcode == 0 for process in processes)
        assert all(status == "ok" for status, _ in results), results
    finally:
        gate.set()
        for process in processes:
            if process.is_alive():
                process.terminate()
            process.join(timeout=5)
        ready_queue.close()
        result_queue.close()

    project_ids = [value for _, value in results]
    assert len(set(project_ids)) == 6
    tenant = TenantKey("https://issuer-process.example", "shared-owner")
    projects = SQLiteProjectStore(path).list_for_tenant(tenant)
    assert len(projects) == 6
    assert {project.project_id for project in projects} == set(project_ids)

def _crash_with_uncommitted_project(database_path, ready_connection):
    import os
    import sqlite3

    connection = sqlite3.connect(database_path, isolation_level=None)
    connection.execute("BEGIN IMMEDIATE")
    connection.execute(
        """INSERT INTO projects
           (project_id, tenant_issuer, tenant_subject, name, description, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            "crash-uncommitted-project",
            "https://issuer-crash.example",
            "crash-owner",
            "Uncommitted project",
            "must disappear after recovery",
            "2026-11-15T00:00:00+00:00",
            "2026-11-15T00:00:00+00:00",
        ),
    )
    ready_connection.send(True)
    # Simulate abrupt process termination without commit, rollback, or close.
    os._exit(0)


def test_sqlite_recovers_uncommitted_project_after_process_crash(tmp_path, tenants):
    path = tmp_path / "project-crash-recovery.sqlite3"
    store = SQLiteProjectStore(path)
    committed = store.create(tenants[0], name="Committed project", description="keep")

    context = multiprocessing.get_context("spawn")
    receive_connection, send_connection = context.Pipe(duplex=False)
    process = context.Process(
        target=_crash_with_uncommitted_project,
        args=(str(path), send_connection),
    )
    process.start()
    try:
        assert receive_connection.poll(30)
        assert receive_connection.recv() is True
        process.join(timeout=30)
        assert not process.is_alive()
        assert process.exitcode == 0
    finally:
        if process.is_alive():
            process.terminate()
            process.join(timeout=5)
        receive_connection.close()
        send_connection.close()

    recovered = SQLiteProjectStore(path)
    assert recovered.get_for_tenant(tenants[0], committed.project_id) == committed
    with sqlite3.connect(path) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM projects WHERE project_id = ?",
            ("crash-uncommitted-project",),
        ).fetchone()[0] == 0



def test_project_store_rejects_in_memory_database_path():
    with pytest.raises(ValueError, match="filesystem-backed"):
        SQLiteProjectStore(":memory:")
