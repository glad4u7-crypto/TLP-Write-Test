import pytest

from core.approvals import ApprovalAuthority
from core.audit import JsonlAuditLog
from core.project_actions import build_project_gateway
from core.projects import ProjectRegistry


def test_gateway_builder_does_not_self_approve_or_execute():
    registry = ProjectRegistry()
    authority = ApprovalAuthority()
    gateway = build_project_gateway(registry, authority)

    assert registry.list_projects() == []
    # No receipt is supplied: the gateway must not create the project.
    result = gateway.execute(
        "create_project",
        {"name": "APAA workspace", "description": "Reviewed"},
    )
    assert result.executed is False
    assert registry.list_projects() == []


def test_explicit_ui_confirmation_receipt_allows_exact_project_creation(tmp_path):
    registry = ProjectRegistry()
    authority = ApprovalAuthority()
    audit = JsonlAuditLog(tmp_path / "audit.jsonl")
    gateway = build_project_gateway(
        registry, authority, audit_log=audit, session_scope="session-A"
    )
    payload = {"name": "APAA workspace", "description": "Reviewed project details"}

    # This receipt issuance represents the trusted UI Confirm event.
    receipt = authority.issue("create_project", payload, session_scope="session-A")
    result = gateway.execute("create_project", payload, approval_receipt=receipt)

    assert result.executed is True
    assert result.output.name == payload["name"]
    assert result.output.description == payload["description"]
    assert len(registry.list_projects()) == 1
    assert len((tmp_path / "audit.jsonl").read_text().splitlines()) == 2
    assert audit.verify() != audit.GENESIS


def test_receipt_cannot_be_reused_for_project_creation():
    registry = ProjectRegistry()
    authority = ApprovalAuthority()
    gateway = build_project_gateway(registry, authority)
    payload = {"name": "One project", "description": ""}

    receipt = authority.issue("create_project", payload)
    first = gateway.execute("create_project", payload, approval_receipt=receipt)
    replay = gateway.execute("create_project", payload, approval_receipt=receipt)

    assert first.executed is True
    assert replay.executed is False
    assert len(registry.list_projects()) == 1


@pytest.mark.parametrize(
    "payload",
    [
        {"name": "", "description": ""},
        {"name": "x" * 81, "description": ""},
        {"name": "valid", "description": "x" * 501},
    ],
)
def test_invalid_project_payload_is_rejected(payload):
    registry = ProjectRegistry()
    authority = ApprovalAuthority()
    gateway = build_project_gateway(registry, authority)
    receipt = authority.issue("create_project", payload)

    result = gateway.execute("create_project", payload, approval_receipt=receipt)

    assert result.executed is False
    assert registry.list_projects() == []


def test_project_gateway_rejects_receipt_from_another_session():
    authority = ApprovalAuthority()
    first_registry = ProjectRegistry()
    second_registry = ProjectRegistry()
    first_gateway = build_project_gateway(
        first_registry, authority, session_scope="streamlit-session-one"
    )
    second_gateway = build_project_gateway(
        second_registry, authority, session_scope="streamlit-session-two"
    )
    payload = {"name": "Session private", "description": ""}
    receipt = authority.issue(
        "create_project", payload, session_scope="streamlit-session-one"
    )

    rejected = second_gateway.execute(
        "create_project", payload, approval_receipt=receipt
    )
    assert rejected.executed is False
    assert second_registry.list_projects() == []
    assert first_registry.list_projects() == []

    accepted = first_gateway.execute(
        "create_project", payload, approval_receipt=receipt
    )
    assert accepted.executed is True
    assert len(first_registry.list_projects()) == 1


def test_gateway_does_not_allow_caller_to_override_its_session_scope():
    authority = ApprovalAuthority()
    registry = ProjectRegistry()
    gateway = build_project_gateway(
        registry, authority, session_scope="trusted-session"
    )
    payload = {"name": "Scope protected", "description": ""}
    receipt = authority.issue(
        "create_project", payload, session_scope="attacker-chosen-session"
    )

    with pytest.raises(TypeError):
        gateway.execute(
            "create_project", payload, approval_receipt=receipt,
            session_scope="attacker-chosen-session",
        )
    result = gateway.execute(
        "create_project", payload, approval_receipt=receipt
    )
    assert result.executed is False
    assert registry.list_projects() == []



def test_project_gateway_uses_durable_tenant_scoped_idempotency_ledger(tmp_path):
    from core.sqlite_security_store import SQLiteSecurityStore
    from core.storage import TenantKey

    tenant = TenantKey("local://apaa-personal", "local-owner")
    store = SQLiteSecurityStore(tmp_path / "security.sqlite3")
    authority = ApprovalAuthority(
        nonce_store=store,
        signing_secret=b"project-idempotency-test-secret-material",
    )
    registry = ProjectRegistry()
    gateway = build_project_gateway(
        registry, authority, session_scope="owner-session",
        idempotency_store=store,
    )
    payload = {"name": "One durable project", "description": "No duplicate dispatch"}

    first_receipt = authority.issue(
        "create_project", payload, tenant=tenant, session_scope="owner-session"
    )
    first = gateway.execute(
        "create_project", payload, approval_receipt=first_receipt,
        tenant=tenant, idempotency_key="owner-project-create-0001",
    )
    assert first.executed is True
    assert len(registry.list_projects()) == 1

    second_receipt = authority.issue(
        "create_project", payload, tenant=tenant, session_scope="owner-session"
    )
    replay = gateway.execute(
        "create_project", payload, approval_receipt=second_receipt,
        tenant=tenant, idempotency_key="owner-project-create-0001",
    )
    assert replay.executed is False
    assert "already completed" in replay.reason
    assert len(registry.list_projects()) == 1


def test_project_gateway_with_durable_ledger_requires_owner_and_request_key(tmp_path):
    from core.sqlite_security_store import SQLiteSecurityStore

    store = SQLiteSecurityStore(tmp_path / "security.sqlite3")
    authority = ApprovalAuthority(
        signing_secret=b"project-idempotency-test-secret-material",
    )
    registry = ProjectRegistry()
    gateway = build_project_gateway(
        registry, authority, idempotency_store=store,
    )
    payload = {"name": "Must not run", "description": ""}
    receipt = authority.issue("create_project", payload)
    result = gateway.execute("create_project", payload, approval_receipt=receipt)
    assert result.executed is False
    assert "validated owner and idempotency key" in result.reason
    assert registry.list_projects() == []
