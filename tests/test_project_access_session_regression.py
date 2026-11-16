"""Two-principal and session-transition regression tests for P36."""
from core.identity import Principal
from core.project_access import ProjectAccessControl
from core.session_security import bind_session_identity, clear_session_identity, session_identity_key
from core.sqlite_project_store import SQLiteProjectStore
from core.storage import TenantKey


OWNER = Principal("owner", "https://owner.example", True)
ALICE = Principal("alice", "https://users.example", True)
BOB = Principal("bob", "https://users.example", True)


def test_two_user_sessions_do_not_share_identity_bound_state(tmp_path):
    owner_state = {}
    reader_state = {}
    bind_session_identity(owner_state, session_identity_key(OWNER.issuer, OWNER.subject))
    bind_session_identity(reader_state, session_identity_key(ALICE.issuer, ALICE.subject))
    owner_state["pending_project"] = {"name": "owner draft"}
    reader_state["pending_project"] = {"name": "reader draft"}

    assert owner_state["active_identity_subject"] != reader_state["active_identity_subject"]
    assert owner_state["pending_project"]["name"] == "owner draft"
    assert reader_state["pending_project"]["name"] == "reader draft"

    bind_session_identity(reader_state, session_identity_key(BOB.issuer, BOB.subject))
    assert "pending_project" not in reader_state
    assert owner_state["pending_project"]["name"] == "owner draft"


def test_revocation_is_observed_by_existing_and_reconstructed_acl_readers(tmp_path):
    path = tmp_path / "projects.sqlite3"
    store = SQLiteProjectStore(path)
    project = store.create(
        TenantKey(OWNER.issuer, OWNER.subject), name="Shared read", description=""
    )
    owner_acl = ProjectAccessControl(store)
    owner_acl.grant_read(project.project_id, OWNER, ALICE)
    reader_acl = ProjectAccessControl(SQLiteProjectStore(path))

    assert reader_acl.has_access(project.project_id, ALICE)
    assert owner_acl.revoke_read(project.project_id, OWNER, ALICE)

    assert not reader_acl.has_access(project.project_id, ALICE)
    assert not ProjectAccessControl(SQLiteProjectStore(path)).has_access(
        project.project_id, ALICE
    )


def test_revoke_regrant_revoke_history_is_append_only_and_ordered(tmp_path):
    store = SQLiteProjectStore(tmp_path / "projects.sqlite3")
    project = store.create(
        TenantKey(OWNER.issuer, OWNER.subject), name="Audit sequence", description=""
    )
    acl = ProjectAccessControl(store)

    acl.grant_read(project.project_id, OWNER, ALICE)
    assert acl.revoke_read(project.project_id, OWNER, ALICE)
    acl.grant_read(project.project_id, OWNER, ALICE)
    assert acl.revoke_read(project.project_id, OWNER, ALICE)

    events = acl.list_events_for_owner(project.project_id, OWNER)
    assert [event.action for event in events] == ["grant", "revoke", "grant", "revoke"]
    assert len({event.event_id for event in events}) == 4
    assert all(event.actor_subject == OWNER.subject for event in events)
    assert not acl.has_access(project.project_id, ALICE)


def test_logout_then_identity_switch_cannot_reuse_old_session_capability():
    from core.approvals import ApprovalAuthority
    from core.execution import ExecutionGateway

    state = {"active_identity_subject": session_identity_key(OWNER.issuer, OWNER.subject)}
    old_authority = ApprovalAuthority()
    old_scope = "owner-session-scope"
    payload = {"name": "Private project", "description": ""}
    receipt = old_authority.issue("create_project", payload, session_scope=old_scope)

    state.update({
        "approval_authority": old_authority,
        "approval_session_scope": old_scope,
        "execution_gateway": ExecutionGateway(
            {"create_project": lambda data: "executed"},
            approval_authority=old_authority,
            session_scope=old_scope,
        ),
    })
    clear_session_identity(state)
    bind_session_identity(state, session_identity_key(ALICE.issuer, ALICE.subject))

    new_authority = ApprovalAuthority()
    new_gateway = ExecutionGateway(
        {"create_project": lambda data: "executed"},
        approval_authority=new_authority,
        session_scope="reader-session-scope",
    )
    result = new_gateway.execute("create_project", payload, approval_receipt=receipt)
    assert result.executed is False
