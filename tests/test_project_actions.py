from core.project_actions import confirm_and_create_project
from core.projects import ProjectRegistry


def test_project_creation_is_gated_by_explicit_controller_invocation():
    registry = ProjectRegistry()
    # The UI calls this function only from its Confirm button branch.
    result = confirm_and_create_project(
        registry,
        "APAA workspace",
        "Reviewed project details",
    )
    assert result.executed is True
    assert result.output.name == "APAA workspace"
    assert result.output.description == "Reviewed project details"


def test_invalid_project_details_do_not_create_a_project():
    registry = ProjectRegistry()
    cases = [
        ("", "empty name"),
        ("x" * 81, "too long"),
        ("valid", "x" * 501),
    ]
    for name, description in cases:
        result = confirm_and_create_project(registry, name, description)
        assert result.executed is False
    assert registry.list_projects() == []


def test_non_text_project_details_are_rejected():
    registry = ProjectRegistry()
    result = confirm_and_create_project(registry, "valid", None)
    assert result.executed is False
    assert registry.list_projects() == []
