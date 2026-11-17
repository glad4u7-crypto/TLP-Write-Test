"""Metadata-only audit wrapper for explicit Personal Edition UI mutations."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from core.audit import create_audit_event


class UIActionAuditError(RuntimeError):
    """An audited UI mutation was blocked or needs manual review."""


def execute_audited_ui_mutation(
    audit_log: Any, action: str, operation: Callable[[], Any]
) -> Any:
    """Persist intent before a user-confirmed UI mutation and completion after it.

    The action identifier is a code-owned constant; task/page content is never
    written to the audit log. If intent cannot be persisted, the operation is
    not called. If completion persistence fails, the caller is told that the
    mutation may have completed and requires manual review.
    """
    if not isinstance(action, str) or not action.strip() or not callable(operation):
        raise ValueError("A fixed action identifier and operation are required.")
    try:
        audit_log.append(create_audit_event(action, False, "ui_mutation_pending"))
    except Exception as exc:
        raise UIActionAuditError(
            "Audit storage is unavailable; the requested change was blocked."
        ) from exc

    try:
        result = operation()
    except Exception as operation_error:
        try:
            audit_log.append(create_audit_event(action, False, "ui_mutation_failed"))
        except Exception as audit_error:
            raise UIActionAuditError(
                "The change failed and its failure could not be recorded; manual review is required."
            ) from audit_error
        raise operation_error

    try:
        audit_log.append(create_audit_event(action, True, "ui_mutation_completed"))
    except Exception as exc:
        raise UIActionAuditError(
            "The change may have completed, but its completion audit could not be saved; manual review is required."
        ) from exc
    return result
