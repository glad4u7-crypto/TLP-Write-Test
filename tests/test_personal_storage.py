from __future__ import annotations

import os
from pathlib import Path

import pytest

from core.personal_runtime import PERSONAL_OWNER_TENANT
from core.personal_storage import SQLitePersonalProjectStore
from core.storage import TenantKey


def test_personal_project_store_persists_across_instances(tmp_path):
    database = tmp_path / "private" / "projects.sqlite3"
    first = SQLitePersonalProjectStore(database)
    created = first.create(PERSONAL_OWNER_TENANT, name="APAA", description="Personal workspace")

    restarted = SQLitePersonalProjectStore(database)
    loaded = restarted.get_for_tenant(PERSONAL_OWNER_TENANT, created.project_id)
    assert loaded == created
    assert [item.project_id for item in restarted.list_for_tenant(PERSONAL_OWNER_TENANT)] == [
        created.project_id
    ]


def test_personal_project_store_enforces_composite_owner_scope(tmp_path):
    store = SQLitePersonalProjectStore(tmp_path / "private" / "projects.sqlite3")
    owner = PERSONAL_OWNER_TENANT
    other = TenantKey("local://different", "different-owner")
    project = store.create(owner, name="Private")

    assert store.get_for_tenant(other, project.project_id) is None
    assert store.list_for_tenant(other) == []
    assert store.update_for_tenant(
        other, project.project_id, name="Taken over", description=""
    ) is None
    assert store.delete_for_tenant(other, project.project_id) is False
    assert store.get_for_tenant(owner, project.project_id) == project


def test_personal_project_store_updates_and_deletes_only_owned_rows(tmp_path):
    store = SQLitePersonalProjectStore(tmp_path / "private" / "projects.sqlite3")
    project = store.create(PERSONAL_OWNER_TENANT, name="Before")
    updated = store.update_for_tenant(
        PERSONAL_OWNER_TENANT, project.project_id, name="After", description="Changed"
    )
    assert updated is not None
    assert updated.name == "After"
    assert updated.description == "Changed"
    assert updated.updated_at >= project.updated_at
    assert store.delete_for_tenant(PERSONAL_OWNER_TENANT, project.project_id)
    assert store.get_for_tenant(PERSONAL_OWNER_TENANT, project.project_id) is None


def test_personal_project_store_validates_project_fields(tmp_path):
    store = SQLitePersonalProjectStore(tmp_path / "private" / "projects.sqlite3")
    with pytest.raises(ValueError):
        store.create(PERSONAL_OWNER_TENANT, name=" ", description="")
    with pytest.raises(ValueError):
        store.create(PERSONAL_OWNER_TENANT, name="x" * 81, description="")
    with pytest.raises(ValueError):
        store.create(PERSONAL_OWNER_TENANT, name="Valid", description="x" * 501)


@pytest.mark.skipif(os.name != "posix", reason="POSIX permission bits are platform-specific")
def test_personal_database_is_owner_only(tmp_path):
    path = tmp_path / "private" / "projects.sqlite3"
    SQLitePersonalProjectStore(path)
    assert (path.parent.stat().st_mode & 0o777) == 0o700
    assert (path.stat().st_mode & 0o777) == 0o600


def test_personal_database_symlink_is_rejected(tmp_path):
    target = tmp_path / "target.sqlite3"
    target.write_bytes(b"")
    link = tmp_path / "private" / "projects.sqlite3"
    link.parent.mkdir(mode=0o700)
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("file symlink creation is unavailable")
    with pytest.raises(ValueError, match="symlink"):
        SQLitePersonalProjectStore(link)
