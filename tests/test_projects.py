import pytest

from core.projects import Project, ProjectRegistry
from core.project_actions import confirm_and_create_project


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


def test_project_controller_creates_and_gets_project():
    registry = ProjectRegistry()
    result = confirm_and_create_project(
        registry, "TradeLab Pro", "Market analysis workspace"
    )
    assert result.executed is True
    project = result.output
    assert registry.get(project.project_id) == project
    assert registry.list_projects() == [project]


def test_registry_keeps_projects_isolated():
    first = ProjectRegistry()
    second = ProjectRegistry()
    assert confirm_and_create_project(first, "Only in first").executed is True
    assert len(first.list_projects()) == 1
    assert second.list_projects() == []
