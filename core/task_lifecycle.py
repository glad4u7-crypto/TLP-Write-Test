"""In-process task lifecycle state machine.

This module records lifecycle state only. It does not dispatch actions, grant
permissions, persist state across process restarts, or replace ExecutionGateway.
"""
from dataclasses import dataclass, replace
from datetime import datetime, timezone
import threading
import uuid

from core.models import Task, TaskStatus


MAX_DESCRIPTION_LENGTH = 4000
MAX_REASON_LENGTH = 500


@dataclass(frozen=True)
class TaskLifecycleEvent:
    task_id: str
    from_status: TaskStatus | None
    to_status: TaskStatus
    version: int
    occurred_at: str
    reason: str


@dataclass(frozen=True)
class TaskSnapshot:
    task: Task
    requires_approval: bool
    version: int
    updated_at: str


class TaskLifecycleError(ValueError):
    """Raised when a requested lifecycle transition is invalid."""


class TaskNotFoundError(KeyError):
    """Raised when a lifecycle operation references an unknown task."""


class TaskVersionConflict(TaskLifecycleError):
    """Raised when a caller attempts to update a stale task snapshot."""


_ALLOWED_TRANSITIONS = {
    TaskStatus.DRAFT: frozenset({TaskStatus.PLANNED, TaskStatus.CANCELLED}),
    TaskStatus.PLANNED: frozenset({
        TaskStatus.AWAITING_APPROVAL, TaskStatus.RUNNING,
        TaskStatus.FAILED, TaskStatus.CANCELLED,
    }),
    TaskStatus.AWAITING_APPROVAL: frozenset({
        TaskStatus.RUNNING, TaskStatus.FAILED, TaskStatus.CANCELLED,
    }),
    TaskStatus.RUNNING: frozenset({
        TaskStatus.SUCCEEDED, TaskStatus.FAILED, TaskStatus.CANCELLED,
    }),
    TaskStatus.SUCCEEDED: frozenset(),
    TaskStatus.FAILED: frozenset(),
    TaskStatus.CANCELLED: frozenset(),
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class TaskLifecycle:
    """Thread-safe, process-local lifecycle registry with optimistic versions.

    A transition to RUNNING from AWAITING_APPROVAL requires the caller to
    record that approval was obtained. This flag is lifecycle bookkeeping,
    not a security credential: the trusted controller must still obtain and
    consume an action/payload-bound ApprovalReceipt through ExecutionGateway.
    """

    def __init__(self) -> None:
        self._tasks: dict[str, TaskSnapshot] = {}
        self._events: list[TaskLifecycleEvent] = []
        self._lock = threading.RLock()

    def create(self, description: str, *, requires_approval: bool = False) -> TaskSnapshot:
        if not isinstance(description, str):
            raise TypeError("Task description must be text.")
        normalized = " ".join(description.split())
        if not normalized:
            raise ValueError("Task description must not be empty.")
        if len(normalized) > MAX_DESCRIPTION_LENGTH:
            raise ValueError(
                f"Task description exceeds the {MAX_DESCRIPTION_LENGTH}-character limit."
            )
        if type(requires_approval) is not bool:
            raise TypeError("requires_approval must be a boolean.")

        with self._lock:
            task_id = uuid.uuid4().hex
            now = _now()
            task = Task(
                description=normalized,
                task_id=task_id,
                status=TaskStatus.DRAFT,
                created_at=now,
            )
            snapshot = TaskSnapshot(task, requires_approval, 0, now)
            self._tasks[task_id] = snapshot
            self._events.append(TaskLifecycleEvent(
                task_id, None, TaskStatus.DRAFT, 0, now, "task_created"
            ))
            return snapshot

    def get(self, task_id: str) -> TaskSnapshot:
        if not isinstance(task_id, str) or not task_id:
            raise ValueError("A valid task ID is required.")
        with self._lock:
            try:
                return self._tasks[task_id]
            except KeyError as exc:
                raise TaskNotFoundError(task_id) from exc

    def list_tasks(self) -> tuple[TaskSnapshot, ...]:
        with self._lock:
            return tuple(sorted(
                self._tasks.values(),
                key=lambda item: (item.task.created_at, item.task.task_id),
            ))

    @property
    def events(self) -> tuple[TaskLifecycleEvent, ...]:
        with self._lock:
            return tuple(self._events)

    def transition(
        self,
        task_id: str,
        target: TaskStatus,
        *,
        expected_version: int,
        reason: str = "",
        approval_recorded: bool = False,
    ) -> TaskSnapshot:
        if not isinstance(target, TaskStatus):
            raise TypeError("target must be a TaskStatus value.")
        if type(expected_version) is not int or expected_version < 0:
            raise ValueError("expected_version must be a non-negative integer.")
        if not isinstance(reason, str) or len(reason) > MAX_REASON_LENGTH:
            raise ValueError("reason must be text of at most 500 characters.")
        if type(approval_recorded) is not bool:
            raise TypeError("approval_recorded must be a boolean.")

        with self._lock:
            current = self.get(task_id)
            if current.version != expected_version:
                raise TaskVersionConflict("Task changed; reload its latest version before retrying.")
            source = current.task.status
            if target not in _ALLOWED_TRANSITIONS[source]:
                raise TaskLifecycleError(
                    f"Transition from {source.value} to {target.value} is not allowed."
                )
            if target is TaskStatus.RUNNING:
                if current.requires_approval and source is not TaskStatus.AWAITING_APPROVAL:
                    raise TaskLifecycleError(
                        "Tasks requiring approval must enter awaiting_approval before running."
                    )
                if source is TaskStatus.AWAITING_APPROVAL and not approval_recorded:
                    raise TaskLifecycleError(
                        "An explicit approval must be recorded before entering running."
                    )

            now = _now()
            updated_task = replace(current.task, status=target)
            updated = TaskSnapshot(
                updated_task, current.requires_approval, current.version + 1, now
            )
            self._tasks[task_id] = updated
            self._events.append(TaskLifecycleEvent(
                task_id, source, target, updated.version, now,
                reason.strip() or "status_transition",
            ))
            return updated
