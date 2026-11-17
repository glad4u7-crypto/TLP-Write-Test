"""Owner-only project association guard for task checkpoints."""
from __future__ import annotations

from core.identity import AuthorizationDenied, Principal, require_authenticated
from core.memory import SQLiteMemoryStore, TaskCheckpoint
from core.sqlite_project_store import SQLiteProjectStore
from core.storage import TenantKey


class OwnerProjectCheckpointAccess:
    """Bind checkpoint save/recovery to an existing project owned by the actor."""

    def __init__(
        self,
        memory_store: SQLiteMemoryStore,
        project_store: SQLiteProjectStore,
        principal: Principal,
    ) -> None:
        if not isinstance(memory_store, SQLiteMemoryStore):
            raise TypeError("A SQLiteMemoryStore is required.")
        if not isinstance(project_store, SQLiteProjectStore):
            raise TypeError("A SQLiteProjectStore is required.")
        verified = require_authenticated(principal)
        self._memory = memory_store
        self._projects = project_store
        self._tenant = TenantKey(verified.issuer, verified.subject)

    def _require_owned_project(self, project_id: str) -> None:
        if not isinstance(project_id, str) or not project_id.strip():
            raise ValueError("A project ID is required.")
        if self._projects.get_for_tenant(self._tenant, project_id) is None:
            raise AuthorizationDenied(
                "A checkpoint can only be associated with a project owned by this identity."
            )

    def save_checkpoint(
        self, *, project_id: str, label: str, summary: str,
        next_action: str, status: str = "active", consent: bool = False,
    ) -> TaskCheckpoint:
        self._require_owned_project(project_id)
        return self._memory.save_checkpoint(
            self._tenant, project_id=project_id, label=label, summary=summary,
            next_action=next_action, status=status, consent=consent,
        )

    def latest_checkpoint(self, project_id: str) -> TaskCheckpoint | None:
        self._require_owned_project(project_id)
        return self._memory.latest_checkpoint(self._tenant, project_id)
