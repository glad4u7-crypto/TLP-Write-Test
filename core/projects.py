"""Session-friendly project registry for the zero-cost agent foundation.

The registry is intentionally storage-agnostic. The Streamlit UI currently keeps
it in session state; persistent storage can be added later without paid services.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4


@dataclass(frozen=True)
class Project:
    name: str
    description: str = ""
    project_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Project name must not be empty.")
        if len(self.name.strip()) > 80:
            raise ValueError("Project name must be 80 characters or fewer.")
        if len(self.description.strip()) > 500:
            raise ValueError("Project description must be 500 characters or fewer.")


class ProjectRegistry:
    """In-memory CRUD registry; persistence is supplied by the application."""

    def __init__(self, projects: list[Project] | None = None) -> None:
        self._projects: dict[str, Project] = {}
        for project in projects or []:
            self._projects[project.project_id] = project

    def create(self, name: str, description: str = "") -> Project:
        project = Project(name=name.strip(), description=description.strip())
        self._projects[project.project_id] = project
        return project

    def list_projects(self) -> list[Project]:
        return list(self._projects.values())

    def get(self, project_id: str) -> Project | None:
        return self._projects.get(project_id)

    def delete(self, project_id: str) -> bool:
        return self._projects.pop(project_id, None) is not None
