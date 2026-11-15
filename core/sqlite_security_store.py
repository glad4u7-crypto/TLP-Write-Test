"""Transactional local persistence for approval nonce consumption and audit events.

This is a storage primitive only. Callers must authenticate principals and
verify receipt signatures before consuming a nonce. No secrets or task payloads
are stored here.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
import sqlite3
import stat
import time
from typing import Any

from core.storage import TenantKey


@dataclass(frozen=True)
class DurableAuditEvent:
    action: str
    result: str
    reason_code: str
    principal_fingerprint: str
    request_id: str


class SQLiteSecurityStore:
    """Process-safe transactional nonce and audit store using SQLite writes."""

    def __init__(self, database_path: str | Path, *, timeout: float = 10.0) -> None:
        self._database_path = str(Path(database_path).absolute())
        self._timeout = timeout
        if self._database_path == ":memory:":
            raise ValueError("SQLiteSecurityStore requires a filesystem-backed database path; :memory: is unsupported.")
        if self._database_path != ":memory:":
            self._secure_database_file(create_parent=True)
        self._initialize()
        if self._database_path != ":memory:":
            self._secure_database_file(create_parent=False)

    def _secure_database_file(self, *, create_parent: bool) -> None:
        """Reject symlinked parent components and unsafe database targets."""
        path = Path(self._database_path)
        # Checking only path.lstat() misses a symlink in a parent directory.
        # Inspect the lexical absolute path without resolving away symlinks.
        for parent in path.absolute().parents:
            try:
                parent_metadata = parent.lstat()
            except FileNotFoundError:
                continue
            if stat.S_ISLNK(parent_metadata.st_mode):
                raise ValueError("Security database parent path must not contain symlinks.")
        if create_parent:
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        # SQLite rollback journals and WAL sidecars live beside the database.
        # A private database file is not sufficient if other users can list or
        # access its containing directory. Never chmod an existing shared dir.
        parent_metadata = path.parent.stat()
        if not stat.S_ISDIR(parent_metadata.st_mode):
            raise ValueError("Security database parent path must be a directory.")
        if os.name == "posix" and parent_metadata.st_mode & 0o077:
            raise ValueError("Security database parent directory must be owner-only.")
        try:
            metadata = path.lstat()
        except FileNotFoundError:
            # SQLite otherwise creates a new database using the process umask,
            # which may briefly expose it before the post-init chmod. Create it
            # atomically with owner-only permissions before SQLite can open it.
            flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0)
            try:
                descriptor = os.open(path, flags, 0o600)
            except FileExistsError:
                metadata = path.lstat()
            else:
                os.close(descriptor)
                metadata = path.lstat()
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
            raise ValueError("Security database must be a regular, non-symlink file.")
        # The database contains tenant identifiers and security audit metadata.
        # Restrict access for both pre-existing and newly initialized files.
        os.chmod(path, 0o600)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self._database_path, timeout=self._timeout, isolation_level=None
        )
        connection.row_factory = sqlite3.Row
        connection.execute(f"PRAGMA busy_timeout = {int(self._timeout * 1000)}")
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        statements = (
            """CREATE TABLE IF NOT EXISTS consumed_approval_nonces (
                issuer TEXT NOT NULL,
                subject TEXT NOT NULL,
                nonce TEXT NOT NULL,
                expires_at INTEGER NOT NULL,
                consumed_at INTEGER NOT NULL,
                PRIMARY KEY (issuer, subject, nonce)
            )""",
            """CREATE INDEX IF NOT EXISTS idx_approval_nonce_expiry
                ON consumed_approval_nonces (expires_at)""",
            """CREATE TABLE IF NOT EXISTS durable_audit_events (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                action TEXT NOT NULL,
                result TEXT NOT NULL,
                reason_code TEXT NOT NULL,
                principal_fingerprint TEXT NOT NULL,
                request_id TEXT NOT NULL,
                previous_hash TEXT NOT NULL,
                entry_hash TEXT NOT NULL UNIQUE
            )""",
        )
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                for statement in statements:
                    connection.execute(statement)
                connection.commit()
            except Exception:
                connection.rollback()
                raise

    def consume_approval_nonce(
        self, tenant: TenantKey, nonce: str, expires_at: int, *, now: int | None = None
    ) -> bool:
        """Atomically consume a verified receipt nonce once for this tenant."""
        if not isinstance(tenant, TenantKey):
            raise TypeError("A validated TenantKey is required.")
        if not isinstance(nonce, str) or not nonce or len(nonce) > 256:
            return False
        if type(expires_at) is not int:
            return False
        current = int(time.time()) if now is None else now
        if type(current) is not int or current >= expires_at:
            return False
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                connection.execute(
                    "DELETE FROM consumed_approval_nonces WHERE expires_at <= ?",
                    (current,),
                )
                try:
                    connection.execute(
                        """INSERT INTO consumed_approval_nonces
                           (issuer, subject, nonce, expires_at, consumed_at)
                           VALUES (?, ?, ?, ?, ?)""",
                        (tenant.issuer, tenant.subject, nonce, expires_at, current),
                    )
                except sqlite3.IntegrityError:
                    connection.rollback()
                    return False
                connection.commit()
                return True
            except Exception:
                connection.rollback()
                raise

    @staticmethod
    def _canonical_event(event: DurableAuditEvent, timestamp: str) -> dict[str, str]:
        if not isinstance(event, DurableAuditEvent):
            raise TypeError("Only DurableAuditEvent records may be stored.")
        fields = {
            "action": event.action,
            "result": event.result,
            "reason_code": event.reason_code,
            "principal_fingerprint": event.principal_fingerprint,
            "request_id": event.request_id,
        }
        for key, value in fields.items():
            if not isinstance(value, str) or not value or len(value) > 256:
                raise ValueError(f"Invalid audit field: {key}")
        return {"timestamp": timestamp, **fields}

    @staticmethod
    def _hash(previous_hash: str, event_data: dict[str, str]) -> str:
        canonical = json.dumps(
            {"previous_hash": previous_hash, "event": event_data},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()

    @staticmethod
    def _verify_audit_connection(connection: sqlite3.Connection) -> str:
        rows = connection.execute(
            """SELECT sequence, timestamp, action, result, reason_code,
                      principal_fingerprint, request_id, previous_hash, entry_hash
               FROM durable_audit_events ORDER BY sequence"""
        ).fetchall()
        # AUTOINCREMENT retains the high-water mark after row deletion. Comparing
        # it with the final row detects accidental tail truncation, including
        # deletion of every row. This is a consistency check, not a tamper-proof
        # external anchor: an attacker able to rewrite the database can alter it.
        sequence_row = connection.execute(
            "SELECT seq FROM sqlite_sequence WHERE name = 'durable_audit_events'"
        ).fetchone()
        recorded_sequence = int(sequence_row["seq"]) if sequence_row is not None else 0
        expected_sequence = int(rows[-1]["sequence"]) if rows else 0
        if recorded_sequence != expected_sequence:
            raise ValueError("SQLite audit sequence indicates missing tail entries.")
        previous_hash = "0" * 64
        for row in rows:
            event_data = {
                "timestamp": row["timestamp"],
                "action": row["action"],
                "result": row["result"],
                "reason_code": row["reason_code"],
                "principal_fingerprint": row["principal_fingerprint"],
                "request_id": row["request_id"],
            }
            if row["previous_hash"] != previous_hash:
                raise ValueError("SQLite audit hash chain linkage is broken.")
            expected = SQLiteSecurityStore._hash(previous_hash, event_data)
            if not hmac.compare_digest(expected, row["entry_hash"]):
                raise ValueError("SQLite audit entry hash mismatch.")
            previous_hash = row["entry_hash"]
        return previous_hash

    def append_audit_event(self, event: DurableAuditEvent) -> str:
        """Verify existing chain and append one event in the same write transaction."""
        timestamp = datetime.now(timezone.utc).isoformat()
        event_data = self._canonical_event(event, timestamp)
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                # Verify while holding the write reservation so another writer
                # cannot change the chain between verification and append.
                previous_hash = self._verify_audit_connection(connection)
                entry_hash = self._hash(previous_hash, event_data)
                connection.execute(
                    """INSERT INTO durable_audit_events
                       (timestamp, action, result, reason_code, principal_fingerprint,
                        request_id, previous_hash, entry_hash)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        timestamp, event.action, event.result, event.reason_code,
                        event.principal_fingerprint, event.request_id,
                        previous_hash, entry_hash,
                    ),
                )
                connection.commit()
                return entry_hash
            except Exception:
                connection.rollback()
                raise

    def verify_audit_chain(self) -> bool:
        with closing(self._connect()) as connection:
            try:
                self._verify_audit_connection(connection)
                return True
            except ValueError:
                return False

    def last_audit_hash(self) -> str:
        with closing(self._connect()) as connection:
            return self._verify_audit_connection(connection)


