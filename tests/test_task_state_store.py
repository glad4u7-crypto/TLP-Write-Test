from pathlib import Path
import os
import sqlite3
import threading

import pytest

from core.models import TaskStatus
from core.storage import TenantKey
from core.task_lifecycle import TaskLifecycle, TaskLifecycleEvent, TaskSnapshot
from core.task_state_store import (
    SQLiteTaskStateStore,
    TaskStateConflict,
    TaskStateNotFound,
)


ALICE = TenantKey("https://issuer.example", "alice")
BOB = TenantKey("https://issuer.example", "bob")


@pytest.fixture
def store(tmp_path):
    return SQLiteTaskStateStore(tmp_path / "private" / "task-state.sqlite3")


def make_initial():
    lifecycle = TaskLifecycle()
    snapshot = lifecycle.create("collect public information")
    return lifecycle, snapshot, lifecycle.events[-1]


def test_create_requires_explicit_consent(store):
    _, snapshot, event = make_initial()
    with pytest.raises(PermissionError):
        store.create(ALICE, snapshot, event)


def test_task_state_and_event_persist_across_store_reconstruction(tmp_path):
    path = tmp_path / "private" / "tasks.sqlite3"
    store = SQLiteTaskStateStore(path)
    lifecycle, initial, created = make_initial()
    store.create(ALICE, initial, created, consent=True)

    planned = lifecycle.transition(initial.task.task_id, TaskStatus.PLANNED, expected_version=0)
    transition = lifecycle.events[-1]
    store.save_transition(ALICE, planned, transition, expected_version=0, consent=True)

    reopened = SQLiteTaskStateStore(path)
    recovered = reopened.get(ALICE, initial.task.task_id)
    assert recovered is not None
    assert recovered.snapshot.task.status is TaskStatus.PLANNED
    assert recovered.snapshot.version == 1
    assert [event.to_status for event in reopened.events(ALICE, initial.task.task_id)] == [
        TaskStatus.DRAFT, TaskStatus.PLANNED
    ]


def test_tenant_isolation_for_reads_lists_and_events(store):
    _, snapshot, event = make_initial()
    store.create(ALICE, snapshot, event, consent=True)
    assert store.get(BOB, snapshot.task.task_id) is None
    assert store.list_tasks(BOB) == ()
    assert store.events(BOB, snapshot.task.task_id) == ()
    assert store.get(ALICE, snapshot.task.task_id) is not None


def test_stale_version_cannot_overwrite_newer_state(store):
    lifecycle, initial, created = make_initial()
    store.create(ALICE, initial, created, consent=True)
    planned = lifecycle.transition(initial.task.task_id, TaskStatus.PLANNED, expected_version=0)
    store.save_transition(ALICE, planned, lifecycle.events[-1], expected_version=0, consent=True)
    cancelled = TaskSnapshot(
        type(initial.task)(initial.task.description, initial.task.task_id,
                           TaskStatus.CANCELLED, initial.task.created_at),
        initial.requires_approval, 1, initial.updated_at,
    )
    fake_event = TaskLifecycleEvent(initial.task.task_id, TaskStatus.DRAFT,
                                    TaskStatus.CANCELLED, 1, initial.updated_at, "stale")
    with pytest.raises(TaskStateConflict):
        store.save_transition(ALICE, cancelled, fake_event, expected_version=0, consent=True)
    assert store.get(ALICE, initial.task.task_id).snapshot.task.status is TaskStatus.PLANNED


