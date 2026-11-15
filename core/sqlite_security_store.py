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
import json
from pathlib import Path
import sqlite3
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
        self._database_path = str(database_path)
        self._timeout = timeout
        if self._database_path != ":memory:":
            Path(self._database_path).parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

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

    def append_audit_event(self, event: DurableAuditEvent) -> str:
        """Append one payload-free audit event in a serialized DB transaction."""
        timestamp = datetime.now(timezone.utc).isoformat()
        event_data = self._canonical_event(event, timestamp)
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                row = connection.execute(
                    "SELECT entry_hash FROM durable_audit_events ORDER BY sequence DESC LIMIT 1"
                ).fetchone()
                previous_hash = row["entry_hash"] if row else "0" * 64
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
            rows = connection.execute(
                """SELECT timestamp, action, result, reason_code,
                          principal_fingerprint, request_id, previous_hash, entry_hash
                   FROM durable_audit_events ORDER BY sequence"""
            ).fetchall()
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
                return False
            expected = self._hash(previous_hash, event_data)
            if not hashlib.compare_digest(expected, row["entry_hash"]):
                return False
            previous_hash = row["entry_hash"]
        return True
