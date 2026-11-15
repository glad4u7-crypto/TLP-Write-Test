import threading

import pytest

from core.task_queue import (
    DuplicateTaskError,
    QueueFullError,
    TaskQueue,
    TaskQueueEmptyError,
)


def test_fifo_order_for_equal_priority():
    queue = TaskQueue()
    for task_id in ("a", "b", "c"):
        queue.enqueue(task_id)
    assert [queue.dequeue().task_id for _ in range(3)] == ["a", "b", "c"]


def test_higher_priority_is_dequeued_first_and_ties_are_fifo():
    queue = TaskQueue()
    queue.enqueue("low", priority=-2)
    queue.enqueue("high-1", priority=5)
    queue.enqueue("middle", priority=1)
    queue.enqueue("high-2", priority=5)
    assert [queue.dequeue().task_id for _ in range(4)] == [
        "high-1", "high-2", "middle", "low"
    ]


def test_duplicate_id_is_rejected_while_queued():
    queue = TaskQueue()
    queue.enqueue("same")
    with pytest.raises(DuplicateTaskError):
        queue.enqueue("same")
    assert len(queue) == 1


def test_capacity_overflow_rejects_without_dropping_existing_items():
    queue = TaskQueue(capacity=2)
    queue.enqueue("one")
    queue.enqueue("two")
    with pytest.raises(QueueFullError):
        queue.enqueue("three")
    assert [entry.task_id for entry in queue.snapshot()] == ["one", "two"]


def test_peek_does_not_remove_and_remove_skips_stale_heap_entries():
    queue = TaskQueue()
    queue.enqueue("first")
    queue.enqueue("second", priority=1)
    assert queue.peek().task_id == "second"
    assert len(queue) == 2
    assert queue.remove("second").task_id == "second"
    assert queue.dequeue().task_id == "first"
    assert len(queue) == 0


def test_dequeue_and_peek_empty_raise_clear_error():
    queue = TaskQueue()
    with pytest.raises(TaskQueueEmptyError):
        queue.dequeue()
    with pytest.raises(TaskQueueEmptyError):
        queue.peek()


@pytest.mark.parametrize("capacity", [0, -1, 1.5, True, 10001])
def test_invalid_capacity_rejected(capacity):
    with pytest.raises(ValueError):
        TaskQueue(capacity=capacity)


@pytest.mark.parametrize("task_id", ["", "  ", " padded ", "x" * 129, None])
def test_invalid_task_id_rejected(task_id):
    with pytest.raises((TypeError, ValueError)):
        TaskQueue().enqueue(task_id)


@pytest.mark.parametrize("priority", [-101, 101, 1.2, True, "high"])
def test_invalid_priority_rejected(priority):
    with pytest.raises(ValueError):
        TaskQueue().enqueue("task", priority=priority)


def test_remove_unknown_id_raises_key_error():
    with pytest.raises(KeyError):
        TaskQueue().remove("missing")


def test_snapshot_is_immutable_and_sorted_without_mutating_queue():
    queue = TaskQueue()
    queue.enqueue("normal")
    queue.enqueue("urgent", priority=10)
    view = queue.snapshot()
    assert isinstance(view, tuple)
    assert [item.task_id for item in view] == ["urgent", "normal"]
    with pytest.raises(AttributeError):
        view.append("tamper")
    assert len(queue) == 2


def test_concurrent_enqueue_keeps_all_unique_tasks():
    queue = TaskQueue(capacity=200)
    threads = [
        threading.Thread(target=queue.enqueue, args=(f"task-{i}",))
        for i in range(100)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(queue) == 100
    assert len({entry.task_id for entry in queue.snapshot()}) == 100


def test_queue_has_no_execution_or_io_surface():
    queue = TaskQueue()
    assert not hasattr(queue, "execute")
    assert not hasattr(queue, "dispatch")
