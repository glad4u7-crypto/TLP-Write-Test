"""Tenant-scoped durable task state store.

This adapter persists lifecycle snapshots and their corresponding events
atomically. It does not execute tasks, grant permissions, or infer consent.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sqlite3
import stat

from core.models import Task, TaskStatus
from core.storage import TenantKey
from core.task_lifecycle import TaskLifecycleEvent, TaskSnapshot


_SECRET_PATTERN = re.compile(
    r"(?i)(-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|"
    r"\b(?:api[_ -]?key|access[_ -]?token|password|secret)\s*[:=]\s*\S+|"
    r"\bBearer\s+[A-Za-z0-9._~+/=-]{12,})"
)
MAX_TASK_DESCRIPTION = 4000
MAX_EVENT_REASON = 500


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class StoredTaskState:
    snapshot: TaskSnapshot
    tenant: TenantKey


class TaskStateConflict(RuntimeError):
    """Raised when a task's persisted version differs from expected_version."""


class TaskStateNotFound(KeyError):
    """Raised when a tenant-scoped task state does not exist."""


class SQLiteTaskStateStore:
    """Private SQLite store with issuer+subject isolation and optimistic writes.

    All personal task-state writes require consent=True. A task's state and
    event are committed in one transaction; stale updates cannot overwrite a
    newer version. Descriptions/reasons resembling credentials are rejected.
    """

    def __init__(self, database_path: str | Path, *, timeout: float = 5.0) -> None:
        raw_path = str(database_path)
        if raw_path == ":memory:":
            raise ValueError("A filesystem-backed database is required for durable task state.")
        if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or not 0 < timeout <= 60:
            raise ValueError("timeout must be greater than 0 and at most 60 seconds.")
        self._path = Path(raw_path).absolute()
        self._timeout = float(timeout)
        self._secure_path(create_parent=True)
        self._initialize()
        self._secure_path(create_parent=False)

    @property
    def database_path(self) -> str:
        return str(self._path)

    def _secure_path(self, *, create_parent: bool) -> None:
        for parent in self._path.parents:
            try:
                if stat.S_ISLNK(parent.lstat().st_mode):
                    raise ValueError("Database parent path must not contain symlinks.")
            except FileNotFoundError:
                continue
        if create_parent:
            self._path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if not stat.S_ISDIR(self._path.parent.stat().st_mode):
            raise ValueError("Database parent must be a directory.")
        if os.name == "posix" and self._path.parent.stat().st_mode & 0o077:
            raise ValueError("Database directory must be owner-only (0700).")
        try:
            metadata = self._path.lstat()
        except FileNotFoundError:
            flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0)
            try:
                fd = os.open(self._path, flags, 0o600)
            except FileExistsError:
                metadata = self._path.lstat()
            else:
                os.close(fd)
                metadata = self._path.lstat()
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
            raise ValueError("Database must be a regular, non-symlink file.")
        os.chmod(self._path, 0o600)

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(str(self._path), timeout=self._timeout, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute(f"PRAGMA busy_timeout = {int(self._timeout * 1000)}")
        db.execute("PRAGMA foreign_keys = ON")
        return db

    def _initialize(self) -> None:
        statements = [
            """CREATE TABLE IF NOT EXISTS task_states (
                issuer TEXT NOT NULL, subject TEXT NOT NULL, task_id TEXT NOT NULL,
                description TEXT NOT NULL, status TEXT NOT NULL, requires_approval INTEGER NOT NULL
                    CHECK (requires_approval IN (0,1)), version INTEGER NOT NULL CHECK (version >= 0),
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                PRIMARY KEY (issuer, subject, task_id))""",
            """CREATE INDEX IF NOT EXISTS idx_task_states_tenant_updated
                ON task_states(issuer, subject, updated_at)""",
            """CREATE TABLE IF NOT EXISTS task_state_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                issuer TEXT NOT NULL, subject TEXT NOT NULL, task_id TEXT NOT NULL,
                from_status TEXT, to_status TEXT NOT NULL, version INTEGER NOT NULL,
                occurred_at TEXT NOT NULL, reason TEXT NOT NULL,
                UNIQUE(issuer, subject, task_id, version),
                FOREIGN KEY(issuer, subject, task_id)
                    REFERENCES task_states(issuer, subject, task_id) ON DELETE CASCADE)""",
            """CREATE INDEX IF NOT EXISTS idx_task_events_tenant_task
                ON task_state_events(issuer, subject, task_id, version)""",
        ]
        with closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                for statement in statements:
                    db.execute(statement)
                db.commit()
            except Exception:
                db.rollback()
                raise

    @staticmethod
    def _tenant(tenant: TenantKey) -> tuple[str, str]:
        if not isinstance(tenant, TenantKey):
            raise TypeError("A validated TenantKey is required.")
        return tenant.issuer, tenant.subject

    @staticmethod
    def _consent(consent: bool) -> None:
        if consent is not True:
            raise PermissionError("Explicit consent=True is required to persist task state.")

    @staticmethod
    def _validate(snapshot: TaskSnapshot, event: TaskLifecycleEvent) -> None:
        if not isinstance(snapshot, TaskSnapshot) or not isinstance(event, TaskLifecycleEvent):
            raise TypeError("A TaskSnapshot and TaskLifecycleEvent are required.")
        task = snapshot.task
        if not isinstance(task, Task) or not isinstance(task.status, TaskStatus):
            raise TypeError("Task snapshot contains an invalid task.")
        if not isinstance(task.task_id, str) or not task.task_id or len(task.task_id) > 128:
            raise ValueError("Task ID must contain 1 to 128 characters.")
        if not isinstance(task.description, str) or not task.description.strip() or len(task.description) > MAX_TASK_DESCRIPTION:
            raise ValueError("Task description is invalid or too long.")
        if _SECRET_PATTERN.search(task.description):
            raise ValueError("Credential-like task descriptions cannot be persisted.")
        if type(snapshot.requires_approval) is not bool:
            raise TypeError("requires_approval must be boolean.")
        if type(snapshot.version) is not int or snapshot.version < 0:
            raise ValueError("Task version must be a non-negative integer.")
        if event.task_id != task.task_id or event.version != snapshot.version or event.to_status is not task.status:
            raise ValueError("Snapshot and event identity/version/status must match.")
        if not isinstance(event.reason, str) or len(event.reason) > MAX_EVENT_REASON:
            raise ValueError("Event reason is invalid or too long.")
        if _SECRET_PATTERN.search(event.reason):
            raise ValueError("Credential-like event reasons cannot be persisted.")
        if event.from_status is not None and not isinstance(event.from_status, TaskStatus):
            raise TypeError("Event source status is invalid.")

    @staticmethod
    def _snapshot(row: sqlite3.Row) -> TaskSnapshot:
        task = Task(row["description"], row["task_id"], TaskStatus(row["status"]), row["created_at"])
        return TaskSnapshot(task, bool(row["requires_approval"]), row["version"], row["updated_at"])

    def create(self, tenant: TenantKey, snapshot: TaskSnapshot, event: TaskLifecycleEvent,
               *, consent: bool = False) -> StoredTaskState:
        self._consent(consent)
        self._validate(snapshot, event)
        if (snapshot.version != 0 or event.from_status is not None
                or event.to_status is not TaskStatus.DRAFT):
            raise ValueError("Initial task state must be DRAFT version 0 with no source status.")
        issuer, subject = self._tenant(tenant)
        with closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                db.execute(
                    "INSERT INTO task_states VALUES (?,?,?,?,?,?,?,?,?)",
                    (issuer, subject, snapshot.task.task_id, snapshot.task.description,
                     snapshot.task.status.value, int(snapshot.requires_approval), 0,
                     snapshot.task.created_at, snapshot.updated_at),
                )
                db.execute(
                    """INSERT INTO task_state_events
                    (issuer,subject,task_id,from_status,to_status,version,occurred_at,reason)
                    VALUES (?,?,?,?,?,?,?,?)""",
                    (issuer, subject, event.task_id, None, event.to_status.value,
                     event.version, event.occurred_at, event.reason),
                )
                db.commit()
            except Exception:
                db.rollback()
                raise
        return StoredTaskState(snapshot, tenant)

    def save_transition(self, tenant: TenantKey, snapshot: TaskSnapshot,
                        event: TaskLifecycleEvent, *, expected_version: int,
                        consent: bool = False) -> StoredTaskState:
        self._consent(consent)
        self._validate(snapshot, event)
        if type(expected_version) is not int or expected_version < 0:
            raise ValueError("expected_version must be a non-negative integer.")
        if snapshot.version != expected_version + 1 or event.from_status is None:
            raise ValueError("Transition version/source status is inconsistent.")
        issuer, subject = self._tenant(tenant)
        with closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                current = db.execute(
                    """SELECT status, version FROM task_states
                       WHERE issuer=? AND subject=? AND task_id=?""",
                    (issuer, subject, snapshot.task.task_id),
                ).fetchone()
                if current is None:
                    raise TaskStateNotFound(snapshot.task.task_id)
                if current["version"] != expected_version:
                    raise TaskStateConflict("Persisted task version changed; reload before retrying.")
                if event.from_status.value != current["status"]:
                    raise ValueError("Transition event source status does not match persisted state.")
                cur = db.execute(
                    """UPDATE task_states SET description=?, status=?, requires_approval=?,
                       version=?, updated_at=? WHERE issuer=? AND subject=? AND task_id=?
                       AND version=?""
                    (snapshot.task.description, snapshot.task.status.value,
                     int(snapshot.requires_approval), snapshot.version, snapshot.updated_at,
                     issuer, subject, snapshot.task.task_id, expected_version),
                )
                if cur.rowcount != 1:
                    raise TaskStateConflict("Persisted task version changed; reload before retrying.")
                db.execute(
                    """INSERT INTO task_state_events
                    (issuer,subject,task_id,from_status,to_status,version,occurred_at,reason)
                    VALUES (?,?,?,?,?,?,?,?)""",
                    (issuer, subject, event.task_id, event.from_status.value,
                     event.to_status.value, event.version, event.occurred_at, event.reason),
                )
                db.commit()
            except Exception:
                db.rollback()
                raise
        return StoredTaskState(snapshot, tenant)

    def get(self, tenant: TenantKey, task_id: str) -> StoredTaskState | None:
        issuer, subject = self._tenant(tenant)
        if not isinstance(task_id, str) or not task_id:
            raise ValueError("A valid task ID is required.")
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT * FROM task_states WHERE issuer=? AND subject=? AND task_id=?",
                (issuer, subject, task_id),
            ).fetchone()
        return StoredTaskState(self._snapshot(row), tenant) if row else None

    def list_tasks(self, tenant: TenantKey, *, limit: int = 100) -> tuple[StoredTaskState, ...]:
        issuer, subject = self._tenant(tenant)
        if type(limit) is not int or not 1 <= limit <= 500:
            raise ValueError("limit must be an integer from 1 to 500.")
        with closing(self._connect()) as db:
            rows = db.execute(
                """SELECT * FROM task_states WHERE issuer=? AND subject=?
                   ORDER BY updated_at DESC, task_id LIMIT ?""", (issuer, subject, limit)
            ).fetchall()
        return tuple(StoredTaskState(self._snapshot(row), tenant) for row in rows)

    def events(self, tenant: TenantKey, task_id: str) -> tuple[TaskLifecycleEvent, ...]:
        issuer, subject = self._tenant(tenant)
        if not isinstance(task_id, str) or not task_id:
            raise ValueError("A valid task ID is required.")
        with closing(self._connect()) as db:
            rows = db.execute(
                """SELECT * FROM task_state_events WHERE issuer=? AND subject=? AND task_id=?
                   ORDER BY version""", (issuer, subject, task_id)
            ).fetchall()
        return tuple(TaskLifecycleEvent(
            row["task_id"], TaskStatus(row["from_status"]) if row["from_status"] else None,
            TaskStatus(row["to_status"]), row["version"], row["occurred_at"], row["reason"]
        ) for row in rows)
