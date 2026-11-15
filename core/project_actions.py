"""Trusted UI controller for the project's first approval-gated mutation.

The Streamlit UI calls this controller only inside the Confirm button branch,
after rendering the exact project name and description for user review.

This is an in-process trust boundary, not protection against arbitrary Python
code execution in the same process.
"""
from core.approvals import ApprovalAuthority
from core.execution import ExecutionGateway, ExecutionResult
from core.projects import ProjectRegistry


def confirm_and_create_project(
    registry: ProjectRegistry,
    name: str,
    description: str = "",
) -> ExecutionResult:
    """Create a project when invoked by the trusted UI's confirmation event."""
    if not isinstance(name, str) or not isinstance(description, str):
        return ExecutionResult(False, "Project details must be text.")
    payload = {
        "name": name.strip(),
        "description": description.strip(),
    }
    if not payload["name"] or len(payload["name"]) > 80 or len(payload["description"]) > 500:
        return ExecutionResult(False, "Project details are invalid or exceed the allowed length.")

    authority = ApprovalAuthority()
    gateway = ExecutionGateway(
        {
            "create_project": lambda data: registry.create(
                data["name"], data["description"]
            )
        },
        approval_authority=authority,
    )
    # This function is invoked only from the UI's explicit Confirm branch.
    receipt = authority.issue("create_project", payload)
    return gateway.execute(
        "create_project",
        payload,
        approval_receipt=receipt,
    )
