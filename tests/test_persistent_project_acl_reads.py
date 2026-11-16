from core.identity import Principal, AuthorizationDenied
from core.persistent_projects import PersistentProjectRegistry
from core.project_access import ProjectAccessControl
from core.projects import _PROJECT_MUTATION_CAPABILITY
from core.sqlite_project_store import SQLiteProjectStore
from core.storage import TenantKey


OWNER = Principal("owner", "https://owner.example", True)
READER = Principal("reader", "https://reader.example", True)
STRANGER = Principal("stranger", "https://stranger.example", True)


def test_registry_lists_and_reads_only_explicitly_granted_projects(tmp_path):
    store = SQLiteProjectStore(tmp_path / "projects.sqlite3")
    acl = ProjectAccessControl(store)
    owner_registry = PersistentProjectRegistry(
        store, TenantKey(OWNER.issuer, OWNER.subject), access_control=acl
    )
    reader_registry = PersistentProjectRegistry(
        store, TenantKey(READER.issuer, READER.subject), access_control=acl
    )
    project = owner_registry.create(
        "Private", "owner data", owner_subject=OWNER.subject, owner_issuer=OWNER.issuer,
        _capability=_PROJECT_MUTATION_CAPABILITY,
    )

    assert reader_registry.get_for_principal(project.project_id, READER) is None
    assert reader_registry.list_projects_for_principal(READER) == []

    acl.grant_read(project.project_id, OWNER, READER)
    visible = reader_registry.get_for_principal(project.project_id, READER)
    assert visible is not None
    assert visible.name == "Private"
    assert visible.owner_issuer == OWNER.issuer
    assert [p.project_id for p in reader_registry.list_projects_for_principal(READER)] == [
        project.project_id
    ]
    assert reader_registry.get_for_principal(project.project_id, STRANGER) is None


def test_registry_rechecks_acl_after_revocation_and_does_not_cache_reads(tmp_path):
    store = SQLiteProjectStore(tmp_path / "projects.sqlite3")
    acl = ProjectAccessControl(store)
    owner_registry = PersistentProjectRegistry(
        store, TenantKey(OWNER.issuer, OWNER.subject), access_control=acl
    )
    reader_registry = PersistentProjectRegistry(
        store, TenantKey(READER.issuer, READER.subject), access_control=acl
    )
    project = owner_registry.create(
        "Revocable", "", owner_subject=OWNER.subject, owner_issuer=OWNER.issuer,
        _capability=_PROJECT_MUTATION_CAPABILITY,
    )
    acl.grant_read(project.project_id, OWNER, READER)
    assert reader_registry.get_for_principal(project.project_id, READER) is not None
    assert acl.revoke_read(project.project_id, OWNER, READER)
    assert reader_registry.get_for_principal(project.project_id, READER) is None
    assert reader_registry.list_projects_for_principal(READER) == []


def test_collaborator_cannot_update_or_delete_owned_project(tmp_path):
    store = SQLiteProjectStore(tmp_path / "projects.sqlite3")
    acl = ProjectAccessControl(store)
    owner_registry = PersistentProjectRegistry(
        store, TenantKey(OWNER.issuer, OWNER.subject), access_control=acl
    )
    reader_registry = PersistentProjectRegistry(
        store, TenantKey(READER.issuer, READER.subject), access_control=acl
    )
    project = owner_registry.create(
        "Read only", "", owner_subject=OWNER.subject, owner_issuer=OWNER.issuer,
        _capability=_PROJECT_MUTATION_CAPABILITY,
    )
    acl.grant_read(project.project_id, OWNER, READER)

    import pytest
    with pytest.raises(AuthorizationDenied):
        reader_registry.update_for_owner(
            project.project_id, READER, name="Changed", description="",
            _capability=_PROJECT_MUTATION_CAPABILITY,
        )
    with pytest.raises(AuthorizationDenied):
        reader_registry.delete_for_owner(
            project.project_id, READER, _capability=_PROJECT_MUTATION_CAPABILITY
        )
    assert owner_registry.get_for_owner(project.project_id, OWNER).name == "Read only"


def test_registry_fails_closed_when_acl_not_configured(tmp_path):
    store = SQLiteProjectStore(tmp_path / "projects.sqlite3")
    registry = PersistentProjectRegistry(
        store, TenantKey(READER.issuer, READER.subject)
    )
    import pytest
    with pytest.raises(PermissionError):
        registry.get_for_principal("any-id", READER)
    with pytest.raises(PermissionError):
        registry.list_projects_for_principal(READER)
