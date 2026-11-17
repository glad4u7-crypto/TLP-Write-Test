"""Local single-owner password authentication for APAA Personal Edition.

This is intended only for the loopback-only local runtime. It is not a
replacement for OIDC or a secure remote authentication boundary.
"""
from __future__ import annotations

import hashlib
import hmac
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
                db.execute(
                    """INSERT INTO local_owner_auth
                       (singleton_id, salt, verifier, failed_attempts, locked_until, created_at)
                       VALUES (1, ?, ?, 0, 0, ?)""",
                    (salt, verifier, int(time.time())),
                )
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
                if row is None or current < int(row[3]):
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
                if row is None or current < int(row[3]):
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
                    db.commit()
                    return False
                db.execute(
                    """UPDATE local_owner_auth SET salt = ?, verifier = ?,
                       failed_attempts = 0, locked_until = 0 WHERE singleton_id = 1""",
                    (salt, verifier),
                )
                db.commit()
                return True
            except Exception:
                db.rollback()
                raise
