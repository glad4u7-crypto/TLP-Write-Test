"""Payload-free execution audit events with optional local JSONL persistence.

The SHA-256 chain detects accidental edits, truncation, reordering, and corruption.
It is not cryptographic protection against an attacker who can rewrite the file
and recompute the chain. Production needs protected storage and access controls.
"""
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
import threading
from typing import Any


@dataclass(frozen=True)
class ExecutionAuditEvent:
    timestamp: str
    action: str
    executed: bool
    reason: str


def create_audit_event(action: str, executed: bool, reason: str) -> ExecutionAuditEvent:
    return ExecutionAuditEvent(
        timestamp=datetime.now(timezone.utc).isoformat(),
        action=action,
        executed=executed,
        reason=reason,
    )


class AuditIntegrityError(ValueError):
    """Raised when the persisted audit chain is malformed or inconsistent."""


class JsonlAuditLog:
    """Append-only JSONL audit store with a verifiable SHA-256 hash chain."""

    GENESIS = "0" * 64

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()

    @staticmethod
    def _entry_hash(previous_hash: str, event: dict[str, Any]) -> str:
        canonical = json.dumps(
            {"previous_hash": previous_hash, "event": event},
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()

    def verify(self) -> str:
        """Verify every line and return the last entry hash."""
        if not self.path.exists():
            return self.GENESIS
        previous_hash = self.GENESIS
        try:
            with self.path.open("r", encoding="utf-8") as stream:
                for line_number, line in enumerate(stream, start=1):
                    record = json.loads(line)
                    if not isinstance(record, dict):
                        raise AuditIntegrityError(f"Invalid record at line {line_number}.")
                    event = record.get("event")
                    stored_previous = record.get("previous_hash")
                    stored_hash = record.get("entry_hash")
                    if not isinstance(event, dict):
                        raise AuditIntegrityError(f"Invalid event at line {line_number}.")
                    if stored_previous != previous_hash:
                        raise AuditIntegrityError(f"Broken chain at line {line_number}.")
                    expected_hash = self._entry_hash(previous_hash, event)
                    if not isinstance(stored_hash, str) or not hmac.compare_digest(
                        expected_hash, stored_hash
                    ):
                        raise AuditIntegrityError(f"Hash mismatch at line {line_number}.")
                    previous_hash = stored_hash
        except (OSError, json.JSONDecodeError) as exc:
            raise AuditIntegrityError("Audit log cannot be read or parsed.") from exc
        return previous_hash

    def append(self, event: ExecutionAuditEvent) -> str:
        """Verify the existing chain, then append one payload-free event."""
        if not isinstance(event, ExecutionAuditEvent):
            raise TypeError("Only ExecutionAuditEvent records may be persisted.")
        event_data = asdict(event)
        with self._lock:
            previous_hash = self.verify()
            entry_hash = self._entry_hash(previous_hash, event_data)
            record = {
                "previous_hash": previous_hash,
                "event": event_data,
                "entry_hash": entry_hash,
            }
            self.path.parent.mkdir(parents=True, exist_ok=True)
            descriptor = os.open(
                self.path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600
            )
            with os.fdopen(descriptor, "a", encoding="utf-8") as stream:
                stream.write(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
            return entry_hash