def test_transition_write_rolls_back_if_event_insert_fails(store, monkeypatch):
    lifecycle, initial, created = make_initial()
    store.create(ALICE, initial, created, consent=True)
    planned = lifecycle.transition(initial.task.task_id, TaskStatus.PLANNED, expected_version=0)
    event = lifecycle.events[-1]
    with sqlite3.connect(store.database_path) as db:
        db.execute("""CREATE TRIGGER reject_event BEFORE INSERT ON task_state_events
                      WHEN NEW.version = 1 BEGIN SELECT RAISE(ABORT, 'blocked'); END""")
    with pytest.raises(sqlite3.IntegrityError):
        store.save_transition(ALICE, planned, event, expected_version=0, consent=True)
    recovered = store.get(ALICE, initial.task.task_id)
    assert recovered.snapshot.version == 0
    assert recovered.snapshot.task.status is TaskStatus.DRAFT


def test_duplicate_initial_state_is_rejected_without_overwrite(store):
    _, snapshot, event = make_initial()
    store.create(ALICE, snapshot, event, consent=True)
    with pytest.raises(sqlite3.IntegrityError):
        store.create(ALICE, snapshot, event, consent=True)
    assert store.get(ALICE, snapshot.task.task_id).snapshot.version == 0


def test_list_is_bounded_and_ordered(store):
    lifecycle = TaskLifecycle()
    first = lifecycle.create("first task")
    second = lifecycle.create("second task")
    store.create(ALICE, first, lifecycle.events[-2], consent=True)
    store.create(ALICE, second, lifecycle.events[-1], consent=True)
    assert len(store.list_tasks(ALICE, limit=1)) == 1
    with pytest.raises(ValueError):
        store.list_tasks(ALICE, limit=501)


def test_secret_like_task_content_is_rejected(store):
    lifecycle = TaskLifecycle()
    snapshot = lifecycle.create("password=hunter2")
    with pytest.raises(ValueError):
        store.create(ALICE, snapshot, lifecycle.events[-1], consent=True)


def test_database_permissions_are_private(store):
    path = Path(store.database_path)
    if os.name == "posix":
        assert path.stat().st_mode & 0o777 == 0o600
        assert path.parent.stat().st_mode & 0o777 == 0o700


def test_concurrent_store_instances_use_compare_and_swap(tmp_path):
    path = tmp_path / "private" / "tasks.sqlite3"
    store_one = SQLiteTaskStateStore(path)
    store_two = SQLiteTaskStateStore(path)
    lifecycle, initial, created = make_initial()
    store_one.create(ALICE, initial, created, consent=True)
    planned = lifecycle.transition(initial.task.task_id, TaskStatus.PLANNED, expected_version=0)
    event = lifecycle.events[-1]
    barrier = threading.Barrier(2)
    outcomes = []

    def attempt(target):
        barrier.wait()
        try:
            target.save_transition(ALICE, planned, event, expected_version=0, consent=True)
            outcomes.append("saved")
        except TaskStateConflict:
            outcomes.append("conflict")

    threads = [threading.Thread(target=attempt, args=(target,))
               for target in (store_one, store_two)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(outcomes) == ["conflict", "saved"]
    assert store_one.get(ALICE, initial.task.task_id).snapshot.version == 1


def test_event_source_must_match_current_persisted_status(store):
    lifecycle, initial, created = make_initial()
    store.create(ALICE, initial, created, consent=True)
    planned = lifecycle.transition(initial.task.task_id, TaskStatus.PLANNED, expected_version=0)
    mismatched = TaskLifecycleEvent(
        initial.task.task_id, TaskStatus.CANCELLED, TaskStatus.PLANNED,
        1, lifecycle.events[-1].occurred_at, "mismatched_source",
    )
    with pytest.raises(ValueError, match="source status"):
        store.save_transition(ALICE, planned, mismatched, expected_version=0, consent=True)
    assert store.get(ALICE, initial.task.task_id).snapshot.version == 0


def test_missing_task_transition_raises_not_found(store):
    lifecycle, initial, _ = make_initial()
    planned = lifecycle.transition(initial.task.task_id, TaskStatus.PLANNED, expected_version=0)
    with pytest.raises(TaskStateNotFound):
        store.save_transition(
            ALICE, planned, lifecycle.events[-1], expected_version=0, consent=True
        )
