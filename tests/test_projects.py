import pytest

from core.approvals import ApprovalAuthority
from core.identity import AuthorizationDenied, Principal
from core.project_actions import build_project_gateway
from core.projects import Project, ProjectRegistry, _PROJECT_MUTATION_CAPABILITY


ALICE = Principal("alice", "https://issuer.example.test", True)
BOB = Principal("bob", "https://issuer.example.test", True)


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


def test_project_creation_requires_ui_issued_receipt_and_assigns_trusted_owner():
    registry = ProjectRegistry()
    authority = ApprovalAuthority()
    gateway = build_project_gateway(registry, authority, principal=ALICE)
    payload = {"name": "TradeLab Pro", "description": "Market analysis workspace"}
    receipt = authority.issue("create_project", payload)

    result = gateway.execute("create_project", payload, approval_receipt=receipt)

    assert result.executed is True
    project = result.output
    assert project.owner_subject == "alice"
    assert registry.get(project.project_id) == project
    assert registry.list_projects() == [project]


def test_client_payload_cannot_spoof_project_owner():
    registry = ProjectRegistry()
    authority = ApprovalAuthority()
    gateway = build_project_gateway(registry, authority, principal=ALICE)
    payload = {"name": "Owned by Alice", "description": "", "owner_subject": "bob"}
    receipt = authority.issue("create_project", payload)
    result = gateway.execute("create_project", payload, approval_receipt=receipt)
    assert result.executed is False
    assert registry.list_projects() == []


def test_registry_keeps_projects_isolated():
    first = ProjectRegistry()
    second = ProjectRegistry()
    authority = ApprovalAuthority()
    gateway = build_project_gateway(first, authority, principal=ALICE)
    payload = {"name": "Only in first", "description": ""}
    receipt = authority.issue("create_project", payload)
    assert gateway.execute("create_project", payload, approval_receipt=receipt).executed
    assert len(first.list_projects()) == 1
    assert second.list_projects() == []


def _owned_registry():
    registry = ProjectRegistry()
    project = registry.create(
        "Alice private", "secret", owner_subject="alice", owner_issuer=ALICE.issuer,
        _capability=_PROJECT_MUTATION_CAPABILITY,
    )
    return registry, project


def test_owner_can_list_and_read_only_owned_projects():
    registry, project = _owned_registry()
    assert registry.list_projects_for_owner(ALICE) == [project]
    assert registry.get_for_owner(project.project_id, ALICE) == project
    assert registry.list_projects_for_owner(BOB) == []


def test_non_owner_cannot_read_project():
    registry, project = _owned_registry()
    with pytest.raises(AuthorizationDenied):
        registry.get_for_owner(project.project_id, BOB)


def test_non_owner_cannot_update_or_delete_project():
    registry, project = _owned_registry()
    with pytest.raises(AuthorizationDenied):
        registry.update_for_owner(
            project.project_id, BOB, name="Stolen", description="",
            _capability=_PROJECT_MUTATION_CAPABILITY,
        )
    with pytest.raises(AuthorizationDenied):
        registry.delete_for_owner(
            project.project_id, BOB, _capability=_PROJECT_MUTATION_CAPABILITY
        )
    assert registry.get_for_owner(project.project_id, ALICE) == project


def test_owner_can_update_and_delete_project():
    registry, project = _owned_registry()
    updated = registry.update_for_owner(
        project.project_id, ALICE, name="Updated", description="new",
        _capability=_PROJECT_MUTATION_CAPABILITY,
    )
    assert updated.owner_subject == "alice"
    assert updated.name == "Updated"
    assert registry.delete_for_owner(
        project.project_id, ALICE, _capability=_PROJECT_MUTATION_CAPABILITY
    )
    assert registry.get(project.project_id) is None



def test_same_subject_from_different_issuer_cannot_list_or_read_project():
    registry = ProjectRegistry()
    project = registry.create(
        "Issuer scoped", "", owner_subject="alice", owner_issuer=ALICE.issuer,
        _capability=_PROJECT_MUTATION_CAPABILITY,
    )
    other_issuer = Principal("alice", "https://other-issuer.example", True)
    assert registry.list_projects_for_owner(other_issuer) == []
    with pytest.raises(AuthorizationDenied):
        registry.get_for_owner(project.project_id, other_issuer)


def test_legacy_project_without_issuer_is_not_visible_or_readable_to_authenticated_user():
    registry = ProjectRegistry()
    legacy = registry.create(
        "Legacy unscoped", "", owner_subject="alice",
        _capability=_PROJECT_MUTATION_CAPABILITY,
    )
    assert registry.list_projects_for_owner(ALICE) == []
    with pytest.raises(AuthorizationDenied):
        registry.get_for_owner(legacy.project_id, ALICE)
