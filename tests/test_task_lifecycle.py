import pytest

from core.models import TaskStatus
from core.task_lifecycle import (
    TaskLifecycle,
    TaskLifecycleError,
    TaskNotFoundError,
    TaskVersionConflict,
)


def test_create_normalizes_description_and_records_draft_event():
    lifecycle = TaskLifecycle()
    snapshot = lifecycle.create("  collect   public information  ")

    assert snapshot.task.description == "collect public information"
    assert snapshot.task.status is TaskStatus.DRAFT
    assert snapshot.version == 0
    assert len(lifecycle.events) == 1
    assert lifecycle.events[0].from_status is None
    assert lifecycle.events[0].to_status is TaskStatus.DRAFT


@pytest.mark.parametrize("description", ["", "  ", "\n\t"])
def test_create_rejects_empty_description(description):
    with pytest.raises(ValueError):
        TaskLifecycle().create(description)


def test_create_enforces_description_limit_and_boolean_flag():
    with pytest.raises(ValueError):
        TaskLifecycle().create("x" * 4001)
    with pytest.raises(TypeError):
        TaskLifecycle().create("task", requires_approval=1)


def test_happy_path_lifecycle_for_read_only_task():
    lifecycle = TaskLifecycle()
    item = lifecycle.create("summarize a report")
    item = lifecycle.transition(item.task.task_id, TaskStatus.PLANNED, expected_version=0)
    item = lifecycle.transition(item.task.task_id, TaskStatus.RUNNING, expected_version=1)
    item = lifecycle.transition(item.task.task_id, TaskStatus.SUCCEEDED, expected_version=2)

    assert item.task.status is TaskStatus.SUCCEEDED
    assert item.version == 3
    assert [event.to_status for event in lifecycle.events] == [
        TaskStatus.DRAFT, TaskStatus.PLANNED, TaskStatus.RUNNING, TaskStatus.SUCCEEDED
    ]


def test_mutating_task_must_wait_for_approval_before_running():
    lifecycle = TaskLifecycle()
    item = lifecycle.create("write a document", requires_approval=True)
    planned = lifecycle.transition(item.task.task_id, TaskStatus.PLANNED, expected_version=0)

    with pytest.raises(TaskLifecycleError, match="awaiting_approval"):
        lifecycle.transition(item.task.task_id, TaskStatus.RUNNING, expected_version=1)

    awaiting = lifecycle.transition(
        item.task.task_id, TaskStatus.AWAITING_APPROVAL, expected_version=1
    )
    with pytest.raises(TaskLifecycleError, match="explicit approval"):
        lifecycle.transition(item.task.task_id, TaskStatus.RUNNING, expected_version=2)

    running = lifecycle.transition(
        item.task.task_id, TaskStatus.RUNNING, expected_version=2,
        approval_recorded=True,
    )
    assert running.task.status is TaskStatus.RUNNING
    assert running.version == 3


def test_approval_flag_does_not_skip_gateway_security_boundary():
    lifecycle = TaskLifecycle()
    item = lifecycle.create("change a file", requires_approval=True)
    lifecycle.transition(item.task.task_id, TaskStatus.PLANNED, expected_version=0)
    lifecycle.transition(
        item.task.task_id, TaskStatus.AWAITING_APPROVAL, expected_version=1
    )
    # The lifecycle only records state. It has no handler and performs no I/O.
    result = lifecycle.transition(
        item.task.task_id, TaskStatus.RUNNING, expected_version=2,
        approval_recorded=True,
    )
    assert result.task.status is TaskStatus.RUNNING
    assert not hasattr(lifecycle, "execute")


def test_invalid_transition_and_terminal_state_are_rejected():
    lifecycle = TaskLifecycle()
    item = lifecycle.create("inspect a file")
    with pytest.raises(TaskLifecycleError):
        lifecycle.transition(item.task.task_id, TaskStatus.SUCCEEDED, expected_version=0)

    item = lifecycle.transition(item.task.task_id, TaskStatus.CANCELLED, expected_version=0)
    with pytest.raises(TaskLifecycleError):
        lifecycle.transition(item.task.task_id, TaskStatus.PLANNED, expected_version=1)


def test_failed_task_is_terminal_until_retry_recovery_part_is_implemented():
    lifecycle = TaskLifecycle()
    item = lifecycle.create("inspect a file")
    item = lifecycle.transition(item.task.task_id, TaskStatus.PLANNED, expected_version=0)
    item = lifecycle.transition(item.task.task_id, TaskStatus.FAILED, expected_version=1)
    with pytest.raises(TaskLifecycleError):
        lifecycle.transition(item.task.task_id, TaskStatus.PLANNED, expected_version=2)


def test_optimistic_version_prevents_stale_update():
    lifecycle = TaskLifecycle()
    item = lifecycle.create("inspect a file")
    lifecycle.transition(item.task.task_id, TaskStatus.PLANNED, expected_version=0)
    with pytest.raises(TaskVersionConflict):
        lifecycle.transition(item.task.task_id, TaskStatus.CANCELLED, expected_version=0)


def test_unknown_task_and_bad_inputs_are_rejected():
    lifecycle = TaskLifecycle()
    with pytest.raises(TaskNotFoundError):
        lifecycle.get("missing")
    with pytest.raises(ValueError):
        lifecycle.get("")
    item = lifecycle.create("inspect")
    with pytest.raises(ValueError):
        lifecycle.transition(item.task.task_id, TaskStatus.PLANNED, expected_version=-1)
    with pytest.raises(TypeError):
        lifecycle.transition(item.task.task_id, "planned", expected_version=0)


def test_snapshots_and_event_history_are_immutable():
    lifecycle = TaskLifecycle()
    item = lifecycle.create("inspect")
    snapshots = lifecycle.list_tasks()
    events = lifecycle.events

    assert isinstance(snapshots, tuple)
    assert isinstance(events, tuple)
    with pytest.raises(AttributeError):
        events.append("tamper")
    with pytest.raises(Exception):
        item.task.status = TaskStatus.RUNNING
