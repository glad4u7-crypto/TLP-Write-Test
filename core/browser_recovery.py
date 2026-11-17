"""Crash-safe, fail-closed browser job journal.

A job ID is consumed exactly once. After a process restart, accepted/running
jobs are marked interrupted and are NEVER automatically replayed: a caller
cannot know whether a remote side effect happened before the crash.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import sqlite3
import stat
import threading
import time
from typing import Final


class RecoveryLedgerError(RuntimeError):
    """The durable browser recovery journal cannot safely proceed."""


class DuplicateBrowserJob(RecoveryLedgerError):
    """A job ID has already been accepted, regardless of its terminal state."""


class BrowserDispatchBlocked(RecoveryLedgerError):
    """A durable fail-closed dispatch latch is active."""


_ACTIVE: Final = ("accepted", "running", "cancel_requested")
_TERMINAL: Final = ("completed", "failed", "cancelled", "timed_out", "interrupted")


class SQLiteBrowserRecoveryLedger:
    """Owner-private SQLite journal with atomic job-ID claims and crash recovery."""

    def __init__(self, database_path: str | os.PathLike[str], *, clock=time.time) -> None:
        path = Path(database_path)
        if not path.is_absolute() or path.name in {"", ".", ".."}:
            raise ValueError("recovery ledger path must be an absolute file path")
        if not callable(clock):
            raise TypeError("clock must be callable")
        if path.parent.is_symlink() or not path.parent.is_dir():
            raise ValueError("recovery ledger parent must be an existing real directory")
        parent = path.parent.stat()
        if (not stat.S_ISDIR(parent.st_mode) or parent.st_uid != os.geteuid()
                or stat.S_IMODE(parent.st_mode) & 0o077):
            raise ValueError("recovery ledger parent must be owner-owned and mode 0700")
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0), 0o600)
        except FileExistsError:
            fd = None
        except OSError as exc:
            raise RecoveryLedgerError("recovery ledger could not be securely created") from exc
        if fd is not None:
            os.close(fd)
        try:
            info = os.lstat(path)
            if (stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode)
                    or info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) & 0o077):
                raise ValueError("recovery ledger must be an owner-private regular file")
        except OSError as exc:
            raise RecoveryLedgerError("recovery ledger could not be inspected safely") from exc
        self.path = path
        self._clock = clock
        self._lock = threading.RLock()
        try:
            with self._connect() as db:
                db.execute("""CREATE TABLE IF NOT EXISTS browser_jobs (
                    job_id TEXT PRIMARY KEY,
                    request_digest TEXT NOT NULL CHECK(length(request_digest)=64),
                    state TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    session_id TEXT,
                    outcome_code TEXT
                )""")
                db.execute("""CREATE TABLE IF NOT EXISTS browser_control (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at REAL NOT NULL
                )""")
            os.chmod(path, 0o600)
        except (OSError, sqlite3.Error) as exc:
            raise RecoveryLedgerError("recovery ledger initialization failed") from exc

    def _connect(self):
        db = sqlite3.connect(self.path, timeout=5.0, isolation_level="IMMEDIATE")
        db.execute("PRAGMA trusted_schema=OFF")
        db.execute("PRAGMA synchronous=FULL")
        db.execute("PRAGMA journal_mode=DELETE")
        return db

    def _now(self) -> float:
        value = self._clock()
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise RecoveryLedgerError("recovery clock returned an invalid timestamp")
        return float(value)

    @staticmethod
    def _validate_job(job_id: str, request_digest: str) -> None:
        if type(job_id) is not str or not 8 <= len(job_id) <= 128 or any(ord(c) < 33 for c in job_id):
            raise ValueError("job ID is invalid")
        if type(request_digest) is not str or len(request_digest) != 64:
            raise ValueError("request digest must be a SHA-256 hex digest")
        try:
            bytes.fromhex(request_digest)
        except ValueError as exc:
            raise ValueError("request digest must be hexadecimal") from exc

    def dispatch_blocked(self) -> bool:
        try:
            with self._connect() as db:
                row = db.execute("SELECT value FROM browser_control WHERE key='dispatch_blocked'").fetchone()
                return bool(row and row[0] == "1")
        except sqlite3.Error as exc:
            raise RecoveryLedgerError("dispatch latch could not be read; refusing dispatch") from exc

    def latch_dispatch_block(self, reason_code: str = "audit_integrity_failure") -> None:
        if type(reason_code) is not str or not reason_code or len(reason_code) > 64:
            raise ValueError("dispatch block reason code is invalid")
        try:
            with self._lock, self._connect() as db:
                db.execute(
                    "INSERT INTO browser_control(key,value,updated_at) VALUES('dispatch_blocked','1',?) "
                    "ON CONFLICT(key) DO UPDATE SET value='1', updated_at=excluded.updated_at",
                    (self._now(),),
                )
                db.execute(
                    "INSERT INTO browser_control(key,value,updated_at) VALUES('dispatch_block_reason',?,?) "
                    "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
                    (reason_code, self._now()),
                )
        except sqlite3.Error as exc:
            raise RecoveryLedgerError("could not persist dispatch block; refusing dispatch") from exc

    def claim(self, job_id: str, request_digest: str, *, session_id: str) -> None:
        """Atomically reserve an ID before any worker dispatch or external action."""
        self._validate_job(job_id, request_digest)
        if type(session_id) is not str or len(session_id) < 16:
            raise ValueError("session ID is invalid")
        now = self._now()
        try:
            with self._lock, self._connect() as db:
                blocked = db.execute(
                    "SELECT value FROM browser_control WHERE key='dispatch_blocked'"
                ).fetchone()
                if blocked and blocked[0] == "1":
                    raise BrowserDispatchBlocked("browser dispatch is durably blocked")
                try:
                    db.execute(
                        "INSERT INTO browser_jobs(job_id,request_digest,state,created_at,updated_at,session_id) "
                        "VALUES(?,?, 'accepted', ?, ?, ?)",
                        (job_id, request_digest, now, now, session_id),
                    )
                except sqlite3.IntegrityError as exc:
                    row = db.execute(
                        "SELECT request_digest,state FROM browser_jobs WHERE job_id=?", (job_id,)
                    ).fetchone()
                    if row:
                        raise DuplicateBrowserJob("job ID was already consumed; automatic replay is forbidden") from exc
                    raise RecoveryLedgerError("job claim violated a ledger constraint") from exc
        except (DuplicateBrowserJob, BrowserDispatchBlocked, RecoveryLedgerError):
            raise
        except sqlite3.Error as exc:
            raise RecoveryLedgerError("atomic job claim failed; dispatch refused") from exc

    def transition(self, job_id: str, state: str, *, outcome_code: str | None = None) -> None:
        """Perform a one-way state transition; terminal states cannot be reopened."""
        if state not in {"running", *_TERMINAL, "cancel_requested"}:
            raise ValueError("unsupported browser job state")
        if outcome_code is not None and (
            type(outcome_code) is not str or len(outcome_code) > 64
            or any(ord(c) < 33 for c in outcome_code)
        ):
            raise ValueError("outcome code must be a short non-sensitive code")
        now = self._now()
        try:
            with self._lock, self._connect() as db:
                row = db.execute("SELECT state FROM browser_jobs WHERE job_id=?", (job_id,)).fetchone()
                if row is None:
                    raise RecoveryLedgerError("job does not exist in the recovery ledger")
                current = row[0]
                allowed = {
                    "accepted": {"running", "failed", "cancelled", "interrupted"},
                    "running": {"cancel_requested", "completed", "failed", "cancelled", "timed_out", "interrupted"},
                    "cancel_requested": {"cancelled", "failed", "interrupted"},
                }
                if state == current and state in _TERMINAL:
                    return
                if state not in allowed.get(current, set()):
                    raise RecoveryLedgerError("invalid or terminal browser job state transition")
                db.execute(
                    "UPDATE browser_jobs SET state=?, updated_at=?, outcome_code=? WHERE job_id=?",
                    (state, now, outcome_code, job_id),
                )
        except RecoveryLedgerError:
            raise
        except sqlite3.Error as exc:
            raise RecoveryLedgerError("browser job state could not be persisted") from exc

    def recover_interrupted(self) -> list[str]:
        """Mark pre-crash jobs interrupted; never re-dispatch them automatically."""
        now = self._now()
        try:
            with self._lock, self._connect() as db:
                rows = db.execute(
                    "SELECT job_id FROM browser_jobs WHERE state IN ('accepted','running','cancel_requested')"
                ).fetchall()
                ids = [row[0] for row in rows]
                db.execute(
                    "UPDATE browser_jobs SET state='interrupted', updated_at=?, "
                    "outcome_code='process_restart' WHERE state IN ('accepted','running','cancel_requested')",
                    (now,),
                )
                return ids
        except sqlite3.Error as exc:
            raise RecoveryLedgerError("crash recovery scan failed; dispatch must remain disabled") from exc

    def get(self, job_id: str) -> dict[str, object] | None:
        try:
            with self._connect() as db:
                row = db.execute(
                    "SELECT job_id,request_digest,state,created_at,updated_at,session_id,outcome_code "
                    "FROM browser_jobs WHERE job_id=?", (job_id,)
                ).fetchone()
            if row is None:
                return None
            return dict(zip(
                ("job_id","request_digest","state","created_at","updated_at","session_id","outcome_code"),
                row,
            ))
        except sqlite3.Error as exc:
            raise RecoveryLedgerError("recovery state could not be read") from exc
