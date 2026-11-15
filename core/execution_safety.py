"""Fail-closed preflight, per-action approval and audit-before-dispatch boundary.

No built-in I/O handlers are provided. Trusted application code must inject
a reviewed handler registry and an ApprovalAuthority.
"""
from collections.abc import Mapping
from dataclasses import dataclass
import json
from typing import Any, Callable

from core.audit import ExecutionAuditEvent
from core.approvals import ApprovalAuthority, ApprovalReceipt
from core.safety import authorize_action

@dataclass(frozen=True)
class PreflightResult:
    valid: bool
    action: str
    reason: str

@dataclass(frozen=True)
class SafeExecutionResult:
    executed: bool
    action: str
    reason: str
    value: Any = None
    manual_review_required: bool = False

def validate_pre_execution(action: object, payload: object, *, max_payload_bytes: int = 32768) -> PreflightResult:
    """Validate untrusted request shape and policy before any side effect."""
    if not isinstance(action, str) or not action.strip() or len(action) > 128:
        return PreflightResult(False, "", "Invalid action identifier.")
    if not isinstance(payload, Mapping):
        return PreflightResult(False, action, "Payload must be a mapping.")
    if type(max_payload_bytes) is not int or not 1 <= max_payload_bytes <= 1048576:
        return PreflightResult(False, action, "Invalid payload size policy.")
    try:
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, OverflowError):
        return PreflightResult(False, action, "Payload is not canonical JSON data.")
    if len(encoded) > max_payload_bytes:
        return PreflightResult(False, action, "Payload exceeds the configured size limit.")
    decision = authorize_action(action)
    if not decision.allowed and "requires approval" not in decision.reason:
        return PreflightResult(False, action, decision.reason)
    return PreflightResult(True, action.strip(), "Pre-execution validation passed.")

class ExecutionSafetyBoundary:
    """Approval + audit gate around an explicitly injected handler registry.

    The authority is a trusted capability and must never be exposed to planners,
    model output, or task payloads. No Auto-Run path exists here.
    """
    def __init__(self, *, approval_authority: ApprovalAuthority, audit_log: Any, handlers: Mapping[str, Callable[[Mapping[str, Any]], Any]]):
        if not isinstance(approval_authority, ApprovalAuthority):
            raise TypeError("A trusted ApprovalAuthority is required.")
        if audit_log is None or not callable(getattr(audit_log, "append", None)):
            raise TypeError("An audit writer is required.")
        if not isinstance(handlers, Mapping):
            raise TypeError("Handlers must be an explicit mapping.")
        clean = {}
        for action, handler in handlers.items():
            if not isinstance(action, str) or not callable(handler):
                raise TypeError("Every handler needs a string action and callable.")
            clean[action] = handler
        self._authority, self._audit, self._handlers = approval_authority, audit_log, clean

    def execute(self, action: object, payload: object, *, receipt: ApprovalReceipt | None = None, tenant: Any = None, session_scope: str = "") -> SafeExecutionResult:
        preflight = validate_pre_execution(action, payload)
        if not preflight.valid:
            return SafeExecutionResult(False, preflight.action, preflight.reason)
        handler = self._handlers.get(preflight.action)
        if handler is None:
            return SafeExecutionResult(False, preflight.action, "No reviewed handler is registered.")
        policy = authorize_action(preflight.action)
        if not policy.allowed and not self._authority.consume(receipt, preflight.action, payload, tenant=tenant, session_scope=session_scope):
            return SafeExecutionResult(False, preflight.action, "Explicit action-specific approval is missing, invalid, expired, or already used.")
        try:
            self._audit.append(ExecutionAuditEvent(timestamp="", action=preflight.action, executed=False, reason="execution_intent"))
        except Exception:
            return SafeExecutionResult(False, preflight.action, "Audit intent could not be persisted; dispatch blocked.")
        try:
            value = handler(payload)
        except Exception:
            try:
                self._audit.append(ExecutionAuditEvent(timestamp="", action=preflight.action, executed=False, reason="handler_failed"))
            except Exception:
                return SafeExecutionResult(False, preflight.action, "Handler failed and audit completion failed; manual review required.", manual_review_required=True)
            return SafeExecutionResult(False, preflight.action, "Handler failed; failure was audited.")
        try:
            self._audit.append(ExecutionAuditEvent(timestamp="", action=preflight.action, executed=True, reason="execution_completed"))
        except Exception:
            return SafeExecutionResult(False, preflight.action, "Action returned but completion audit failed; manual review required.", manual_review_required=True)
        return SafeExecutionResult(True, preflight.action, "Execution completed and audited.", value=value)