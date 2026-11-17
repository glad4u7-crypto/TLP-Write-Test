"""Trusted project-action handler registration for the Streamlit UI.

The UI must issue a one-time receipt only inside its explicit Confirm-button event.
The owner is taken from the trusted Principal captured by the server-side controller,
never from the task payload or a client-supplied owner field.
"""
from core.approvals import ApprovalAuthority
from core.audit import JsonlAuditLog
from core.execution import ExecutionGateway
from core.identity import Principal, require_authenticated
from core.projects import ProjectRegistry, _PROJECT_MUTATION_CAPABILITY
from core.storage import TenantKey


def build_project_gateway(
    registry: ProjectRegistry,
    approval_authority: ApprovalAuthority,
    *,
    audit_log: JsonlAuditLog | None = None,
    principal: Principal | None = None,
    session_scope: str = "",
) -> ExecutionGateway:
    if not isinstance(approval_authority, ApprovalAuthority):
        raise TypeError("A trusted ApprovalAuthority instance is required.")
    if principal is not None:
        principal = require_authenticated(principal)
        owner_subject = principal.subject
    else:
        # Local-only mode is explicitly unauthenticated and must not be public.
        # Persistent local registries expose their fixed server-side tenant;
        # legacy in-memory test registries retain the historical prototype ID.
        local_tenant = getattr(registry, "_tenant", None)
        if isinstance(local_tenant, TenantKey):
            owner_subject = local_tenant.subject
            owner_issuer = local_tenant.issuer
        else:
            owner_subject = "local-prototype"
            owner_issuer = None

    def create_project(data):
        if not isinstance(data, dict) or set(data) != {"name", "description"}:
            raise ValueError("Project payload must contain only name and description.")
        return registry.create(
            data["name"],
            data["description"],
            owner_subject=owner_subject,
            owner_issuer=principal.issuer if principal is not None else owner_issuer,
            _capability=_PROJECT_MUTATION_CAPABILITY,
        )

    return ExecutionGateway(
        {"create_project": create_project},
        approval_authority=approval_authority,
        audit_log=audit_log,
        session_scope=session_scope,
    )
