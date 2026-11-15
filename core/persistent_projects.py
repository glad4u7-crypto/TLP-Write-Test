"""ProjectRegistry-compatible facade backed by tenant-scoped SQLite storage."""
from __future__ import annotations

from core.identity import Principal, AuthorizationDenied, require_authenticated
from core.projects import Project, ProjectRegistry, _PROJECT_MUTATION_CAPABILITY
from core.sqlite_project_store import SQLiteProjectStore
from core.storage import TenantKey


class PersistentProjectRegistry(ProjectRegistry):
    """Persistent registry bound to one validated OIDC tenant."""

    def __init__(self, store: SQLiteProjectStore, tenant: TenantKey) -> None:
        if not isinstance(store, SQLiteProjectStore) or not isinstance(tenant, TenantKey):
            raise TypeError("Persistent registry requires SQLiteProjectStore and TenantKey.")
        self._store = store
        self._tenant = tenant
        self._projects = {}

    def _as_project(self, stored) -> Project:
        return Project(
            name=stored.name,
            description=stored.description,
            project_id=stored.project_id,
            created_at=stored.created_at,
            owner_subject=self._tenant.subject,
            owner_issuer=self._tenant.issuer,
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
        stored = self._store.create(self._tenant, name=name, description=description)
        return self._as_project(stored)

    def list_projects(self) -> list[Project]:
        return [self._as_project(item) for item in self._store.list_for_tenant(self._tenant)]

    def list_projects_for_owner(self, principal: Principal) -> list[Project]:
        self._check_principal(principal)
        return self.list_projects()

    def get(self, project_id: str) -> Project | None:
        stored = self._store.get_for_tenant(self._tenant, project_id)
        return self._as_project(stored) if stored else None

    def get_for_owner(self, project_id: str, principal: Principal) -> Project | None:
        self._check_principal(principal)
        return self.get(project_id)

    def update_for_owner(
        self, project_id: str, principal: Principal, *, name: str, description: str,
        _capability: object | None = None,
    ) -> Project:
        if _capability is not _PROJECT_MUTATION_CAPABILITY:
            raise PermissionError("Project updates must go through a trusted controller.")
        self._check_principal(principal)
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
        self._check_principal(principal)
        return self._store.delete_for_tenant(self._tenant, project_id)

    def delete(self, project_id: str, *, _capability: object | None = None) -> bool:
        if _capability is not _PROJECT_MUTATION_CAPABILITY:
            raise PermissionError("Project deletion must go through the approval gateway.")
        return self._store.delete_for_tenant(self._tenant, project_id)
