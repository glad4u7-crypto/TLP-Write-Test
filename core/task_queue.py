"""Bounded, in-memory task queue. Queueing never executes a task."""
from dataclasses import dataclass
from datetime import datetime, timezone
import heapq
import threading

MAX_TASK_ID_LENGTH = 128
MAX_QUEUE_CAPACITY = 10000
MAX_PRIORITY = 100
MIN_PRIORITY = -100


class TaskQueueError(ValueError):
    """Base class for queue contract violations."""


class DuplicateTaskError(TaskQueueError):
    """Raised when a task ID is already waiting in this queue."""


class QueueFullError(TaskQueueError):
    """Raised rather than silently dropping work when capacity is reached."""


class TaskQueueEmptyError(TaskQueueError):
    """Raised when dequeue is called on an empty queue."""


@dataclass(frozen=True)
class QueueEntry:
    task_id: str
    priority: int
    sequence: int
    enqueued_at: str


class TaskQueue:
    """Thread-safe bounded priority queue with FIFO ordering for ties.

    Larger priority values are dequeued first. Equal priorities preserve
    enqueue order. The queue stores identifiers only: it does not own task
    state, call handlers, grant permissions, persist data, or execute work.
    """

    def __init__(self, capacity: int = 100) -> None:
        if type(capacity) is not int or not 1 <= capacity <= MAX_QUEUE_CAPACITY:
            raise ValueError(f"capacity must be an integer from 1 to {MAX_QUEUE_CAPACITY}.")
        self._capacity = capacity
        self._heap: list[tuple[int, int, str]] = []
        self._entries: dict[str, QueueEntry] = {}
        self._sequence = 0
        self._lock = threading.RLock()

    @property
    def capacity(self) -> int:
        return self._capacity

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)

    def __bool__(self) -> bool:
        return len(self) > 0

    def enqueue(self, task_id: str, *, priority: int = 0) -> QueueEntry:
        if not isinstance(task_id, str):
            raise TypeError("task_id must be text.")
        if not task_id or task_id != task_id.strip() or len(task_id) > MAX_TASK_ID_LENGTH:
            raise ValueError("task_id must be non-empty, trimmed and at most 128 characters.")
        if type(priority) is not int or not MIN_PRIORITY <= priority <= MAX_PRIORITY:
            raise ValueError("priority must be an integer from -100 to 100.")

        with self._lock:
            if task_id in self._entries:
                raise DuplicateTaskError(f"Task {task_id!r} is already queued.")
            if len(self._entries) >= self._capacity:
                raise QueueFullError("Task queue is full; no queued task was dropped.")
            self._sequence += 1
            entry = QueueEntry(
                task_id, priority, self._sequence,
                datetime.now(timezone.utc).isoformat(),
            )
            self._entries[task_id] = entry
            heapq.heappush(self._heap, (-priority, entry.sequence, task_id))
            return entry

    def peek(self) -> QueueEntry:
        with self._lock:
            self._discard_stale_head()
            if not self._heap:
                raise TaskQueueEmptyError("Task queue is empty.")
            return self._entries[self._heap[0][2]]

    def dequeue(self) -> QueueEntry:
        with self._lock:
            self._discard_stale_head()
            if not self._heap:
                raise TaskQueueEmptyError("Task queue is empty.")
            _, _, task_id = heapq.heappop(self._heap)
            return self._entries.pop(task_id)

    def remove(self, task_id: str) -> QueueEntry:
        if not isinstance(task_id, str) or not task_id:
            raise ValueError("A valid task_id is required.")
        with self._lock:
            try:
                return self._entries.pop(task_id)
            except KeyError as exc:
                raise KeyError(task_id) from exc

    def snapshot(self) -> tuple[QueueEntry, ...]:
        with self._lock:
            return tuple(sorted(
                self._entries.values(),
                key=lambda item: (-item.priority, item.sequence),
            ))

    def _discard_stale_head(self) -> None:
        while self._heap and self._heap[0][2] not in self._entries:
            heapq.heappop(self._heap)
