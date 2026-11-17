from pathlib import Path
import os
import pytest

from core.memory import SQLiteMemoryStore
from core.storage import TenantKey


@pytest.fixture
def store(tmp_path):
    return SQLiteMemoryStore(tmp_path / "private" / "memory.sqlite3")


@pytest.fixture
def alice():
    return TenantKey("https://issuer.example", "alice")


@pytest.fixture
def bob():
    return TenantKey("https://issuer.example", "bob")


def test_all_writes_require_explicit_consent(store, alice):
    with pytest.raises(PermissionError):
        store.add_memory(alice, category="fact", content="likes concise plans")
    with pytest.raises(PermissionError):
        store.add_knowledge(alice, title="Plan", content="steps")
    with pytest.raises(PermissionError):
        store.append_turn(alice, conversation_id="c1", role="user", content="hello")
    with pytest.raises(PermissionError):
        store.save_preference(alice, key="language", value="bn")
    with pytest.raises(PermissionError):
        store.save_checkpoint(alice, project_id="p1", label="CP1",
                              summary="done", next_action="continue")


def test_long_term_memory_crud_and_tenant_isolation(store, alice, bob):
    record = store.add_memory(alice, category="preference", content="Prefers Bengali",
                              tags=["language"], consent=True)
    assert store.list_memories(alice)[0] == record
    assert store.list_memories(bob) == []
    assert store.delete_memory(bob, record.memory_id) is False
    assert store.delete_memory(alice, record.memory_id) is True


def test_knowledge_collection_and_lexical_retrieval(store, alice, bob):
    doc = store.add_knowledge(alice, title="Python safety", content="Use allowlists and fail closed.",
                              tags=["security"], consent=True)
    assert store.list_knowledge(alice) == [doc]
    result = store.search(alice, "allowlists security")
    assert result and result[0]["id"] == doc.document_id
    assert store.search(bob, "allowlists") == []
    assert store.delete_knowledge(bob, doc.document_id) is False
    assert store.delete_knowledge(alice, doc.document_id) is True


def test_short_term_conversation_continuity_and_deletion(store, alice):
    store.append_turn(alice, conversation_id="thread-1", role="user",
                      content="We are building APAA", consent=True)
    store.append_turn(alice, conversation_id="thread-1", role="assistant",
                      content="Continue from checkpoint 7", consent=True)
    turns = store.conversation_context(alice, "thread-1")
    assert [turn.role for turn in turns] == ["user", "assistant"]
    assert store.delete_conversation(alice, "thread-1") == 2
    assert store.conversation_context(alice, "thread-1") == []


def test_preference_upsert_and_isolation(store, alice, bob):
    store.save_preference(alice, key="language", value="Bengali", consent=True)
    store.save_preference(alice, key="language", value="bn", consent=True)
    assert store.get_preferences(alice) == {"language": "bn"}
    assert store.get_preferences(bob) == {}
    assert store.delete_preference(bob, "language") is False
    assert store.delete_preference(alice, "language") is True


def test_checkpoint_recovery_is_project_and_tenant_scoped(store, alice, bob):
    cp = store.save_checkpoint(alice, project_id="APAA", label="S07-C03-P03",
                               summary="Context recovery ready", next_action="Run final matrix",
                               consent=True)
    assert store.latest_checkpoint(alice, "APAA") == cp
    assert store.latest_checkpoint(bob, "APAA") is None
    assert store.latest_checkpoint(alice, "Other") is None


def test_expiry_purge_keeps_pinned_memory(store, alice):
    expired = store.add_memory(alice, category="fact", content="temporary note",
                               expires_in_days=1, consent=True)
    pinned = store.add_memory(alice, category="fact", content="keep this",
                              expires_in_days=1, pinned=True, consent=True)
    with pytest.MonkeyPatch.context() as mp:
        from core import memory
        mp.setattr(memory, "_now", lambda: "9999-01-01T00:00:00+00:00")
        assert store.purge_expired_memories(alice) == 1
    assert store.list_memories(alice) == [pinned]


@pytest.mark.parametrize("content", [
    "password=secret123", "api_key: abcdefghijklmnop",
    "-----BEGIN PRIVATE KEY-----",
    "Bearer abcdefghijklmnop",
])
def test_credential_like_content_is_rejected(store, alice, content):
    with pytest.raises(ValueError):
        store.add_memory(alice, category="fact", content=content, consent=True)


def test_invalid_category_and_unbounded_limits_rejected(store, alice):
    with pytest.raises(ValueError):
        store.add_memory(alice, category="credential", content="no", consent=True)
    with pytest.raises(ValueError):
        store.search(alice, "hello", limit=1000)


def test_database_file_is_private(store):
    path = Path(store.database_path)
    if os.name == "posix":
        assert path.stat().st_mode & 0o777 == 0o600
        assert path.parent.stat().st_mode & 0o777 == 0o700



def test_checkpoint_history_is_newest_first_and_bounded(store, alice, bob):
    first = store.save_checkpoint(
        alice, project_id="APAA", label="Start", summary="Initial work",
        next_action="Read first file", status="active", consent=True,
    )
    second = store.save_checkpoint(
        alice, project_id="APAA", label="Progress", summary="Reviewed two files",
        next_action="Run tests", status="blocked", consent=True,
    )
    history = store.list_checkpoints(alice, "APAA")
    assert [item.checkpoint_id for item in history] == [
        second.checkpoint_id, first.checkpoint_id
    ]
    assert history[0].status == "blocked"
    assert store.list_checkpoints(alice, "APAA", limit=1) == (history[0],)
    assert store.list_checkpoints(bob, "APAA") == ()



def test_task_plan_step_progress_is_durable_consent_gated_and_tenant_scoped(store, alice, bob):
    with pytest.raises(PermissionError):
        store.set_task_plan_step_progress(
            alice, project_id="p1", plan_id="plan-0123456789abcdef",
            step_id="step-1", title="Review files", completed=True,
        )
    saved = store.set_task_plan_step_progress(
        alice, project_id="p1", plan_id="plan-0123456789abcdef",
        step_id="step-1", title="Review files", completed=True, consent=True,
    )
    assert saved.status == "completed"
    assert store.list_task_plan_step_progress(
        alice, project_id="p1", plan_id="plan-0123456789abcdef"
    ) == (saved,)
    assert store.list_task_plan_step_progress(
        bob, project_id="p1", plan_id="plan-0123456789abcdef"
    ) == ()
    reset = store.set_task_plan_step_progress(
        alice, project_id="p1", plan_id="plan-0123456789abcdef",
        step_id="step-1", title="Review files", completed=False, consent=True,
    )
    assert reset.status == "pending"
    assert len(store.list_task_plan_step_progress(
        alice, project_id="p1", plan_id="plan-0123456789abcdef"
    )) == 1


@pytest.mark.parametrize("step_id", ["../escape", "", "a" * 65])
def test_task_plan_step_progress_rejects_unsafe_step_ids(store, alice, step_id):
    with pytest.raises(ValueError):
        store.set_task_plan_step_progress(
            alice, project_id="p1", plan_id="plan-0123456789abcdef",
            step_id=step_id, title="Step", completed=True, consent=True,
        )
