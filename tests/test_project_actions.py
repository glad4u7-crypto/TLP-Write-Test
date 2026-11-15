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
    gateway = build_project_gateway(registry, authority, audit_log=audit)
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
