import sqlite3
import pytest

from core.identity import (
    AuthenticationRequired,
    AuthorizationDenied,
    Principal,
)
from core.persistent_projects import PersistentProjectRegistry
from core.projects import _PROJECT_MUTATION_CAPABILITY
from core.sqlite_project_store import SQLiteProjectStore
from core.storage import TenantKey


ALICE = Principal("alice", "https://issuer-one.example", True)
OTHER_ISSUER = Principal("alice", "https://issuer-two.example", True)
BOB = Principal("bob", "https://issuer-one.example", True)
UNAUTHENTICATED_ALICE = Principal("alice", "https://issuer-one.example", False)


def make_registry(tmp_path):
    tenant = TenantKey(ALICE.issuer, ALICE.subject)
    store = SQLiteProjectStore(tmp_path / "projects.sqlite3")
    return PersistentProjectRegistry(store, tenant), store


def create_alice_project(registry):
    return registry.create(
        "Alice only", "", owner_subject=ALICE.subject, owner_issuer=ALICE.issuer,
        _capability=_PROJECT_MUTATION_CAPABILITY,
    )


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
    create_alice_project(registry)
    with pytest.raises(AuthorizationDenied):
        registry.list_projects_for_owner(principal)


@pytest.mark.parametrize("principal", [OTHER_ISSUER, BOB])
def test_registry_rejects_cross_tenant_read_update_and_delete(tmp_path, principal):
    registry, _ = make_registry(tmp_path)
    project = create_alice_project(registry)

    with pytest.raises(AuthorizationDenied):
        registry.get_for_owner(project.project_id, principal)
    with pytest.raises(AuthorizationDenied):
        registry.update_for_owner(
            project.project_id, principal, name="Stolen", description="",
            _capability=_PROJECT_MUTATION_CAPABILITY,
        )
    with pytest.raises(AuthorizationDenied):
        registry.delete_for_owner(
            project.project_id, principal, _capability=_PROJECT_MUTATION_CAPABILITY
        )

    # Failed cross-tenant operations must not alter or remove the owner's record.
    retained = registry.get_for_owner(project.project_id, ALICE)
    assert retained is not None
    assert retained.name == "Alice only"


@pytest.mark.parametrize(
    "principal",
    [UNAUTHENTICATED_ALICE, None, object()],
)
def test_registry_rejects_missing_or_unauthenticated_principal_for_owner_operations(
    tmp_path, principal
):
    registry, _ = make_registry(tmp_path)
    project = create_alice_project(registry)

    with pytest.raises(AuthenticationRequired):
        registry.list_projects_for_owner(principal)
    with pytest.raises(AuthenticationRequired):
        registry.get_for_owner(project.project_id, principal)
    with pytest.raises(AuthenticationRequired):
        registry.update_for_owner(
            project.project_id, principal, name="Unauthorized", description="",
            _capability=_PROJECT_MUTATION_CAPABILITY,
        )
    with pytest.raises(AuthenticationRequired):
        registry.delete_for_owner(
            project.project_id, principal, _capability=_PROJECT_MUTATION_CAPABILITY
        )

    assert registry.get_for_owner(project.project_id, ALICE).name == "Alice only"


