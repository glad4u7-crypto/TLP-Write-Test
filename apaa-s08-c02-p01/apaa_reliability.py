"""APAA P06 reliability primitives: atomic claims and cooperative execution budgets."""
from __future__ import annotations
import sqlite3, threading, time
from typing import Any

class ExecutionBudget:
    """Cooperative deadline and cancellation token; handlers must call check()."""
    def __init__(self, timeout_seconds: float, *, max_steps: int = 10000):
        if timeout_seconds <= 0 or max_steps < 1:
            raise ValueError("positive timeout and max_steps required")
        self.deadline = time.monotonic() + timeout_seconds
        self.max_steps = max_steps
        self.steps = 0
        self.cancelled = threading.Event()

    def cancel(self) -> None:
        self.cancelled.set()

    def consume(self, steps: int = 1) -> None:
        if steps < 0:
            raise ValueError("steps cannot be negative")
        self.steps += steps
        self.check()

    def check(self) -> None:
        if self.cancelled.is_set():
            raise RuntimeError("execution cancelled")
        if time.monotonic() >= self.deadline:
            raise TimeoutError("cooperative execution deadline exceeded")
        if self.steps > self.max_steps:
            raise RuntimeError("execution step budget exceeded")

class AtomicSQLiteClaimer:
    """Atomic queue claim helper for an existing APAA tasks table."""
    def __init__(self, database_path: str):
        self.path = database_path
        self.lock = threading.RLock()

    def claim_next(self, worker_id: str, lease_seconds: float = 30) -> dict[str, Any] | None:
        if not worker_id or lease_seconds <= 0:
            raise ValueError("worker_id and positive lease required")
        with self.lock, sqlite3.connect(self.path, timeout=10, isolation_level=None) as db:
            db.row_factory = sqlite3.Row
            db.execute("BEGIN IMMEDIATE")
            try:
                row = db.execute(
                    "SELECT * FROM tasks WHERE status='queued' ORDER BY created_at,task_id LIMIT 1"
                ).fetchone()
                if row is None:
                    db.commit()
                    return None
                now = time.time()
                changed = db.execute(
                    """UPDATE tasks SET status='running',lease_owner=?,lease_expires_at=?,
                       attempts=attempts+1,updated_at=? WHERE task_id=? AND status='queued'""",
                    (worker_id, now + lease_seconds, now, row["task_id"]),
                ).rowcount
                if changed != 1:
                    raise RuntimeError("atomic claim lost; retry safely")
                claimed = dict(db.execute("SELECT * FROM tasks WHERE task_id=?", (row["task_id"],)).fetchone())
                db.commit()
                return claimed
            except Exception:
                db.rollback()
                raise

def validate_result_size(result: Any, max_bytes: int = 65536) -> None:
    import json
    if max_bytes < 1:
        raise ValueError("max_bytes must be positive")
    try:
        encoded = json.dumps(result, allow_nan=False, separators=(",", ":")).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError("handler result must be finite JSON data") from exc
    if len(encoded) > max_bytes:
        raise ValueError("handler result exceeds configured size limit")
