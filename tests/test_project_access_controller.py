import pytest

from core.identity import AuthorizationDenied, Principal
from core.project_access import ProjectAccessControl
from core.project_access_controller import OwnerProjectAccessController
from core.sqlite_project_store import SQLiteProjectStore
from core.storage import TenantKey


OWNER = Principal("owner", "https://owner.example", True)
READER = Principal("reader", "https://reader.example", True)
OTHER_ISSUER_OWNER = Principal("owner", "https://other-issuer.example", True)
UNAUTHENTICATED = Principal("reader", "https://reader.example", False)


def setup_controller(tmp_path):
    store = SQLiteProjectStore(tmp_path / "projects.sqlite3")
    project = store.create(
        TenantKey(OWNER.issuer, OWNER.subject),
        name="Owner private project",
        description="",
    )
    access = ProjectAccessControl(store)
    return project, access, OwnerProjectAccessController(access)


def test_controller_grants_only_explicit_read_access_and_records_owner_actor(tmp_path):
    project, access, controller = setup_controller(tmp_path)

    grant = controller.grant_read(project.project_id, actor=OWNER, grantee=READER)

    assert grant.project_id == project.project_id
    assert access.has_access(project.project_id, READER)
    events = controller.list_events(project.project_id, actor=OWNER)
    assert [event.action for event in events] == ["grant"]
    assert (events[0].actor_issuer, events[0].actor_subject) == (
        OWNER.issuer, OWNER.subject
    )
    assert (events[0].grantee_issuer, events[0].grantee_subject) == (
        READER.issuer, READER.subject
    )


def test_controller_revoke_is_immediate_and_idempotent(tmp_path):
    project, access, controller = setup_controller(tmp_path)
    controller.grant_read(project.project_id, actor=OWNER, grantee=READER)

    assert controller.revoke_read(project.project_id, actor=OWNER, grantee=READER)
    assert not access.has_access(project.project_id, READER)
    assert not controller.revoke_read(project.project_id, actor=OWNER, grantee=READER)
    assert [event.action for event in controller.list_events(
        project.project_id, actor=OWNER
    )] == ["grant", "revoke"]


@pytest.mark.parametrize("actor", [READER, OTHER_ISSUER_OWNER, UNAUTHENTICATED, None])
def test_controller_rejects_non_owner_or_untrusted_actor(tmp_path, actor):
    project, _, controller = setup_controller(tmp_path)

    with pytest.raises(PermissionError):
        controller.grant_read(project.project_id, actor=actor, grantee=READER)
    with pytest.raises(PermissionError):
        controller.revoke_read(project.project_id, actor=actor, grantee=READER)
    with pytest.raises(PermissionError):
        controller.list_grants(project.project_id, actor=actor)
    with pytest.raises(PermissionError):
        controller.list_events(project.project_id, actor=actor)


def test_controller_rejects_self_grant_and_self_revoke(tmp_path):
    project, access, controller = setup_controller(tmp_path)

    with pytest.raises(ValueError):
        controller.grant_read(project.project_id, actor=OWNER, grantee=OWNER)
    with pytest.raises(ValueError):
        controller.revoke_read(project.project_id, actor=OWNER, grantee=OWNER)
    assert access.has_access(project.project_id, OWNER)
    assert controller.list_events(project.project_id, actor=OWNER) == []


def test_controller_rejects_missing_project_and_malformed_grantee(tmp_path):
    _, _, controller = setup_controller(tmp_path)

    with pytest.raises(AuthorizationDenied):
        controller.grant_read("missing-project", actor=OWNER, grantee=READER)
    with pytest.raises(PermissionError):
        controller.grant_read(
            "missing-project", actor=OWNER, grantee=UNAUTHENTICATED
        )


def test_controller_has_no_generic_privilege_escalation_methods(tmp_path):
    _, _, controller = setup_controller(tmp_path)

    assert not hasattr(controller, "grant")
    assert not hasattr(controller, "grant_write")
    assert not hasattr(controller, "grant_execute")
    assert not hasattr(controller, "grant_file_access")
    assert not hasattr(controller, "grant_memory_access")
    assert not hasattr(controller, "grant_checkpoint_access")
