import pytest

from core.approvals import ApprovalAuthority
from core.project_actions import build_project_gateway
from core.projects import Project, ProjectRegistry


def test_project_requires_name():
    with pytest.raises(ValueError, match="name"):
        Project(name="  ")


def test_project_rejects_long_name():
    with pytest.raises(ValueError, match="80"):
        Project(name="x" * 81)


def test_registry_mutation_requires_internal_capability():
    registry = ProjectRegistry()
    with pytest.raises(PermissionError, match="approval gateway"):
        registry.create("TradeLab Pro", "Market analysis workspace")
    with pytest.raises(PermissionError, match="approval gateway"):
        registry.delete("nonexistent")


def test_project_creation_requires_ui_issued_receipt():
    registry = ProjectRegistry()
    authority = ApprovalAuthority()
    gateway = build_project_gateway(registry, authority)
    payload = {"name": "TradeLab Pro", "description": "Market analysis workspace"}
    receipt = authority.issue("create_project", payload)

    result = gateway.execute("create_project", payload, approval_receipt=receipt)

    assert result.executed is True
    project = result.output
    assert registry.get(project.project_id) == project
    assert registry.list_projects() == [project]


def test_registry_keeps_projects_isolated():
    first = ProjectRegistry()
    second = ProjectRegistry()
    authority = ApprovalAuthority()
    gateway = build_project_gateway(first, authority)
    payload = {"name": "Only in first", "description": ""}
    receipt = authority.issue("create_project", payload)

    assert gateway.execute("create_project", payload, approval_receipt=receipt).executed
    assert len(first.list_projects()) == 1
    assert second.list_projects() == []
