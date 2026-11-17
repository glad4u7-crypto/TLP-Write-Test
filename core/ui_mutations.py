"""Payload-bound approval and metadata-only audit for Personal Edition UI mutations."""
from __future__ import annotations

from collections.abc import Callable, Mapping
import json
from typing import Any

from core.audit import create_audit_event
from core.safety import authorize_action


class UIActionAuditError(RuntimeError):
    """A UI mutation was blocked or needs manual review."""


def execute_audited_ui_mutation(
    audit_log: Any,
    action: str,
    approved: bool,
    payload: Mapping[str, Any],
    operation: Callable[[Mapping[str, Any]], Any],
    *,
    approval_authority: Any,
    tenant: Any,
    session_scope: str,
) -> Any:
    """Consume a fresh action/payload/session-bound Owner receipt before mutation.

    The trusted UI passes the exact values it is about to save. They are
    canonicalized once, copied into a private JSON snapshot, approved and then
    passed to the operation. The operation must use that snapshot rather than
    closing over mutable form values. Approval nonces are one-time and durable
    when the configured authority uses the SQLite nonce store.
    """
    if not isinstance(action, str) or not action.strip() or not callable(operation):
        raise ValueError("A fixed action identifier and operation are required.")
    if type(approved) is not bool:
        raise ValueError("Explicit UI approval must be a boolean.")
    if not isinstance(payload, Mapping):
        raise ValueError("A mapping payload is required for Owner approval.")
    if not isinstance(session_scope, str) or not session_scope or len(session_scope) > 256:
        raise ValueError("A valid Owner approval session scope is required.")
    if not callable(getattr(approval_authority, "issue", None)) or not callable(
        getattr(approval_authority, "consume", None)
    ):
        raise UIActionAuditError("Owner approval authority is unavailable; the change was blocked.")

    if not approved:
        decision = authorize_action(action)
        raise UIActionAuditError(decision.reason)

    try:
        canonical_payload = json.dumps(
            dict(payload), sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False,
        )
        payload_snapshot = json.loads(canonical_payload)
        if not isinstance(payload_snapshot, dict):
            raise ValueError("Approval payload must be a JSON object.")
        receipt = approval_authority.issue(
            action, payload_snapshot, tenant=tenant, session_scope=session_scope
        )
        consumed = approval_authority.consume(
            receipt, action, payload_snapshot, tenant=tenant,
            session_scope=session_scope,
        )
    except Exception as exc:
        raise UIActionAuditError(
            "Owner approval could not be verified; the requested change was blocked."
        ) from exc
    if not consumed:
        raise UIActionAuditError(
            "Owner approval was invalid, expired, replayed or bound to different details."
        )

    try:
        audit_log.append(create_audit_event(action, False, "ui_mutation_pending"))
    except Exception as exc:
        raise UIActionAuditError(
            "Audit storage is unavailable; the requested change was blocked."
        ) from exc

    try:
        result = operation(payload_snapshot)
    except Exception:
        try:
            audit_log.append(create_audit_event(action, False, "ui_mutation_failed"))
        except Exception as audit_error:
            raise UIActionAuditError(
                "The change failed and its failure could not be recorded; manual review is required."
            ) from audit_error
        raise

    try:
        audit_log.append(create_audit_event(action, True, "ui_mutation_completed"))
    except Exception as exc:
        raise UIActionAuditError(
            "The change may have completed, but its completion audit could not be saved; manual review is required."
        ) from exc
    return result
