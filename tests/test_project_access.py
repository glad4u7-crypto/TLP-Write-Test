import pytest

from core.identity import Principal, AuthorizationDenied
from core.project_access import ProjectAccessControl
from core.sqlite_project_store import SQLiteProjectStore
from core.storage import TenantKey


OWNER = Principal("owner-sub", "https://owner.example", True)
READER = Principal("reader-sub", "https://reader.example", True)
SAME_SUBJECT_OTHER_ISSUER = Principal("owner-sub", "https://other.example", True)
SAME_ISSUER_OTHER_SUBJECT = Principal("other-sub", "https://owner.example", True)
UNAUTHENTICATED = Principal("reader-sub", "https://reader.example", False)


def setup_access(tmp_path):
    store = SQLiteProjectStore(tmp_path / "projects.sqlite3")
    project = store.create(
        TenantKey(OWNER.issuer, OWNER.subject), name="Private project", description=""
    )
    return store, project, ProjectAccessControl(store)


def test_access_is_owner_only_until_explicit_grant(tmp_path):
    _, project, access = setup_access(tmp_path)
    assert access.is_owner(project.project_id, OWNER)
    assert not access.is_owner(project.project_id, READER)
    assert access.has_access(project.project_id, OWNER)
    assert not access.has_access(project.project_id, READER)


def test_owner_can_grant_and_revoke_exact_issuer_subject_identity(tmp_path):
    _, project, access = setup_access(tmp_path)
    grant = access.grant_read(project.project_id, OWNER, READER)
    assert grant.grantee_issuer == READER.issuer
    assert grant.grantee_subject == READER.subject
    assert access.has_access(project.project_id, READER)
    assert access.revoke_read(project.project_id, OWNER, READER)
    assert not access.has_access(project.project_id, READER)
    records = access.list_for_owner(project.project_id, OWNER)
    assert len(records) == 1 and records[0].revoked_at is not None


@pytest.mark.parametrize("forged", [SAME_SUBJECT_OTHER_ISSUER, SAME_ISSUER_OTHER_SUBJECT])
def test_issuer_and_subject_must_both_match_grant(tmp_path, forged):
    _, project, access = setup_access(tmp_path)
    access.grant_read(project.project_id, OWNER, READER)
    assert not access.has_access(project.project_id, forged)


def test_non_owner_cannot_grant_revoke_or_list(tmp_path):
    _, project, access = setup_access(tmp_path)
    with pytest.raises(PermissionError):
        access.grant_read(project.project_id, READER, SAME_ISSUER_OTHER_SUBJECT)
    access.grant_read(project.project_id, OWNER, READER)
    with pytest.raises(PermissionError):
        access.revoke_read(project.project_id, READER, OWNER)
    with pytest.raises(PermissionError):
        access.list_for_owner(project.project_id, READER)


def test_owner_cannot_grant_or_revoke_self(tmp_path):
    _, project, access = setup_access(tmp_path)
    with pytest.raises(ValueError):
        access.grant_read(project.project_id, OWNER, OWNER)
    with pytest.raises(ValueError):
        access.revoke_read(project.project_id, OWNER, OWNER)
    assert access.has_access(project.project_id, OWNER)


def test_invalid_identity_and_missing_project_fail_closed(tmp_path):
    _, project, access = setup_access(tmp_path)
    assert not access.has_access(project.project_id, UNAUTHENTICATED)
    assert not access.has_access("missing-project", OWNER)
    with pytest.raises(PermissionError):
        access.grant_read("missing-project", OWNER, READER)


def test_regrant_reactivates_single_grant_record(tmp_path):
    _, project, access = setup_access(tmp_path)
    access.grant_read(project.project_id, OWNER, READER)
    access.revoke_read(project.project_id, OWNER, READER)
    access.grant_read(project.project_id, OWNER, READER)
    assert access.has_access(project.project_id, READER)
    assert len(access.list_for_owner(project.project_id, OWNER)) == 1


def test_grants_survive_store_reconstruction_and_revocation_is_immediate(tmp_path):
    path = tmp_path / "projects.sqlite3"
    store = SQLiteProjectStore(path)
    project = store.create(
        TenantKey(OWNER.issuer, OWNER.subject), name="Durable", description=""
    )
    access = ProjectAccessControl(store)
    access.grant_read(project.project_id, OWNER, READER)
    reopened = ProjectAccessControl(SQLiteProjectStore(path))
    assert reopened.has_access(project.project_id, READER)
    assert reopened.revoke_read(project.project_id, OWNER, READER)
    assert not ProjectAccessControl(SQLiteProjectStore(path)).has_access(
        project.project_id, READER
    )

 
def test_grant_and_revoke_write_owner_only_immutable_audit_events(tmp_path):
    _, project, access = setup_access(tmp_path)
    access.grant_read(project.project_id, OWNER, READER)
    access.revoke_read(project.project_id, OWNER, READER)
    events = access.list_events_for_owner(project.project_id, OWNER)
    assert [event.action for event in events] == ["grant", "revoke"]
    assert all(event.grantee_issuer == READER.issuer for event in events)
    assert all(event.grantee_subject == READER.subject for event in events)
    assert all(event.actor_issuer == OWNER.issuer for event in events)
    assert all(event.actor_subject == OWNER.subject for event in events)
    assert events[0].event_id != events[1].event_id
    assert not access.revoke_read(project.project_id, OWNER, READER)
    assert len(access.list_events_for_owner(project.project_id, OWNER)) == 2


def test_non_owner_cannot_read_access_audit_events(tmp_path):
    _, project, access = setup_access(tmp_path)
    access.grant_read(project.project_id, OWNER, READER)
    with pytest.raises(PermissionError):
        access.list_events_for_owner(project.project_id, READER)


def test_access_audit_events_survive_store_reconstruction(tmp_path):
    path = tmp_path / "projects.sqlite3"
    store = SQLiteProjectStore(path)
    project = store.create(
        TenantKey(OWNER.issuer, OWNER.subject), name="Audit", description=""
    )
    ProjectAccessControl(store).grant_read(project.project_id, OWNER, READER)
    reopened = ProjectAccessControl(SQLiteProjectStore(path))
    assert [event.action for event in reopened.list_events_for_owner(project.project_id, OWNER)] == ["grant"]

 
def test_access_audit_events_cannot_be_updated_or_deleted(tmp_path):
    import sqlite3
    _, project, access = setup_access(tmp_path)
    access.grant_read(project.project_id, OWNER, READER)
    with access._store._connect() as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE project_access_events SET action='revoke' WHERE project_id=?",
                (project.project_id,),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "DELETE FROM project_access_events WHERE project_id=?",
                (project.project_id,),
            )
    assert [event.action for event in access.list_events_for_owner(project.project_id, OWNER)] == ["grant"]
