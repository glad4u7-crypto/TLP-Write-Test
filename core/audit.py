"""Minimal in-memory execution audit events.

Payload values are deliberately excluded so secrets and user content are not
copied into logs. Durable tamper-evident storage is a later release gate.
"""
from dataclasses import dataclass
from datetime import datetime, timezone


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
