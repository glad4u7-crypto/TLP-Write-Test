"""Session-friendly project registry with owner-scoped access.

The registry is storage-agnostic. The current Streamlit UI stores it per session.
Owner checks are application authorization controls, not isolation from arbitrary
Python code executing inside the same process.
"""
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from uuid import uuid4

from core.identity import Principal, require_project_owner

_PROJECT_MUTATION_CAPABILITY = object()


@dataclass(frozen=True)
class Project:
    name: str
    description: str = ""
    project_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    owner_subject: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("Project name must not be empty.")
        if len(self.name.strip()) > 80:
            raise ValueError("Project name must be 80 characters or fewer.")
        if not isinstance(self.description, str) or len(self.description.strip()) > 500:
            raise ValueError("Project description must be 500 characters or fewer.")
        if self.owner_subject is not None and (
            not isinstance(self.owner_subject, str) or not self.owner_subject.strip()
        ):
            raise ValueError("Project owner subject must be non-empty text.")


class ProjectRegistry:
    """In-memory CRUD registry; persistence is supplied by the application."""

    def __init__(self, projects: list[Project] | None = None) -> None:
        self._projects: dict[str, Project] = {}
        for project in projects or []:
            self._projects[project.project_id] = project

    def create(
        self,
        name: str,
        description: str = "",
        *,
        owner_subject: str | None = None,
        _capability: object | None = None,
    ) -> Project:
        if _capability is not _PROJECT_MUTATION_CAPABILITY:
            raise PermissionError("Project creation must go through the approval gateway.")
        project = Project(
            name=name.strip() if isinstance(name, str) else name,
            description=description.strip() if isinstance(description, str) else description,
            owner_subject=owner_subject,
        )
        self._projects[project.project_id] = project
        return project

    def list_projects(self) -> list[Project]:
        """Trusted internal listing; do not expose directly to untrusted callers."""
        return list(self._projects.values())

    def list_projects_for_owner(self, principal: Principal) -> list[Project]:
        from core.identity import require_authenticated
        verified = require_authenticated(principal)
        return [
            project for project in self._projects.values()
            if project.owner_subject == verified.subject
        ]

    def get(self, project_id: str) -> Project | None:
        """Trusted internal lookup; use get_for_owner at user-facing boundaries."""
        return self._projects.get(project_id)

    def get_for_owner(self, project_id: str, principal: Principal) -> Project | None:
        project = self._projects.get(project_id)
        if project is None:
            return None
        require_project_owner(principal, project.owner_subject)
        return project

    def update_for_owner(
        self,
        project_id: str,
        principal: Principal,
        *,
        name: str,
        description: str,
        _capability: object | None = None,
    ) -> Project:
        if _capability is not _PROJECT_MUTATION_CAPABILITY:
            raise PermissionError("Project updates must go through a trusted controller.")
        project = self._projects.get(project_id)
        if project is None:
            raise KeyError("Project not found.")
        require_project_owner(principal, project.owner_subject)
        updated = replace(project, name=name.strip(), description=description.strip())
        self._projects[project_id] = updated
        return updated

    def delete_for_owner(
        self,
        project_id: str,
        principal: Principal,
        *,
        _capability: object | None = None,
    ) -> bool:
        if _capability is not _PROJECT_MUTATION_CAPABILITY:
            raise PermissionError("Project deletion must go through a trusted controller.")
        project = self._projects.get(project_id)
        if project is None:
            return False
        require_project_owner(principal, project.owner_subject)
        del self._projects[project_id]
        return True

    def delete(
        self,
        project_id: str,
        *,
        _capability: object | None = None,
    ) -> bool:
        if _capability is not _PROJECT_MUTATION_CAPABILITY:
            raise PermissionError("Project deletion must go through the approval gateway.")
        return self._projects.pop(project_id, None) is not None
