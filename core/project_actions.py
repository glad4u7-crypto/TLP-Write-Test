"""Trusted project-action handler registration for the Streamlit UI.

This module deliberately does not create approvals. The UI must issue a
one-time receipt only inside its explicit Confirm-button event and pass that
receipt to the returned gateway.
"""
from core.approvals import ApprovalAuthority
from core.audit import JsonlAuditLog
from core.execution import ExecutionGateway
from core.projects import ProjectRegistry, _PROJECT_MUTATION_CAPABILITY


def build_project_gateway(
    registry: ProjectRegistry,
    approval_authority: ApprovalAuthority,
    *,
    audit_log: JsonlAuditLog | None = None,
) -> ExecutionGateway:
    """Build the project gateway without issuing or consuming any approval."""
    if not isinstance(approval_authority, ApprovalAuthority):
        raise TypeError("A trusted ApprovalAuthority instance is required.")

    def create_project(data):
        return registry.create(
            data["name"],
            data["description"],
            _capability=_PROJECT_MUTATION_CAPABILITY,
        )

    return ExecutionGateway(
        {"create_project": create_project},
        approval_authority=approval_authority,
        audit_log=audit_log,
    )
