"""Narrow owner-only management facade for project read grants.

The controller intentionally exposes no generic role, write, execution, file,
memory, checkpoint, invitation, browser, or worker grant operation. The caller
must supply a Principal created by trusted server-side authentication.
"""
from __future__ import annotations

from core.identity import (
    AuthorizationDenied,
    Principal,
    require_authenticated,
)
from core.project_access import (
    ProjectAccessControl,
    ProjectAccessEvent,
    ProjectAccessGrant,
)


class OwnerProjectAccessController:
    """Owner-only grant/revoke and audit-read boundary for one project ACL."""

    def __init__(self, access_control: ProjectAccessControl) -> None:
        if not isinstance(access_control, ProjectAccessControl):
            raise TypeError("A ProjectAccessControl instance is required.")
        self._access = access_control

    def _require_owner(self, project_id: str, actor: Principal) -> Principal:
        if not isinstance(project_id, str) or not project_id.strip():
            raise ValueError("A project ID is required.")
        verified = require_authenticated(actor)
        if not self._access.is_owner(project_id, verified):
            raise AuthorizationDenied("Only the exact project owner may manage access.")
        return verified

    def grant_read(
        self, project_id: str, *, actor: Principal, grantee: Principal,
    ) -> ProjectAccessGrant:
        """Grant read-only project visibility; never grants mutation or execution."""
        owner = self._require_owner(project_id, actor)
        verified_grantee = require_authenticated(grantee)
        if (
            owner.issuer == verified_grantee.issuer
            and owner.subject == verified_grantee.subject
        ):
            raise ValueError("The owner already has access.")
        return self._access.grant_read(project_id, owner, verified_grantee)

    def revoke_read(
        self, project_id: str, *, actor: Principal, grantee: Principal,
    ) -> bool:
        """Revoke only the exact issuer+subject read grant; idempotent if absent."""
        owner = self._require_owner(project_id, actor)
        verified_grantee = require_authenticated(grantee)
        if (
            owner.issuer == verified_grantee.issuer
            and owner.subject == verified_grantee.subject
        ):
            raise ValueError("The owner cannot revoke their own ownership access.")
        return self._access.revoke_read(project_id, owner, verified_grantee)

    def list_grants(
        self, project_id: str, *, actor: Principal,
    ) -> list[ProjectAccessGrant]:
        owner = self._require_owner(project_id, actor)
        return self._access.list_for_owner(project_id, owner)

    def list_events(
        self, project_id: str, *, actor: Principal,
    ) -> list[ProjectAccessEvent]:
        owner = self._require_owner(project_id, actor)
        return self._access.list_events_for_owner(project_id, owner)