@pytest.mark.parametrize(
    ("owner_subject", "owner_issuer"),
    [
        ("bob", ALICE.issuer),
        (ALICE.subject, OTHER_ISSUER.issuer),
    ],
)
def test_gateway_cannot_create_project_for_spoofed_owner(
    tmp_path, owner_subject, owner_issuer
):
    registry, _ = make_registry(tmp_path)
    with pytest.raises(AuthorizationDenied):
        registry.create(
            "Spoof", "", owner_subject=owner_subject, owner_issuer=owner_issuer,
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


def test_persistent_gateway_uses_sqlite_audit_for_intent_and_completion(tmp_path):
    from core.approvals import ApprovalAuthority
    from core.project_actions import build_project_gateway
    from core.sqlite_security_store import SQLiteExecutionAuditLog, SQLiteSecurityStore

    tenant = TenantKey(ALICE.issuer, ALICE.subject)
    project_store = SQLiteProjectStore(tmp_path / "projects.sqlite3")
    security_store = SQLiteSecurityStore(tmp_path / "security.sqlite3")
    authority = ApprovalAuthority(
        nonce_store=security_store,
        signing_secret=b"sqlite-gateway-integration-secret-32-bytes",
    )
    audit_log = SQLiteExecutionAuditLog(security_store, tenant)
    registry = PersistentProjectRegistry(project_store, tenant)
    gateway = build_project_gateway(
        registry, authority, audit_log=audit_log, principal=ALICE,
        session_scope="sqlite-audit-session",
    )
    payload = {"name": "Durably audited", "description": "intent and completion"}
    receipt = authority.issue(
        "create_project", payload, tenant=tenant,
        session_scope="sqlite-audit-session",
    )

    result = gateway.execute(
        "create_project", payload, approval_receipt=receipt, tenant=tenant
    )

    assert result.executed is True
    assert audit_log.verify() != audit_log.GENESIS
    assert len(registry.list_projects_for_owner(ALICE)) == 1
    with sqlite3.connect(tmp_path / "security.sqlite3") as connection:
        rows = connection.execute(
            "SELECT action, result, reason_code FROM durable_audit_events ORDER BY sequence"
        ).fetchall()
    assert rows == [
        ("create_project", "denied", "authorized_dispatch_pending"),
        ("create_project", "success", "action_executed"),
    ]


def test_persistent_gateway_blocks_project_creation_when_sqlite_intent_audit_fails(
    tmp_path, monkeypatch
):
    from core.approvals import ApprovalAuthority
    from core.project_actions import build_project_gateway
    from core.sqlite_security_store import SQLiteExecutionAuditLog, SQLiteSecurityStore

    tenant = TenantKey(ALICE.issuer, ALICE.subject)
    project_store = SQLiteProjectStore(tmp_path / "projects.sqlite3")
    security_store = SQLiteSecurityStore(tmp_path / "security.sqlite3")
    authority = ApprovalAuthority(
        nonce_store=security_store,
        signing_secret=b"sqlite-audit-failure-secret-32-bytes",
    )
    audit_log = SQLiteExecutionAuditLog(security_store, tenant)
    registry = PersistentProjectRegistry(project_store, tenant)
    gateway = build_project_gateway(
        registry, authority, audit_log=audit_log, principal=ALICE,
        session_scope="sqlite-audit-failure-session",
    )

    def fail_audit(_event):
        raise OSError("simulated durable audit storage failure")

    monkeypatch.setattr(audit_log, "append", fail_audit)
    payload = {"name": "Must not be created", "description": ""}
    receipt = authority.issue(
        "create_project", payload, tenant=tenant,
        session_scope="sqlite-audit-failure-session",
    )

    result = gateway.execute(
        "create_project", payload, approval_receipt=receipt, tenant=tenant
    )

    assert result.executed is False
    assert "not executed" in result.reason
    assert registry.list_projects_for_owner(ALICE) == []


def test_persistent_gateway_blocks_protected_action_when_existing_audit_chain_is_tampered(
    tmp_path,
):
    import sqlite3

    from core.approvals import ApprovalAuthority
    from core.project_actions import build_project_gateway
    from core.sqlite_security_store import (
        DurableAuditEvent,
        SQLiteExecutionAuditLog,
        SQLiteSecurityStore,
    )

    tenant = TenantKey(ALICE.issuer, ALICE.subject)
    project_store = SQLiteProjectStore(tmp_path / "projects.sqlite3")
    security_path = tmp_path / "security.sqlite3"
    security_store = SQLiteSecurityStore(security_path)
    authority = ApprovalAuthority(
        nonce_store=security_store,
        signing_secret=b"tampered-audit-gateway-secret-32-bytes",
    )
    audit_log = SQLiteExecutionAuditLog(security_store, tenant)
    registry = PersistentProjectRegistry(project_store, tenant)

    # Seed a valid prior event, then simulate unauthorized database tampering.
    security_store.append_audit_event(
        DurableAuditEvent(
            "previous.action", "denied", "test_seed", "prior-fingerprint", "prior-request"
        )
    )
    with sqlite3.connect(security_path) as connection:
        connection.execute(
            "UPDATE durable_audit_events SET action = 'forged.action' WHERE sequence = 1"
        )

    gateway = build_project_gateway(
        registry, authority, audit_log=audit_log, principal=ALICE,
        session_scope="tampered-audit-session",
    )
    payload = {"name": "Must not be created", "description": ""}
    receipt = authority.issue(
        "create_project", payload, tenant=tenant,
        session_scope="tampered-audit-session",
    )

    result = gateway.execute(
        "create_project", payload, approval_receipt=receipt, tenant=tenant
    )

    assert result.executed is False
    assert "Audit persistence unavailable" in result.reason
    assert registry.list_projects_for_owner(ALICE) == []
    with pytest.raises(ValueError, match="audit"):
        audit_log.verify()
