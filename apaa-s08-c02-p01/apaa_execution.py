"""APAA S08-C02-P01: guarded, sequential, auditable task execution."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
import sqlite3
import threading
import time
import uuid
from typing import Any, Callable


class TaskStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    BLOCKED = "blocked"


_ALLOWED = {
    TaskStatus.QUEUED: {TaskStatus.RUNNING, TaskStatus.BLOCKED},
    TaskStatus.RUNNING: {TaskStatus.SUCCEEDED, TaskStatus.FAILED},
    TaskStatus.SUCCEEDED: set(),
    TaskStatus.FAILED: set(),
    TaskStatus.BLOCKED: set(),
}


class ExecutionDenied(RuntimeError):
    pass


@dataclass(frozen=True)
class Task:
    task_id: str
    action: str
    payload: dict[str, Any]
    permission_granted: bool = False
    user_consented: bool = False

    @classmethod
    def create(cls, action: str, payload: dict[str, Any], *,
               permission_granted: bool = False,
               user_consented: bool = False) -> "Task":
        if not action or not isinstance(action, str):
            raise ValueError("action must be a non-empty string")
        if not isinstance(payload, dict):
            raise ValueError("payload must be a dictionary")
        return cls(str(uuid.uuid4()), action, payload,
                   permission_granted, user_consented)


class StateStore:
    """Small durable SQLite journal; no task payload is executed by the store."""
    def __init__(self, path: str = ":memory:") -> None:
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        with self._db:
            self._db.execute("""CREATE TABLE IF NOT EXISTS tasks (
                task_id TEXT PRIMARY KEY, action TEXT NOT NULL,
                payload TEXT NOT NULL, status TEXT NOT NULL,
                result TEXT, error TEXT, created_at REAL NOT NULL,
                updated_at REAL NOT NULL)""")

    def add(self, task: Task) -> None:
        now = time.time()
        with self._lock, self._db:
            self._db.execute(
                "INSERT INTO tasks(task_id,action,payload,status,created_at,updated_at) VALUES(?,?,?,?,?,?)",
                (task.task_id, task.action, json.dumps(task.payload, sort_keys=True),
                 TaskStatus.QUEUED.value, now, now))

    def transition(self, task_id: str, target: TaskStatus, *,
                   result: Any = None, error: str | None = None) -> None:
        with self._lock, self._db:
            row = self._db.execute(
                "SELECT status FROM tasks WHERE task_id=?", (task_id,)).fetchone()
            if row is None:
                raise KeyError(task_id)
            current = TaskStatus(row["status"])
            if target not in _ALLOWED[current]:
                raise ValueError(f"invalid transition: {current.value} -> {target.value}")
            self._db.execute(
                "UPDATE tasks SET status=?, result=?, error=?, updated_at=? WHERE task_id=?",
                (target.value, json.dumps(result, sort_keys=True, default=str)
                 if result is not None else None, error, time.time(), task_id))

    def get(self, task_id: str) -> dict[str, Any]:
        with self._lock:
            row = self._db.execute("SELECT * FROM tasks WHERE task_id=?",
                                   (task_id,)).fetchone()
            if row is None:
                raise KeyError(task_id)
            return dict(row)

    def close(self) -> None:
        with self._lock:
            self._db.close()


class ExecutionEngine:
    """FIFO, single-worker executor with deny-by-default policy."""
    def __init__(self, store: StateStore | None = None) -> None:
        self.store = store or StateStore()
        self._handlers: dict[str, Callable[[dict[str, Any]], Any]] = {}
        self._queue: list[Task] = []
        self._queue_lock = threading.RLock()
        self._run_lock = threading.Lock()

    def register(self, action: str, handler: Callable[[dict[str, Any]], Any]) -> None:
        if not action or not callable(handler):
            raise ValueError("a named action and callable handler are required")
        with self._queue_lock:
            if action in self._handlers:
                raise ValueError(f"handler already registered: {action}")
            self._handlers[action] = handler

    def submit(self, task: Task) -> str:
        with self._queue_lock:
            self.store.add(task)
            self._queue.append(task)
        return task.task_id

    def run_next(self) -> str | None:
        # Non-blocking acquisition prevents concurrent callers executing together.
        if not self._run_lock.acquire(blocking=False):
            raise RuntimeError("an execution is already in progress")
        try:
            with self._queue_lock:
                if not self._queue:
                    return None
                task = self._queue.pop(0)

            handler = self._handlers.get(task.action)
            if not task.permission_granted or not task.user_consented or handler is None:
                self.store.transition(task.task_id, TaskStatus.BLOCKED,
                    error="permission, consent, or registered handler missing")
                return task.task_id

            self.store.transition(task.task_id, TaskStatus.RUNNING)
            try:
                output = handler(dict(task.payload))
            except Exception as exc:
                self.store.transition(task.task_id, TaskStatus.FAILED,
                                      error=f"{type(exc).__name__}: {exc}")
            else:
                self.store.transition(task.task_id, TaskStatus.SUCCEEDED,
                                      result=output)
            return task.task_id
        finally:
            self._run_lock.release()

    def run_all(self) -> list[str]:
        completed = []
        while True:
            task_id = self.run_next()
            if task_id is None:
                return completed
            completed.append(task_id)
