"""Crash-safe, fail-closed browser job journal.

A job ID is consumed exactly once. After a process restart, accepted/running
jobs are marked interrupted and are NEVER automatically replayed: a caller
cannot know whether a remote side effect happened before the crash.
"""
from __future__ import annotations

import hashlib
import json
from contextlib import contextmanager
import os
import re
from pathlib import Path
import sqlite3
import stat
import tempfile
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
            with self._database() as db:
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
                db.execute("""CREATE TABLE IF NOT EXISTS browser_job_history (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL,
                    state TEXT NOT NULL,
                    occurred_at REAL NOT NULL,
                    outcome_code TEXT,
                    previous_hash TEXT NOT NULL CHECK(length(previous_hash)=64),
                    entry_hash TEXT NOT NULL UNIQUE CHECK(length(entry_hash)=64)
                )""")
                db.execute("""CREATE TRIGGER IF NOT EXISTS browser_history_no_update
                    BEFORE UPDATE ON browser_job_history
                    BEGIN SELECT RAISE(ABORT, 'action history is append-only'); END""")
                db.execute("""CREATE TRIGGER IF NOT EXISTS browser_history_no_delete
                    BEFORE DELETE ON browser_job_history
                    BEGIN SELECT RAISE(ABORT, 'action history is append-only'); END""")
            os.chmod(path, 0o600)
        except (OSError, sqlite3.Error) as exc:
            raise RecoveryLedgerError("recovery ledger initialization failed") from exc

    def _connect(self):
        # Explicit transaction control makes SELECT-then-UPDATE transitions
        # serializable across threads and independent processes.
        db = sqlite3.connect(self.path, timeout=5.0, isolation_level=None)
        db.execute("PRAGMA trusted_schema=OFF")
        db.execute("PRAGMA synchronous=FULL")
        db.execute("PRAGMA busy_timeout=5000")
        return db

    @contextmanager
    def _database(self):
        """Commit/rollback and always close the SQLite connection."""
        db = self._connect()
        try:
            with db:
                db.execute("BEGIN IMMEDIATE")
                yield db
        finally:
            db.close()

    def _now(self) -> float:
        value = self._clock()
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise RecoveryLedgerError("recovery clock returned an invalid timestamp")
        return float(value)

    @staticmethod
    def _validate_job(job_id: str, request_digest: str) -> None:
        if type(job_id) is not str or not 8 <= len(job_id) <= 128 or any(ord(c) < 33 for c in job_id):
            raise ValueError("job ID is invalid")
        if type(request_digest) is not str or not re.fullmatch(r"[0-9a-f]{64}", request_digest):
            raise ValueError("request digest must be a canonical lowercase SHA-256 hex digest")

    @staticmethod
    def _history_entry_hash(previous_hash: str, job_id: str, state: str,
                            occurred_at: float, outcome_code: str | None) -> str:
        payload = {
            "job_id": job_id,
            "state": state,
            "occurred_at": occurred_at,
            "outcome_code": outcome_code,
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                               ensure_ascii=True, allow_nan=False).encode("ascii")
        return hashlib.sha256(previous_hash.encode("ascii") + b"\n" + canonical).hexdigest()

    def _append_history(self, db: sqlite3.Connection, job_id: str, state: str,
                        occurred_at: float, outcome_code: str | None) -> None:
        row = db.execute(
            "SELECT entry_hash FROM browser_job_history ORDER BY sequence DESC LIMIT 1"
        ).fetchone()
        previous_hash = row[0] if row else "0" * 64
        entry_hash = self._history_entry_hash(
            previous_hash, job_id, state, occurred_at, outcome_code
        )
        db.execute(
            """INSERT INTO browser_job_history
               (job_id,state,occurred_at,outcome_code,previous_hash,entry_hash)
               VALUES(?,?,?,?,?,?)""",
            (job_id, state, occurred_at, outcome_code, previous_hash, entry_hash),
        )

    @staticmethod
    def _verify_history_connection(db: sqlite3.Connection) -> str:
        previous_hash = "0" * 64
        rows = db.execute(
            """SELECT sequence,job_id,state,occurred_at,outcome_code,
                      previous_hash,entry_hash
               FROM browser_job_history ORDER BY sequence"""
        ).fetchall()
        for expected_sequence, row in enumerate(rows, start=1):
            sequence, job_id, state, occurred_at, outcome_code, stored_previous, stored_hash = row
            if sequence != expected_sequence or stored_previous != previous_hash:
                raise RecoveryLedgerError("action history sequence or hash chain is broken")
            expected_hash = SQLiteBrowserRecoveryLedger._history_entry_hash(
                previous_hash, job_id, state, occurred_at, outcome_code
            )
            if not isinstance(stored_hash, str) or not __import__("hmac").compare_digest(
                expected_hash, stored_hash
            ):
                raise RecoveryLedgerError("action history integrity verification failed")
            previous_hash = stored_hash
        return previous_hash

    def verify_history(self) -> str:
        """Verify the append-only action-state history and return its head hash."""
        try:
            with self._database() as db:
                return self._verify_history_connection(db)
        except RecoveryLedgerError:
            raise
        except sqlite3.Error as exc:
            raise RecoveryLedgerError("action history could not be verified") from exc

    def list_history(self, job_id: str | None = None) -> list[dict[str, object]]:
        """Return payload-free history records; never expose session IDs or request bodies."""
        if job_id is not None and (type(job_id) is not str or not 8 <= len(job_id) <= 128):
            raise ValueError("job ID is invalid")
        try:
            self.verify_history()
            with self._database() as db:
                if job_id is None:
                    rows = db.execute(
                        """SELECT sequence,job_id,state,occurred_at,outcome_code,entry_hash
                           FROM browser_job_history ORDER BY sequence"""
                    ).fetchall()
                else:
                    rows = db.execute(
                        """SELECT sequence,job_id,state,occurred_at,outcome_code,entry_hash
                           FROM browser_job_history WHERE job_id=? ORDER BY sequence""",
                        (job_id,),
                    ).fetchall()
            return [
                dict(zip(("sequence","job_id","state","occurred_at","outcome_code","entry_hash"), row))
                for row in rows
            ]
        except sqlite3.Error as exc:
            raise RecoveryLedgerError("action history could not be read") from exc

    def backup_to(self, destination: str | os.PathLike[str]) -> Path:
        """Create a consistent, owner-private SQLite backup without overwriting files."""
        target = Path(destination)
        if not target.is_absolute() or target.parent != self.path.parent:
            raise ValueError("backup must use an absolute path in the private ledger directory")
        parent = target.parent.lstat()
        if stat.S_ISLNK(parent.st_mode) or not stat.S_ISDIR(parent.st_mode) or stat.S_IMODE(parent.st_mode) & 0o077:
            raise ValueError("backup directory must remain owner-private")
        try:
            fd = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0), 0o600)
        except FileExistsError as exc:
            raise RecoveryLedgerError("backup destination already exists; refusing overwrite") from exc
        os.close(fd)
        try:
            # sqlite3.Connection.backup() manages its own read snapshot. Do not
            # wrap the source in _database()/BEGIN IMMEDIATE: a write transaction
            # on the source can make the online-backup API wait indefinitely.
            source = self._connect()
            destination_db = sqlite3.connect(target, isolation_level=None)
            try:
                source.backup(destination_db)
                result = destination_db.execute("PRAGMA integrity_check").fetchone()
                if not result or result[0] != "ok":
                    raise RecoveryLedgerError("backup SQLite integrity check failed")
                self._verify_history_connection(destination_db)
            finally:
                destination_db.close()
                source.close()
            os.chmod(target, 0o600)
            return target
        except Exception:
            try:
                target.unlink()
            except OSError:
                pass
            raise

    def restore_from(self, backup: str | os.PathLike[str]) -> None:
        """Restore only a structurally valid backup; replace atomically after verification."""
        source_path = Path(backup)
        if not source_path.is_absolute() or source_path == self.path or source_path.parent != self.path.parent:
            raise ValueError("restore source must be a separate absolute file in the private ledger directory")
        info = source_path.lstat()
        if (stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode)
                or info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) & 0o077):
            raise ValueError("restore source must be an owner-owned private regular file")
        fd, temporary_name = tempfile.mkstemp(prefix=".apaa-restore-", dir=self.path.parent)
        os.close(fd)
        temporary_path = Path(temporary_name)
        try:
            source_db = sqlite3.connect(f"file:{source_path}?mode=ro", uri=True)
            destination_db = sqlite3.connect(temporary_path, isolation_level=None)
            try:
                source_db.backup(destination_db)
                result = destination_db.execute("PRAGMA integrity_check").fetchone()
                if not result or result[0] != "ok":
                    raise RecoveryLedgerError("restore source failed SQLite integrity check")
                self._verify_history_connection(destination_db)
                required = {"browser_jobs", "browser_control", "browser_job_history"}
                present = {row[0] for row in destination_db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()}
                if not required.issubset(present):
                    raise RecoveryLedgerError("restore source is missing required ledger tables")
            finally:
                source_db.close()
                destination_db.close()
            os.chmod(temporary_path, 0o600)
            os.replace(temporary_path, self.path)
            os.chmod(self.path, 0o600)
        except Exception:
            try:
                temporary_path.unlink()
            except OSError:
                pass
            raise

    def dispatch_blocked(self) -> bool:
        try:
            with self._database() as db:
                row = db.execute("SELECT value FROM browser_control WHERE key='dispatch_blocked'").fetchone()
                return bool(row and row[0] == "1")
        except sqlite3.Error as exc:
            raise RecoveryLedgerError("dispatch latch could not be read; refusing dispatch") from exc

    def latch_dispatch_block(self, reason_code: str = "audit_integrity_failure") -> None:
        if type(reason_code) is not str or not reason_code or len(reason_code) > 64:
            raise ValueError("dispatch block reason code is invalid")
        try:
            with self._lock, self._database() as db:
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
            with self._lock, self._database() as db:
                self._verify_history_connection(db)
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
            with self._lock, self._database() as db:
                self._verify_history_connection(db)
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
                self._append_history(db, job_id, state, now, outcome_code)
        except RecoveryLedgerError:
            raise
        except sqlite3.Error as exc:
            raise RecoveryLedgerError("browser job state could not be persisted") from exc

    def recover_interrupted(self) -> list[str]:
        """Mark pre-crash jobs interrupted; never re-dispatch them automatically."""
        now = self._now()
        try:
            with self._lock, self._database() as db:
                self._verify_history_connection(db)
                rows = db.execute(
                    "SELECT job_id FROM browser_jobs WHERE state IN ('accepted','running','cancel_requested')"
                ).fetchall()
                ids = [row[0] for row in rows]
                for (job_id,) in rows:
                    db.execute(
                        "UPDATE browser_jobs SET state='interrupted', updated_at=?, "
                        "outcome_code='process_restart' WHERE job_id=?",
                        (now, job_id),
                    )
                    self._append_history(db, job_id, "interrupted", now, "process_restart")
                return ids
        except sqlite3.Error as exc:
            raise RecoveryLedgerError("crash recovery scan failed; dispatch must remain disabled") from exc

    def get(self, job_id: str) -> dict[str, object] | None:
        try:
            with self._database() as db:
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
