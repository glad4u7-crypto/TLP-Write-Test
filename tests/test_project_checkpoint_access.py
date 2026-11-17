import pytest

from core.identity import AuthorizationDenied, Principal
from core.memory import SQLiteMemoryStore
from core.project_checkpoint_access import OwnerProjectCheckpointAccess
from core.sqlite_project_store import SQLiteProjectStore
from core.storage import TenantKey


OWNER = Principal("owner", "https://owner.example", True)
OTHER = Principal("other", "https://other.example", True)


def test_checkpoint_controller_requires_existing_exact_owner_project(tmp_path):
    project_store = SQLiteProjectStore(tmp_path / "projects.sqlite3")
    memory_store = SQLiteMemoryStore(tmp_path / "memory.sqlite3")
    owner_project = project_store.create(
        TenantKey(OWNER.issuer, OWNER.subject), name="Owned", description=""
    )
    other_project = project_store.create(
        TenantKey(OTHER.issuer, OTHER.subject), name="Not owned", description=""
    )
    checkpoints = OwnerProjectCheckpointAccess(memory_store, project_store, OWNER)

    saved = checkpoints.save_checkpoint(
        project_id=owner_project.project_id, label="P36",
        summary="Owner checkpoint", next_action="Continue", consent=True,
    )
    assert checkpoints.latest_checkpoint(owner_project.project_id) == saved

    with pytest.raises(AuthorizationDenied):
        checkpoints.save_checkpoint(
            project_id=other_project.project_id, label="Spoof",
            summary="Must not persist", next_action="No", consent=True,
        )
    with pytest.raises(AuthorizationDenied):
        checkpoints.latest_checkpoint(other_project.project_id)
    with pytest.raises(AuthorizationDenied):
        checkpoints.latest_checkpoint("missing-project")


def test_checkpoint_controller_requires_authenticated_principal(tmp_path):
    project_store = SQLiteProjectStore(tmp_path / "projects.sqlite3")
    memory_store = SQLiteMemoryStore(tmp_path / "memory.sqlite3")
    with pytest.raises(PermissionError):
        OwnerProjectCheckpointAccess(
            memory_store, project_store,
            Principal("owner", "https://owner.example", False),
        )
