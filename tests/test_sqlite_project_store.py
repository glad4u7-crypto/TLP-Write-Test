from concurrent.futures import ThreadPoolExecutor

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
