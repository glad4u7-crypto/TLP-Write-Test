"""Single-worker sequential task runner.

This controller coordinates existing queue, lifecycle and trusted gateway
contracts. It does not register handlers, create approvals, or perform I/O
outside the explicitly registered ExecutionGateway handler.
"""
from collections.abc import Callable, Mapping
from dataclasses import dataclass
import threading
from typing import Any

from core.approvals import ApprovalReceipt
from core.execution import ExecutionGateway, ExecutionResult
from core.models import TaskStatus
from core.storage import TenantKey
from core.task_lifecycle import TaskLifecycle, TaskLifecycleError, TaskSnapshot
from core.task_queue import TaskQueue, TaskQueueEmptyError


@dataclass(frozen=True)
class TaskExecutionRequest:
    """Trusted-controller description resolved for one queued task."""

    action: str
    payload: Mapping[str, Any]
    tenant: TenantKey | None = None


@dataclass(frozen=True)
class SequentialExecutionResult:
    task_id: str
    status: TaskStatus
    reason: str
    gateway_result: ExecutionResult | None = None
    snapshot: TaskSnapshot | None = None


RequestResolver = Callable[[str], TaskExecutionRequest]
ApprovalProvider = Callable[[str, str, Mapping[str, Any]], ApprovalReceipt | None]


class SequentialTaskExecutor:
    """Run at most one queued task at a time, in queue order.

    A process-wide dispatch lock prevents a second executor instance from
    bypassing the sequential guarantee for a shared runtime.

    The resolver and approval provider are trusted application-controller
    dependencies. They must never be supplied by planner/model output or task
    descriptions. Mutating work must already be in AWAITING_APPROVAL and must
    obtain a fresh receipt from the trusted UI before gateway dispatch.
    """

    _global_run_lock = threading.Lock()

    def __init__(
        self,
        queue: TaskQueue,
        lifecycle: TaskLifecycle,
        gateway: ExecutionGateway,
    ) -> None:
        if not isinstance(queue, TaskQueue):
            raise TypeError("queue must be a TaskQueue.")
        if not isinstance(lifecycle, TaskLifecycle):
            raise TypeError("lifecycle must be a TaskLifecycle.")
        if not isinstance(gateway, ExecutionGateway):
            raise TypeError("gateway must be an ExecutionGateway.")
        self._queue = queue
        self._lifecycle = lifecycle
        self._gateway = gateway
        self._run_lock = self._global_run_lock

    def run_next(
        self,
        resolve_request: RequestResolver,
        *,
        request_approval: ApprovalProvider | None = None,
    ) -> SequentialExecutionResult | None:
        """Execute the next queued task, returning None when the queue is empty."""
        if not callable(resolve_request):
            raise TypeError("resolve_request must be a trusted callable.")
        if request_approval is not None and not callable(request_approval):
            raise TypeError("request_approval must be a trusted callable.")

        # Lock covers dequeue through terminal state update: concurrent callers
        # cannot overlap handlers or reorder task completion.
        with self._run_lock:
            try:
                entry = self._queue.dequeue()
            except TaskQueueEmptyError:
                return None

            task_id = entry.task_id
            try:
                snapshot = self._lifecycle.get(task_id)
                if snapshot.task.status not in (
                    TaskStatus.PLANNED, TaskStatus.AWAITING_APPROVAL
                ):
                    return SequentialExecutionResult(
                        task_id, snapshot.task.status,
                        "Task is not in a runnable lifecycle state.", snapshot=snapshot,
                    )

                request = resolve_request(task_id)
                if not isinstance(request, TaskExecutionRequest):
                    raise TypeError("Resolver must return TaskExecutionRequest.")
                if not isinstance(request.action, str) or not request.action.strip():
                    raise ValueError("Resolved action must be non-empty text.")
                if not isinstance(request.payload, Mapping):
                    raise TypeError("Resolved payload must be a mapping.")

                receipt = None
                if snapshot.requires_approval:
                    if snapshot.task.status is not TaskStatus.AWAITING_APPROVAL:
                        raise PermissionError(
                            "Approval-required task must be awaiting approval before execution."
                        )
                    if request_approval is None:
                        raise PermissionError("Trusted UI approval is required.")
                    receipt = request_approval(task_id, request.action, request.payload)
                    if not isinstance(receipt, ApprovalReceipt):
                        raise PermissionError("Trusted UI did not provide a valid approval receipt.")
                elif snapshot.task.status is not TaskStatus.PLANNED:
                    raise TaskLifecycleError(
                        "A task not requiring approval must be planned before execution."
                    )

                running = self._lifecycle.transition(
                    task_id, TaskStatus.RUNNING,
                    expected_version=snapshot.version,
                    reason="sequential_execution_started",
                    approval_recorded=bool(receipt),
                )
                gateway_result = self._gateway.execute(
                    request.action,
                    request.payload,
                    approval_receipt=receipt,
                    tenant=request.tenant,
                )
                target = (
                    TaskStatus.SUCCEEDED if gateway_result.executed
                    else TaskStatus.FAILED
                )
                finished = self._lifecycle.transition(
                    task_id, target,
                    expected_version=running.version,
                    reason="sequential_execution_finished",
                )
                return SequentialExecutionResult(
                    task_id, target, gateway_result.reason,
                    gateway_result=gateway_result, snapshot=finished,
                )
            except Exception as exc:
                # Fail closed: no automatic retry and no handler fallback.
                try:
                    latest = self._lifecycle.get(task_id)
                    if latest.task.status in (
                        TaskStatus.PLANNED, TaskStatus.AWAITING_APPROVAL,
                        TaskStatus.RUNNING,
                    ):
                        latest = self._lifecycle.transition(
                            task_id, TaskStatus.FAILED,
                            expected_version=latest.version,
                            reason="sequential_execution_blocked",
                        )
                    else:
                        latest = self._lifecycle.get(task_id)
                except Exception:
                    latest = None
                return SequentialExecutionResult(
                    task_id, TaskStatus.FAILED,
                    f"Task blocked: {type(exc).__name__}.",
                    snapshot=latest,
                )
