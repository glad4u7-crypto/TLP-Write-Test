import pytest

from core.projects import Project, ProjectRegistry


def test_project_requires_name():
    with pytest.raises(ValueError, match="name"):
        Project(name="  ")


def test_project_rejects_long_name():
    with pytest.raises(ValueError, match="80"):
        Project(name="x" * 81)


def test_registry_creates_and_gets_project():
    registry = ProjectRegistry()
    project = registry.create("TradeLab Pro", "Market analysis workspace")
    assert registry.get(project.project_id) == project
    assert registry.list_projects() == [project]


def test_registry_deletes_project():
    registry = ProjectRegistry()
    project = registry.create("Research")
    assert registry.delete(project.project_id) is True
    assert registry.get(project.project_id) is None
    assert registry.delete(project.project_id) is False


def test_registry_keeps_projects_isolated():
    first = ProjectRegistry()
    second = ProjectRegistry()
    first.create("Only in first")
    assert len(first.list_projects()) == 1
    assert second.list_projects() == []
