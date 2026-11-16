"""ProjectRegistry-compatible facade with owner-only writes and explicit ACL reads."""
from __future__ import annotations

from core.identity import Principal, AuthorizationDenied, require_authenticated
from core.projects import Project, ProjectRegistry, _PROJECT_MUTATION_CAPABILITY
from core.project_access import ProjectAccessControl
from core.sqlite_project_store import SQLiteProjectStore
from core.storage import TenantKey


class PersistentProjectRegistry(ProjectRegistry):
    """Persistent registry; collaborators receive explicit read-only access only."""

    def __init__(
        self, store: SQLiteProjectStore, tenant: TenantKey, *,
        access_control: ProjectAccessControl | None = None,
    ) -> None:
        if not isinstance(store, SQLiteProjectStore) or not isinstance(tenant, TenantKey):
            raise TypeError("Persistent registry requires SQLiteProjectStore and TenantKey.")
        if access_control is not None and not isinstance(access_control, ProjectAccessControl):
            raise TypeError("A ProjectAccessControl instance is required.")
        self._store = store
        self._tenant = tenant
        self._access_control = access_control
        self._projects = {}

    @staticmethod
    def _as_project(stored) -> Project:
        return Project(
            name=stored.name,
            description=stored.description,
            project_id=stored.project_id,
            created_at=stored.created_at,
            owner_subject=stored.tenant.subject,
            owner_issuer=stored.tenant.issuer,
        )

    def _check_principal(self, principal: Principal) -> None:
        verified = require_authenticated(principal)
        if (verified.issuer, verified.subject) != (self._tenant.issuer, self._tenant.subject):
            raise AuthorizationDenied("Authenticated principal does not match this registry tenant.")

    def create(
        self, name: str, description: str = "", *, owner_subject: str | None = None,
        owner_issuer: str | None = None, _capability: object | None = None,
    ) -> Project:
        if _capability is not _PROJECT_MUTATION_CAPABILITY:
            raise PermissionError("Project creation must go through the approval gateway.")
        if owner_subject != self._tenant.subject or owner_issuer != self._tenant.issuer:
            raise AuthorizationDenied("Project owner does not match the authenticated tenant.")
        return self._as_project(self._store.create(self._tenant, name=name, description=description))

    def list_projects(self) -> list[Project]:
        """Trusted internal owner-tenant listing; not a collaborator-facing API."""
        return [self._as_project(item) for item in self._store.list_for_tenant(self._tenant)]

    def list_projects_for_owner(self, principal: Principal) -> list[Project]:
        self._check_principal(principal)
        return self.list_projects()

    def get(self, project_id: str) -> Project | None:
        """Trusted internal owner-tenant lookup; use get_for_principal at read boundaries."""
        stored = self._store.get_for_tenant(self._tenant, project_id)
        return self._as_project(stored) if stored else None

    def get_for_owner(self, project_id: str, principal: Principal) -> Project | None:
        self._check_principal(principal)
        return self.get(project_id)

    def list_projects_for_principal(self, principal: Principal) -> list[Project]:
        """List only owned or actively granted projects; requires an ACL store."""
        verified = require_authenticated(principal)
        if self._access_control is None:
            raise PermissionError("Explicit access control is required for collaborator reads.")
        candidates = self._store.list_all_for_access_filter()
        return [
            self._as_project(item) for item in candidates
            if self._access_control.has_access(item.project_id, verified)
        ]

    def get_for_principal(self, project_id: str, principal: Principal) -> Project | None:
        """Read lookup that rechecks current ACL on every call (revocation takes effect immediately)."""
        verified = require_authenticated(principal)
        if self._access_control is None:
            raise PermissionError("Explicit access control is required for collaborator reads.")
        stored = self._store.get_by_id_for_access_filter(project_id)
        if stored is None or not self._access_control.has_access(project_id, verified):
            return None
        return self._as_project(stored)

    def update_for_owner(
        self, project_id: str, principal: Principal, *, name: str, description: str,
        _capability: object | None = None,
    ) -> Project:
        if _capability is not _PROJECT_MUTATION_CAPABILITY:
            raise PermissionError("Project updates must go through a trusted controller.")
        verified = require_authenticated(principal)
        if self._access_control is not None and not self._access_control.is_owner(project_id, verified):
            raise AuthorizationDenied("Only the exact project owner may update this project.")
        self._check_principal(verified)
        stored = self._store.update_for_tenant(
            self._tenant, project_id, name=name, description=description
        )
        if stored is None:
            raise KeyError("Project not found.")
        return self._as_project(stored)

    def delete_for_owner(
        self, project_id: str, principal: Principal, *, _capability: object | None = None,
    ) -> bool:
        if _capability is not _PROJECT_MUTATION_CAPABILITY:
            raise PermissionError("Project deletion must go through a trusted controller.")
        verified = require_authenticated(principal)
        if self._access_control is not None and not self._access_control.is_owner(project_id, verified):
            raise AuthorizationDenied("Only the exact project owner may delete this project.")
        self._check_principal(verified)
        return self._store.delete_for_tenant(self._tenant, project_id)

    def delete(self, project_id: str, *, _capability: object | None = None) -> bool:
        if _capability is not _PROJECT_MUTATION_CAPABILITY:
            raise PermissionError("Project deletion must go through the approval gateway.")
        return self._store.delete_for_tenant(self._tenant, project_id)
