import threading
import time

from core.approvals import ApprovalAuthority
from core.execution import ExecutionGateway
from core.models import TaskStatus
from core.sequential_executor import (
    SequentialTaskExecutor,
    TaskExecutionRequest,
)
from core.task_lifecycle import TaskLifecycle
from core.task_queue import TaskQueue


def _planned(lifecycle, description, *, requires_approval=False):
    item = lifecycle.create(description, requires_approval=requires_approval)
    return lifecycle.transition(
        item.task.task_id, TaskStatus.PLANNED, expected_version=item.version
    )


def test_runs_tasks_one_at_a_time_in_queue_order():
    lifecycle = TaskLifecycle()
    first = _planned(lifecycle, "read first")
    second = _planned(lifecycle, "read second")
    queue = TaskQueue()
    queue.enqueue(first.task.task_id)
    queue.enqueue(second.task.task_id)
    active = {"count": 0, "maximum": 0}
    calls = []

    def handler(payload):
        active["count"] += 1
        active["maximum"] = max(active["maximum"], active["count"])
        time.sleep(0.02)
        calls.append(payload["item"])
        active["count"] -= 1
        return "ok"

    gateway = ExecutionGateway({"inspect_repository": handler})
    executor = SequentialTaskExecutor(queue, lifecycle, gateway)
    resolver = lambda task_id: TaskExecutionRequest(
        "inspect_repository", {"item": "first" if task_id == first.task.task_id else "second"}
    )

    results = [executor.run_next(resolver), executor.run_next(resolver)]

    assert [result.status for result in results] == [
        TaskStatus.SUCCEEDED, TaskStatus.SUCCEEDED
    ]
    assert calls == ["first", "second"]
    assert active["maximum"] == 1
    assert executor.run_next(resolver) is None


def test_approval_required_task_needs_trusted_receipt_before_gateway_dispatch():
    lifecycle = TaskLifecycle()
    item = _planned(lifecycle, "write a document", requires_approval=True)
    awaiting = lifecycle.transition(
        item.task.task_id, TaskStatus.AWAITING_APPROVAL, expected_version=item.version
    )
    queue = TaskQueue()
    queue.enqueue(awaiting.task.task_id)
    authority = ApprovalAuthority()
    calls = []
    payload = {"document_id": "doc-1", "content": "approved content"}
    gateway = ExecutionGateway(
        {"write_file": lambda data: calls.append(data) or "saved"},
        approval_authority=authority,
    )
    executor = SequentialTaskExecutor(queue, lifecycle, gateway)
    resolver = lambda _: TaskExecutionRequest("write_file", payload)

    blocked = executor.run_next(resolver)
    assert blocked.status is TaskStatus.FAILED
    assert calls == []

    # A new task and fresh approval demonstrate the permitted route.
    next_item = _planned(lifecycle, "write another document", requires_approval=True)
    next_item = lifecycle.transition(
        next_item.task.task_id, TaskStatus.AWAITING_APPROVAL,
        expected_version=next_item.version,
    )
    queue.enqueue(next_item.task.task_id)
    receipt = authority.issue("write_file", payload)
    approved = executor.run_next(
        resolver,
        request_approval=lambda *_: receipt,
    )
    assert approved.status is TaskStatus.SUCCEEDED
    assert calls == [payload]


def test_invalid_task_state_is_not_dispatched():
    lifecycle = TaskLifecycle()
    item = lifecycle.create("still draft")
    queue = TaskQueue()
    queue.enqueue(item.task.task_id)
    calls = []
    executor = SequentialTaskExecutor(
        queue, lifecycle,
        ExecutionGateway({"inspect_repository": lambda payload: calls.append(payload)}),
    )

    result = executor.run_next(
        lambda _: TaskExecutionRequest("inspect_repository", {})
    )

    assert result.status is TaskStatus.DRAFT
    assert calls == []


def test_failed_gateway_result_marks_task_failed_without_retry():
    lifecycle = TaskLifecycle()
    item = _planned(lifecycle, "unregistered action")
    queue = TaskQueue()
    queue.enqueue(item.task.task_id)
    executor = SequentialTaskExecutor(queue, lifecycle, ExecutionGateway())

    result = executor.run_next(
        lambda _: TaskExecutionRequest("inspect_repository", {})
    )

    assert result.status is TaskStatus.FAILED
    assert lifecycle.get(item.task.task_id).task.status is TaskStatus.FAILED
    assert queue.snapshot() == ()


def test_concurrent_run_next_calls_do_not_overlap_handlers():
    lifecycle = TaskLifecycle()
    items = [_planned(lifecycle, f"task {i}") for i in range(4)]
    queue = TaskQueue()
    for item in items:
        queue.enqueue(item.task.task_id)
    active = {"count": 0, "max": 0}
    lock = threading.Lock()

    def handler(_):
        with lock:
            active["count"] += 1
            active["max"] = max(active["max"], active["count"])
        time.sleep(0.02)
        with lock:
            active["count"] -= 1
        return True

    executor = SequentialTaskExecutor(
        queue, lifecycle, ExecutionGateway({"inspect_repository": handler})
    )
    resolver = lambda _: TaskExecutionRequest("inspect_repository", {})

    threads = [
        threading.Thread(target=executor.run_next, args=(resolver,))
        for _ in range(4)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert active["max"] == 1
    assert all(lifecycle.get(item.task.task_id).task.status is TaskStatus.SUCCEEDED for item in items)
    assert queue.snapshot() == ()
