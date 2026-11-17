"""Local single-owner password authentication for APAA Personal Edition.

This is intended only for the loopback-only local runtime. It is not a
replacement for OIDC or a secure remote authentication boundary.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
from contextlib import contextmanager
from pathlib import Path
import secrets
import sqlite3
import stat
import time


_MIN_PASSPHRASE_LENGTH = 12
_SALT_BYTES = 16
_VERIFIER_BYTES = 32
_SCRYPT_N = 1 << 14
_SCRYPT_R = 8
_SCRYPT_P = 1


class LocalOwnerAuthStore:
    """Persist one owner verifier and cross-restart login throttling in SQLite."""

    def __init__(
        self,
        database_path: str | Path,
        *,
        max_attempts: int = 5,
        lockout_seconds: int = 300,
    ) -> None:
        if type(max_attempts) is not int or max_attempts < 1:
            raise ValueError("max_attempts must be a positive integer.")
        if type(lockout_seconds) is not int or lockout_seconds < 1:
            raise ValueError("lockout_seconds must be a positive integer.")
        self.path = Path(database_path).expanduser().absolute()
        self.max_attempts = max_attempts
        self.lockout_seconds = lockout_seconds
        self._secure_path(create_parent=True)
        with self._connect() as db:
            db.execute(
                """CREATE TABLE IF NOT EXISTS local_owner_auth (
                    singleton_id INTEGER PRIMARY KEY CHECK (singleton_id = 1),
                    salt BLOB NOT NULL,
                    verifier BLOB NOT NULL,
                    failed_attempts INTEGER NOT NULL DEFAULT 0,
                    locked_until INTEGER NOT NULL DEFAULT 0,
                    created_at INTEGER NOT NULL,
                    last_success_at INTEGER
                )"""
            )
            db.execute(
                """CREATE TABLE IF NOT EXISTS local_owner_auth_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    occurred_at INTEGER NOT NULL,
                    previous_hash TEXT,
                    entry_hash TEXT
                )"""
            )
            db.execute(
                """CREATE TABLE IF NOT EXISTS local_owner_auth_event_head (
                    singleton_id INTEGER PRIMARY KEY CHECK (singleton_id = 1),
                    event_id INTEGER NOT NULL,
                    entry_hash TEXT NOT NULL
                )"""
            )
            db.execute("BEGIN IMMEDIATE")
            try:
                columns = {
                    row[1] for row in db.execute(
                        "PRAGMA table_info(local_owner_auth_events)"
                    ).fetchall()
                }
                legacy_schema = (
                    "previous_hash" not in columns or "entry_hash" not in columns
                )
                if "previous_hash" not in columns:
                    db.execute(
                        "ALTER TABLE local_owner_auth_events ADD COLUMN previous_hash TEXT"
                    )
                if "entry_hash" not in columns:
                    db.execute(
                        "ALTER TABLE local_owner_auth_events ADD COLUMN entry_hash TEXT"
                    )
                rows = db.execute(
                    "SELECT event_id, event_type, occurred_at, previous_hash, entry_hash "
                    "FROM local_owner_auth_events ORDER BY event_id"
                ).fetchall()
                if legacy_schema:
                    previous = self._EVENT_GENESIS
                    for event_id, event_type, occurred_at, _, _ in rows:
                        entry = self._event_hash(
                            previous, int(event_id), str(event_type), int(occurred_at)
                        )
                        db.execute(
                            "UPDATE local_owner_auth_events "
                            "SET previous_hash=?, entry_hash=? WHERE event_id=?",
                            (previous, entry, int(event_id)),
                        )
                        previous = entry
                    rows = db.execute(
                        "SELECT event_id, event_type, occurred_at, previous_hash, entry_hash "
                        "FROM local_owner_auth_events ORDER BY event_id"
                    ).fetchall()
                # Store the expected tail separately from the event rows so
                # accidental tail deletion/truncation is detectable.
                head = db.execute(
                    "SELECT event_id, entry_hash FROM local_owner_auth_event_head "
                    "WHERE singleton_id=1"
                ).fetchone()
                if head is None:
                    if rows and not legacy_schema:
                        raise ValueError(
                            "Owner authentication audit head is missing; refusing recovery."
                        )
                    tail_id = int(rows[-1][0]) if rows else 0
                    tail_hash = str(rows[-1][4]) if rows else self._EVENT_GENESIS
                    db.execute(
                        "INSERT INTO local_owner_auth_event_head "
                        "(singleton_id, event_id, entry_hash) VALUES (1, ?, ?)",
                        (tail_id, tail_hash),
                    )
                # Never auto-reseal a database that already has the hash-chain
                # schema: NULL or invalid hashes are corruption, not migration.
                self._verify_events(db)
                db.commit()
            except Exception:
                db.rollback()
                raise
        self._secure_path(create_parent=False)

    def _secure_path(self, *, create_parent: bool) -> None:
        for component in (self.path, *self.path.parents):
            try:
                metadata = component.lstat()
            except FileNotFoundError:
                continue
            if stat.S_ISLNK(metadata.st_mode):
                raise ValueError("Owner authentication path must not contain symlinks.")
        if create_parent:
            self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        parent = self.path.parent.stat()
        if not stat.S_ISDIR(parent.st_mode):
            raise ValueError("Owner authentication parent must be a directory.")
        if os.name == "posix" and parent.st_mode & 0o077:
            raise ValueError("Owner authentication directory must be owner-only.")
        try:
            metadata = self.path.lstat()
        except FileNotFoundError:
            flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0)
            try:
                descriptor = os.open(self.path, flags, 0o600)
            except FileExistsError:
                metadata = self.path.lstat()
            else:
                os.close(descriptor)
                metadata = self.path.lstat()
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
            raise ValueError("Owner authentication database must be a regular file.")
        os.chmod(self.path, 0o600)

    @contextmanager
    def _connect(self):
        self._secure_path(create_parent=False)
        db = sqlite3.connect(str(self.path), timeout=10, isolation_level=None)
        try:
            db.execute("PRAGMA busy_timeout = 10000")
            db.execute("PRAGMA foreign_keys = ON")
            yield db
        finally:
            db.close()

    @staticmethod
    def _derive(passphrase: str, salt: bytes) -> bytes:
        return hashlib.scrypt(
            passphrase.encode("utf-8"),
            salt=salt,
            n=_SCRYPT_N,
            r=_SCRYPT_R,
            p=_SCRYPT_P,
            dklen=_VERIFIER_BYTES,
        )

    @staticmethod
    def _validate_passphrase(passphrase: object) -> None:
        if not isinstance(passphrase, str):
            raise ValueError("Owner passphrase must be text.")
        if len(passphrase) < _MIN_PASSPHRASE_LENGTH:
            raise ValueError("Use an Owner passphrase with at least 12 characters.")
        if len(passphrase) > 1024 or not passphrase.strip():
            raise ValueError("Owner passphrase length is invalid.")

    _ALLOWED_EVENTS = frozenset({
        "owner_setup", "login_success", "login_failed", "login_locked",
        "logout", "passphrase_changed", "passphrase_change_failed",
    })

    _ALLOWED_EVENTS = frozenset({
        "owner_setup", "login_success", "login_failed", "login_locked",
        "logout", "passphrase_changed", "passphrase_change_failed",
    })
    _EVENT_GENESIS = "0" * 64

    @staticmethod
    def _event_hash(previous_hash: str, event_id: int, event_type: str, occurred_at: int) -> str:
        canonical = json.dumps(
            {"event_id": event_id, "event_type": event_type,
             "occurred_at": occurred_at, "previous_hash": previous_hash},
            sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()

    @classmethod
    def _verify_events(cls, db: sqlite3.Connection) -> str:
        previous = cls._EVENT_GENESIS
        rows = db.execute(
            "SELECT event_id, event_type, occurred_at, previous_hash, entry_hash "
            "FROM local_owner_auth_events ORDER BY event_id"
        ).fetchall()
        for event_id, event_type, occurred_at, stored_previous, stored_hash in rows:
            if event_type not in cls._ALLOWED_EVENTS or type(occurred_at) is not int:
                raise ValueError("Owner authentication audit chain contains an invalid event.")
            expected = cls._event_hash(previous, int(event_id), str(event_type), int(occurred_at))
            if stored_previous != previous or not isinstance(stored_hash, str) or not hmac.compare_digest(expected, stored_hash):
                raise ValueError("Owner authentication audit chain integrity verification failed.")
            previous = stored_hash
        head = db.execute(
            "SELECT event_id, entry_hash FROM local_owner_auth_event_head "
            "WHERE singleton_id=1"
        ).fetchone()
        expected_id = int(rows[-1][0]) if rows else 0
        if head is None or int(head[0]) != expected_id or head[1] != previous:
            raise ValueError("Owner authentication audit chain integrity verification failed.")
        return previous

    @classmethod
    def _append_event(cls, db: sqlite3.Connection, event_type: str, timestamp: int) -> None:
        cls._verify_events(db)
        latest = db.execute(
            "SELECT entry_hash FROM local_owner_auth_events ORDER BY event_id DESC LIMIT 1"
        ).fetchone()
        previous = str(latest[0]) if latest else cls._EVENT_GENESIS
        cursor = db.execute(
            "INSERT INTO local_owner_auth_events "
            "(event_type, occurred_at, previous_hash, entry_hash) VALUES (?, ?, ?, ?)",
            (event_type, timestamp, previous, ""),
        )
        event_id = int(cursor.lastrowid)
        entry = cls._event_hash(previous, event_id, event_type, timestamp)
        db.execute("UPDATE local_owner_auth_events SET entry_hash=? WHERE event_id=?", (entry, event_id))
        db.execute(
            "UPDATE local_owner_auth_event_head SET event_id=?, entry_hash=? WHERE singleton_id=1",
            (event_id, entry),
        )

    def verify_events(self) -> str:
        with self._connect() as db:
            return self._verify_events(db)

    def record_event(self, event_type: str, *, occurred_at: int | None = None) -> None:
        """Append a payload-free local authentication security event."""
        if event_type not in self._ALLOWED_EVENTS:
            raise ValueError("Unsupported Owner authentication audit event.")
        timestamp = int(time.time()) if occurred_at is None else occurred_at
        if type(timestamp) is not int or timestamp < 0:
            raise ValueError("Owner authentication audit timestamp is invalid.")
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                self._append_event(db, event_type, timestamp)
                db.commit()
            except Exception:
                db.rollback()
                raise

    def list_events(self, *, limit: int = 100) -> tuple[tuple[str, int], ...]:
        """Return newest payload-free authentication events for local review."""
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise ValueError("Owner authentication audit limit is invalid.")
        with self._connect() as db:
            self._verify_events(db)
            rows = db.execute(
                """SELECT event_type, occurred_at FROM local_owner_auth_events
                   ORDER BY event_id DESC LIMIT ?""",
                (limit,),
            ).fetchall()
        return tuple((str(row[0]), int(row[1])) for row in rows)

    def is_configured(self) -> bool:
        with self._connect() as db:
            row = db.execute(
                "SELECT 1 FROM local_owner_auth WHERE singleton_id = 1"
            ).fetchone()
        return row is not None

    def configure(self, passphrase: str, confirmation: str) -> None:
        self._validate_passphrase(passphrase)
        if not isinstance(confirmation, str) or not hmac.compare_digest(
            passphrase, confirmation
        ):
            raise ValueError("Owner passphrases do not match.")
        salt = secrets.token_bytes(_SALT_BYTES)
        verifier = self._derive(passphrase, salt)
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                if db.execute(
                    "SELECT 1 FROM local_owner_auth WHERE singleton_id = 1"
                ).fetchone():
                    raise ValueError("Owner authentication is already configured.")
                created_at = int(time.time())
                db.execute(
                    """INSERT INTO local_owner_auth
                       (singleton_id, salt, verifier, failed_attempts, locked_until, created_at)
                       VALUES (1, ?, ?, 0, 0, ?)""",
                    (salt, verifier, created_at),
                )
                self._append_event(db, "owner_setup", created_at)
                db.commit()
            except Exception:
                db.rollback()
                raise

    def authenticate(self, passphrase: str, *, now: int | None = None) -> bool:
        current = int(time.time()) if now is None else now
        if type(current) is not int or current < 0:
            return False
        if not isinstance(passphrase, str) or len(passphrase) > 1024:
            candidate = ""
        else:
            candidate = passphrase
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                row = db.execute(
                    """SELECT salt, verifier, failed_attempts, locked_until
                       FROM local_owner_auth WHERE singleton_id = 1"""
                ).fetchone()
                if row is None:
                    db.commit()
                    return False
                if current < int(row[3]):
                    self._append_event(db, "login_locked", current)
                    db.commit()
                    return False
                actual = self._derive(candidate, bytes(row[0]))
                valid = hmac.compare_digest(actual, bytes(row[1]))
                if valid:
                    db.execute(
                        """UPDATE local_owner_auth
                           SET failed_attempts = 0, locked_until = 0, last_success_at = ?
                           WHERE singleton_id = 1""",
                        (current,),
                    )
                    self._append_event(db, "login_success", current)
                    db.commit()
                    return True
                failures = int(row[2]) + 1
                locked_until = current + self.lockout_seconds if failures >= self.max_attempts else 0
                db.execute(
                    """UPDATE local_owner_auth
                       SET failed_attempts = ?, locked_until = ?
                       WHERE singleton_id = 1""",
                    (0 if locked_until else failures, locked_until),
                )
                self._append_event(db, "login_locked" if locked_until else "login_failed", current)
                db.commit()
                return False
            except Exception:
                db.rollback()
                raise

    def change_passphrase(self, current_passphrase: str, new_passphrase: str,
                          confirmation: str, *, now: int | None = None) -> bool:
        self._validate_passphrase(new_passphrase)
        if not isinstance(confirmation, str) or not hmac.compare_digest(
            new_passphrase, confirmation
        ):
            raise ValueError("New Owner passphrases do not match.")
        current = int(time.time()) if now is None else now
        if type(current) is not int or current < 0:
            return False
        salt = secrets.token_bytes(_SALT_BYTES)
        verifier = self._derive(new_passphrase, salt)
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                row = db.execute(
                    """SELECT salt, verifier, failed_attempts, locked_until
                       FROM local_owner_auth WHERE singleton_id = 1"""
                ).fetchone()
                if row is None:
                    db.commit()
                    return False
                if current < int(row[3]):
                    self._append_event(db, "passphrase_change_failed", current)
                    db.commit()
                    return False
                actual = self._derive(current_passphrase if isinstance(current_passphrase, str) else "", bytes(row[0]))
                if not hmac.compare_digest(actual, bytes(row[1])):
                    failures = int(row[2]) + 1
                    locked_until = current + self.lockout_seconds if failures >= self.max_attempts else 0
                    db.execute(
                        """UPDATE local_owner_auth SET failed_attempts = ?, locked_until = ?
                           WHERE singleton_id = 1""",
                        (0 if locked_until else failures, locked_until),
                    )
                    self._append_event(db, "passphrase_change_failed", current)
                    db.commit()
                    return False
                db.execute(
                    """UPDATE local_owner_auth SET salt = ?, verifier = ?,
                       failed_attempts = 0, locked_until = 0 WHERE singleton_id = 1""",
                    (salt, verifier),
                )
                self._append_event(db, "passphrase_changed", current)
                db.commit()
                return True
            except Exception:
                db.rollback()
                raise
