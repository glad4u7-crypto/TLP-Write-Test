"""Durable, atomic one-time challenge consumption for host attestation.

The ledger stores only challenge digests and consumption timestamps. It is an
owner-controlled local SQLite file; callers must protect its parent directory
and back it up as part of the host security state.
"""
from __future__ import annotations

import hashlib
import os
from contextlib import contextmanager
from pathlib import Path
import re
import sqlite3
import stat
import threading
import time


class ChallengeLedgerError(RuntimeError):
    """The replay ledger could not safely record a challenge."""


class SQLiteChallengeLedger:
    """Atomically consume a 256-bit challenge across threads and processes."""

    def __init__(self, database_path: str | os.PathLike[str], *, timeout_seconds: float = 5.0):
        raw = Path(database_path)
        if not raw.is_absolute() or raw.name in {"", ".", ".."}:
            raise ValueError("challenge ledger path must be an absolute file path")
        if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float)) or not 0.1 <= timeout_seconds <= 30:
            raise ValueError("challenge ledger timeout is invalid")
        self.path = raw
        self.timeout_seconds = float(timeout_seconds)
        self._lock = threading.RLock()
        if not self.path.parent.is_dir() or self.path.parent.is_symlink():
            raise ValueError("challenge ledger parent must be an existing non-symlink directory")
        parent_info = self.path.parent.stat()
        if (not stat.S_ISDIR(parent_info.st_mode) or parent_info.st_uid != os.geteuid()
                or stat.S_IMODE(parent_info.st_mode) & 0o077):
            raise ValueError("challenge ledger parent must be owner-owned and private (0700)")
        # Create the database with private permissions from its first inode;
        # chmod-after-SQLite-create would leave a brief world-readable window.
        try:
            fd = os.open(
                self.path,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0),
                0o600,
            )
        except FileExistsError:
            fd = None
        except OSError as exc:
            raise ChallengeLedgerError("challenge ledger file could not be securely created") from exc
        if fd is not None:
            os.close(fd)
        try:
            info = os.lstat(self.path)
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                    or stat.S_IMODE(info.st_mode) & 0o077):
                raise ValueError("challenge ledger must be an owner-owned private regular file")
        except OSError as exc:
            raise ChallengeLedgerError("challenge ledger file could not be safely inspected") from exc
        try:
            with self._database() as db:
                db.execute(
                    "CREATE TABLE IF NOT EXISTS consumed_challenges ("
                    "challenge TEXT PRIMARY KEY CHECK(length(challenge)=64), "
                    "consumed_at INTEGER NOT NULL)"
                )
            os.chmod(self.path, 0o600)
        except (OSError, sqlite3.Error) as exc:
            raise ChallengeLedgerError("challenge ledger initialization failed") from exc

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(
            self.path, timeout=self.timeout_seconds, isolation_level="IMMEDIATE"
        )
        db.execute("PRAGMA trusted_schema=OFF")
        db.execute("PRAGMA synchronous=FULL")
        return db

    @contextmanager
    def _database(self):
        db = self._connect()
        try:
            with db:
                yield db
        finally:
            db.close()

    def consume(self, challenge: str, *, now: int | None = None) -> bool:
        if type(challenge) is not str or not re.fullmatch(r"[0-9a-f]{64}", challenge):
            raise ValueError("challenge must be a lowercase 256-bit hexadecimal value")
        timestamp = int(time.time()) if now is None else now
        if type(timestamp) is not int or timestamp < 0:
            raise ValueError("challenge consumption timestamp is invalid")
        try:
            with self._lock, self._database() as db:
                cursor = db.execute(
                    "INSERT INTO consumed_challenges(challenge, consumed_at) "
                    "VALUES (?, ?) ON CONFLICT(challenge) DO NOTHING",
                    (hashlib.sha256(challenge.encode("ascii")).hexdigest(), timestamp),
                )
                return cursor.rowcount == 1
        except sqlite3.Error as exc:
            raise ChallengeLedgerError("challenge replay ledger write failed closed") from exc
