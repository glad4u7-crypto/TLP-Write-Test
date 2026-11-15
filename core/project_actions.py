"""Trusted UI controller for the project's first approval-gated mutation.

Only the application UI should call this function, and only after the user
reviews the exact project name and description and presses Confirm.
"""
from core.approvals import ApprovalAuthority
from core.execution import ExecutionGateway, ExecutionResult
from core.projects import ProjectRegistry


def create_project_after_confirmation(
    registry: ProjectRegistry,
    name: str,
    description: str = "",
    *,
    confirmed_by_user: bool,
) -> ExecutionResult:
    """Create a project through the gateway after an explicit UI confirmation."""
    if confirmed_by_user is not True:
        return ExecutionResult(False, "Explicit user confirmation is required.")

    payload = {
        "name": name.strip(),
        "description": description.strip(),
    }
    authority = ApprovalAuthority()
    gateway = ExecutionGateway(
        {
            "create_project": lambda data: registry.create(
                data["name"], data["description"]
            )
        },
        approval_authority=authority,
    )
    receipt = authority.issue(
        "create_project",
        payload,
        confirmed_by_user=True,
    )
    return gateway.execute(
        "create_project",
        payload,
        approval_receipt=receipt,
    )
