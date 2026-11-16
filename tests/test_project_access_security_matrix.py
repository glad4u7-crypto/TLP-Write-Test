"""Security regression matrix for project ACL and private user resources."""
import pytest

from core.identity import Principal
from core.persistent_projects import PersistentProjectRegistry
from core.project_access import ProjectAccessControl
from core.sqlite_project_store import SQLiteProjectStore
from core.storage import TenantKey


OWNER = Principal("owner", "https://owner.example", True)
READER = Principal("reader", "https://reader.example", True)
OTHER = Principal("reader", "https://other.example", True)


def test_project_read_rechecks_acl_after_revoke_and_owner_mutations_stay_owner_only(tmp_path):
    path = tmp_path / "projects.sqlite3"
    store = SQLiteProjectStore(path)
    project = store.create(
        TenantKey(OWNER.issuer, OWNER.subject), name="Private", description=""
    )
    access = ProjectAccessControl(store)
    registry = PersistentProjectRegistry(
        store, TenantKey(OWNER.issuer, OWNER.subject), access_control=access
    )

    assert registry.get_for_principal(project.project_id, READER) is None
    access.grant_read(project.project_id, OWNER, READER)
    assert registry.get_for_principal(project.project_id, READER) is not None
    assert [item.project_id for item in registry.list_projects_for_principal(READER)] == [
        project.project_id
    ]

    # A new request/reconstructed registry must observe revocation immediately.
    assert access.revoke_read(project.project_id, OWNER, READER)
    reopened_access = ProjectAccessControl(SQLiteProjectStore(path))
    reopened_registry = PersistentProjectRegistry(
        SQLiteProjectStore(path), TenantKey(OWNER.issuer, OWNER.subject),
        access_control=reopened_access,
    )
    assert reopened_registry.get_for_principal(project.project_id, READER) is None
    assert reopened_registry.list_projects_for_principal(READER) == []
    assert reopened_registry.get_for_owner(project.project_id, OWNER) is not None


def test_grant_is_bound_to_both_oidc_issuer_and_subject_across_sessions(tmp_path):
    store = SQLiteProjectStore(tmp_path / "projects.sqlite3")
    project = store.create(
        TenantKey(OWNER.issuer, OWNER.subject), name="Issuer-bound", description=""
    )
    access = ProjectAccessControl(store)
    access.grant_read(project.project_id, OWNER, READER)

    assert access.has_access(project.project_id, READER)
    assert not access.has_access(project.project_id, OTHER)


def test_project_registry_without_acl_never_exposes_collaborator_reads(tmp_path):
    store = SQLiteProjectStore(tmp_path / "projects.sqlite3")
    project = store.create(
        TenantKey(OWNER.issuer, OWNER.subject), name="Owner only", description=""
    )
    registry = PersistentProjectRegistry(
        store, TenantKey(OWNER.issuer, OWNER.subject)
    )

    with pytest.raises(PermissionError):
        registry.get_for_principal(project.project_id, READER)
    with pytest.raises(PermissionError):
        registry.list_projects_for_principal(READER)


def test_memory_and_checkpoint_records_remain_tenant_private(tmp_path):
    from core.memory import SQLiteMemoryStore

    memory = SQLiteMemoryStore(tmp_path / "memory.sqlite3")
    owner = TenantKey(OWNER.issuer, OWNER.subject)
    reader = TenantKey(READER.issuer, READER.subject)

    record = memory.add_memory(
        owner, category="project", content="owner private context", consent=True
    )
    checkpoint = memory.save_checkpoint(
        owner, project_id="owner-project", label="private checkpoint",
        summary="owner-only summary", next_action="continue", consent=True,
    )

    assert memory.list_memories(owner) == [record]
    assert memory.list_memories(reader) == []
    assert memory.latest_checkpoint(owner, "owner-project") == checkpoint
    assert memory.latest_checkpoint(reader, "owner-project") is None


def test_memory_and_checkpoint_writes_still_require_explicit_consent(tmp_path):
    from core.memory import SQLiteMemoryStore

    memory = SQLiteMemoryStore(tmp_path / "memory.sqlite3")
    tenant = TenantKey(OWNER.issuer, OWNER.subject)
    with pytest.raises(PermissionError):
        memory.add_memory(tenant, category="fact", content="private", consent=False)
    with pytest.raises(PermissionError):
        memory.save_checkpoint(
            tenant, project_id="p1", label="cp", summary="summary",
            next_action="next", consent=False,
        )
