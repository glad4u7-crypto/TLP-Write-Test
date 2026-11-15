import pytest

from core.identity import AuthorizationDenied, Principal
from core.persistent_projects import PersistentProjectRegistry
from core.projects import _PROJECT_MUTATION_CAPABILITY
from core.sqlite_project_store import SQLiteProjectStore
from core.storage import TenantKey


ALICE = Principal("alice", "https://issuer-one.example", True)
OTHER_ISSUER = Principal("alice", "https://issuer-two.example", True)
BOB = Principal("bob", "https://issuer-one.example", True)


def make_registry(tmp_path):
    tenant = TenantKey(ALICE.issuer, ALICE.subject)
    store = SQLiteProjectStore(tmp_path / "projects.sqlite3")
    return PersistentProjectRegistry(store, tenant), store


def test_registry_crud_survives_reconstruction(tmp_path):
    registry, store = make_registry(tmp_path)
    project = registry.create(
        "Persistent", "saved", owner_subject=ALICE.subject, owner_issuer=ALICE.issuer,
        _capability=_PROJECT_MUTATION_CAPABILITY,
    )
    reopened = PersistentProjectRegistry(
        SQLiteProjectStore(tmp_path / "projects.sqlite3"),
        TenantKey(ALICE.issuer, ALICE.subject),
    )
    assert reopened.list_projects_for_owner(ALICE)[0].project_id == project.project_id
    updated = reopened.update_for_owner(
        project.project_id, ALICE, name="Updated", description="kept",
        _capability=_PROJECT_MUTATION_CAPABILITY,
    )
    assert updated.name == "Updated"
    assert reopened.delete_for_owner(
        project.project_id, ALICE, _capability=_PROJECT_MUTATION_CAPABILITY
    )
    assert reopened.list_projects_for_owner(ALICE) == []


@pytest.mark.parametrize("principal", [OTHER_ISSUER, BOB])
def test_registry_rejects_other_tenant_even_when_subject_or_issuer_matches(tmp_path, principal):
    registry, _ = make_registry(tmp_path)
    registry.create(
        "Alice only", "", owner_subject=ALICE.subject, owner_issuer=ALICE.issuer,
        _capability=_PROJECT_MUTATION_CAPABILITY,
    )
    with pytest.raises(AuthorizationDenied):
        registry.list_projects_for_owner(principal)


def test_gateway_cannot_create_project_for_spoofed_owner(tmp_path):
    registry, _ = make_registry(tmp_path)
    with pytest.raises(AuthorizationDenied):
        registry.create(
            "Spoof", "", owner_subject="bob", owner_issuer=ALICE.issuer,
            _capability=_PROJECT_MUTATION_CAPABILITY,
        )


def test_approval_gateway_creates_project_persistently_for_authenticated_tenant(tmp_path):
    from core.approvals import ApprovalAuthority
    from core.project_actions import build_project_gateway
    from core.sqlite_security_store import SQLiteSecurityStore

    tenant = TenantKey(ALICE.issuer, ALICE.subject)
    project_store = SQLiteProjectStore(tmp_path / "projects.sqlite3")
    security_store = SQLiteSecurityStore(tmp_path / "security.sqlite3")
    authority = ApprovalAuthority(
        nonce_store=security_store,
        signing_secret=b"local-test-secret-material-at-least-32-bytes",
    )
    registry = PersistentProjectRegistry(project_store, tenant)
    gateway = build_project_gateway(
        registry, authority, principal=ALICE
    )
    payload = {"name": "Approved persistent project", "description": "created after approval"}
    receipt = authority.issue("create_project", payload, tenant=tenant)
    result = gateway.execute(
        "create_project", payload, approval_receipt=receipt, tenant=tenant
    )
    assert result.executed is True
    reopened = PersistentProjectRegistry(
        SQLiteProjectStore(tmp_path / "projects.sqlite3"), tenant
    )
    assert [p.project_id for p in reopened.list_projects_for_owner(ALICE)] == [
        result.output.project_id
    ]