class SQLiteExecutionAuditLog:
    """Adapter matching ExecutionGateway's append/verify audit-log contract.

    The tenant is supplied by trusted application code, not by the event/task.
    Only a one-way principal fingerprint is persisted.
    """
    GENESIS = "0" * 64

    def __init__(self, store: SQLiteSecurityStore, tenant: TenantKey) -> None:
        if not isinstance(store, SQLiteSecurityStore) or not isinstance(tenant, TenantKey):
            raise TypeError("A SQLiteSecurityStore and validated TenantKey are required.")
        self._store = store
        self._principal_fingerprint = hashlib.sha256(
            f"{tenant.issuer}\n{tenant.subject}".encode("utf-8")
        ).hexdigest()

    def append(self, event: Any) -> str:
        if not all(hasattr(event, field) for field in ("action", "executed", "reason")):
            raise TypeError("Unsupported execution audit event.")
        import uuid
        record = DurableAuditEvent(
            action=str(event.action),
            result="success" if event.executed else "denied",
            reason_code=str(event.reason),
            principal_fingerprint=self._principal_fingerprint,
            request_id=uuid.uuid4().hex,
        )
        return self._store.append_audit_event(record)

    def verify(self) -> str:
        if not self._store.verify_audit_chain():
            raise ValueError("SQLite audit hash chain verification failed.")
        return self._store.last_audit_hash()
