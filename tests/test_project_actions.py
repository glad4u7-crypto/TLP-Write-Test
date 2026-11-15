import pytest

from core.project_actions import create_project_after_confirmation
from core.projects import ProjectRegistry


def test_project_creation_is_blocked_without_explicit_confirmation():
    registry = ProjectRegistry()

    result = create_project_after_confirmation(
        registry,
        "APAA test",
        "Should not be created",
        confirmed_by_user=False,
    )

    assert result.executed is False
    assert registry.list_projects() == []


def test_project_creation_runs_through_approval_gateway_after_confirmation():
    registry = ProjectRegistry()

    result = create_project_after_confirmation(
        registry,
        "APAA workspace",
        "Created only after reviewing the exact details",
        confirmed_by_user=True,
    )

    assert result.executed is True
    assert result.output.name == "APAA workspace"
    assert result.output.description == "Created only after reviewing the exact details"
    assert registry.get(result.output.project_id) == result.output


@pytest.mark.parametrize(
    ("name", "description"),
    [
        ("", "empty name"),
        ("x" * 81, "too long"),
        ("valid", "x" * 501),
    ],
)
def test_invalid_project_details_do_not_create_a_project(name, description):
    registry = ProjectRegistry()

    result = create_project_after_confirmation(
        registry,
        name,
        description,
        confirmed_by_user=True,
    )

    assert result.executed is False
    assert registry.list_projects() == []
