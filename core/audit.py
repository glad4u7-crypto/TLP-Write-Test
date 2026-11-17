"""Payload-free execution audit events with optional local JSONL persistence.

The SHA-256 chain detects accidental edits, truncation, reordering, and corruption.
It is not cryptographic protection against an attacker who can rewrite the file
and recompute hashes. Production needs protected storage and access controls.
"""
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
import re
from pathlib import Path
import stat
import threading
from typing import Any


# Share a lock between all JsonlAuditLog objects targeting the same resolved
# path. A per-instance lock is insufficient: two Streamlit sessions can create
# separate objects that append to the same file in one Python process.
_PATH_LOCKS: dict[str, threading.Lock] = {}
_PATH_LOCKS_GUARD = threading.Lock()


@dataclass(frozen=True)
class ExecutionAuditEvent:
    timestamp: str
    action: str
    executed: bool
    reason: str


_SECRET_ASSIGNMENT = re.compile(
    r"(?i)\\b(authorization|proxy-authorization|cookie|set-cookie|password|passwd|token|secret|api[_-]?key|session(?:[_ -]?id)?)\\s*[:=]\\s*([^\\s,;]+)"
)
_BEARER = re.compile(r"(?i)\\b(bearer|basic)\\s+[A-Za-z0-9._~+/=-]+")
_URL = re.compile(r"(?i)\\bhttps?://[^\\s<>\\\"]+")
_EMAIL = re.compile(r"(?i)\\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\\.[A-Z]{2,}\\b")


def redact_sensitive_text(value: str, *, limit: int = 256) -> str:
    """Return bounded audit text with credentials, URL paths and identifiers masked."""
    if type(value) is not str:
        raise TypeError("audit text must be a string")
    value = _SECRET_ASSIGNMENT.sub(lambda m: f"{m.group(1)}=[REDACTED]", value)
    value = _BEARER.sub(lambda m: f"{m.group(1)} [REDACTED]", value)

    def hide_url(match):
        from urllib.parse import urlsplit
        try:
            parsed = urlsplit(match.group(0))
            host = parsed.hostname or "[host]"
            port = f":{parsed.port}" if parsed.port else ""
            return f"{parsed.scheme}://{host}{port}/[REDACTED]"
        except ValueError:
            return "[URL REDACTED]"

    value = _URL.sub(hide_url, value)
    value = _EMAIL.sub("[EMAIL REDACTED]", value)
    return value[:limit]


def create_audit_event(action: str, executed: bool, reason: str) -> ExecutionAuditEvent:
    if type(executed) is not bool:
        raise TypeError("executed must be a boolean")
    return ExecutionAuditEvent(
        timestamp=datetime.now(timezone.utc).isoformat(),
        action=redact_sensitive_text(action, limit=96),
        executed=executed,
        reason=redact_sensitive_text(reason, limit=256),
    )


class AuditIntegrityError(ValueError):
    """Raised when the persisted audit chain is malformed or inconsistent."""


class JsonlAuditLog:
    """Append-only JSONL audit store with a verifiable SHA-256 hash chain."""

    GENESIS = "0" * 64

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).absolute()
        lock_key = str(self.path.resolve(strict=False))
        with _PATH_LOCKS_GUARD:
            self._lock = _PATH_LOCKS.setdefault(lock_key, threading.Lock())

    @staticmethod
    def _entry_hash(previous_hash: str, event: dict[str, Any]) -> str:
        canonical = json.dumps(
            {"previous_hash": previous_hash, "event": event},
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()

    def _secure_parent_directory(self, *, create: bool = False) -> bool:
        """Reject symlinked path components and require a private log directory."""
        absolute_parents = self.path.absolute().parents
        for parent in absolute_parents:
            try:
                metadata = parent.lstat()
            except FileNotFoundError:
                continue
            if stat.S_ISLNK(metadata.st_mode):
                raise AuditIntegrityError("Audit log parent path must not contain symlinks.")

        if create:
            self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)

        try:
            metadata = self.path.parent.lstat()
        except FileNotFoundError:
            return False
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
            raise AuditIntegrityError("Audit log parent must be a real directory.")
        if os.name == "posix" and metadata.st_mode & 0o077:
            raise AuditIntegrityError("Audit log parent directory must be owner-only.")
        return True

    def _open_existing_readonly(self) -> int:
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(self.path, flags)
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            os.close(descriptor)
            raise AuditIntegrityError("Audit log target must be a regular file.")
        return descriptor

    def verify(self) -> str:
        """Verify every line and return the last entry hash."""
        if not self._secure_parent_directory():
            return self.GENESIS
        if not self.path.exists() and not self.path.is_symlink():
            return self.GENESIS
        previous_hash = self.GENESIS
        try:
            descriptor = self._open_existing_readonly()
            with os.fdopen(descriptor, "r", encoding="utf-8") as stream:
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
        except AuditIntegrityError:
            raise
        except (OSError, json.JSONDecodeError) as exc:
            raise AuditIntegrityError("Audit log cannot be read, opened safely, or parsed.") from exc
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
            self._secure_parent_directory(create=True)
            flags = (
                os.O_WRONLY | os.O_CREAT | os.O_APPEND
                | getattr(os, "O_NOFOLLOW", 0)
            )
            descriptor = os.open(self.path, flags, 0o600)
            try:
                if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                    raise AuditIntegrityError("Audit log target must be a regular file.")
                os.fchmod(descriptor, 0o600)
                with os.fdopen(descriptor, "a", encoding="utf-8") as stream:
                    descriptor = -1
                    stream.write(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n")
                    stream.flush()
                    os.fsync(stream.fileno())
            finally:
                if descriptor >= 0:
                    os.close(descriptor)
            return entry_hash
