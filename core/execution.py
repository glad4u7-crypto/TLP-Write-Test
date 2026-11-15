"""Permission-gated dispatch for explicitly registered agent actions.

No shell, browser, network, device, or provider adapters are included.
"""
from collections.abc import Callable, Mapping, Iterable
from dataclasses import dataclass
import re
from typing import Any

from core.approvals import ApprovalAuthority, ApprovalReceipt
from core.audit import (
    ExecutionAuditEvent,
    JsonlAuditLog,
    create_audit_event,
)
from core.safety import authorize_action


ActionHandler = Callable[[Mapping[str, Any]], Any]


def _canonical_action(action: object) -> str:
    if not isinstance(action, str):
        return ""
    return re.sub(r"[^a-z0-9]+", "_", action.strip().lower()).strip("_")


@dataclass(frozen=True)
class ExecutionResult:
    executed: bool
    reason: str
    output: Any = None
    audit_event: ExecutionAuditEvent | None = None


class ExecutionGateway:
    """Dispatch registered handlers only after policy, approval and audit checks.

    The ApprovalAuthority and audit store must remain private to trusted
    application code. This is not isolation against arbitrary code in-process.
    """

    def __init__(
        self,
        handlers: Mapping[str, ActionHandler] | None = None,
        *,
        approval_authority: ApprovalAuthority | None = None,
        auto_run_actions: Iterable[str] = (),
        audit_log: JsonlAuditLog | None = None,
    ) -> None:
        self._handlers: dict[str, ActionHandler] = {}
        self._approval_authority = approval_authority
        self._audit_log = audit_log
        self._auto_run_actions = frozenset(
            _canonical_action(item) for item in auto_run_actions
            if _canonical_action(item)
        )
        self._audit_events: list[ExecutionAuditEvent] = []
        for action, handler in (handlers or {}).items():
            canonical = _canonical_action(action)
            if not canonical or not callable(handler):
                raise ValueError("Each handler needs a valid action and callable.")
            if not authorize_action(canonical, approved_action=canonical).allowed:
                raise ValueError(f"Action is not registered for execution: {canonical}")
            if canonical in self._handlers:
                raise ValueError(f"Duplicate action handler: {canonical}")
            self._handlers[canonical] = handler

    @property
    def audit_events(self) -> tuple[ExecutionAuditEvent, ...]:
        """Read-only snapshot of payload-free events for this process lifetime."""
        return tuple(self._audit_events)

    def _record(
        self,
        action: object,
        executed: bool,
        reason: str,
    ) -> tuple[ExecutionAuditEvent, bool]:
        event = create_audit_event(_canonical_action(action), executed, reason)
        self._audit_events.append(event)
        if self._audit_log is None:
            return event, True
        try:
            self._audit_log.append(event)
        except Exception:
            # Any backend failure must fail closed before a side effect.
            # Keep the gateway independent of a specific audit backend type.
            return event, False
        return event, True

    def _finish(
        self,
        action: object,
        executed: bool,
        reason: str,
        output: Any = None,
    ) -> ExecutionResult:
        event, persisted = self._record(action, executed, reason)
        if not persisted:
            return ExecutionResult(
                False,
                "Audit persistence failed; execution was blocked or outcome could not be fully recorded.",
                None,
                event,
            )
        return ExecutionResult(executed, reason, output, event)

    def execute(
        self,
        action: str,
        payload: Mapping[str, Any] | None = None,
        *,
        approval_receipt: ApprovalReceipt | None = None,
        auto_run: bool = False,
    ) -> ExecutionResult:
        """Run one handler only after policy + approval + durable intent audit."""
        if payload is not None and not isinstance(payload, Mapping):
            return self._finish(action, False, "Action payload must be a mapping.")

        decision = authorize_action(action)
        authorized = decision.allowed

        if not authorized and auto_run:
            auto_decision = authorize_action(
                action,
                auto_run=True,
                auto_run_actions=self._auto_run_actions,
            )
            authorized = auto_decision.allowed
            if not authorized:
                decision = auto_decision

        if not authorized and self._approval_authority is not None:
            if self._approval_authority.consume(approval_receipt, action, payload):
                exact_action = _canonical_action(action)
                decision = authorize_action(action, approved_action=exact_action)
                authorized = decision.allowed

        if not authorized:
            return self._finish(action, False, decision.reason)

        canonical = _canonical_action(action)
        handler = self._handlers.get(canonical)
        if handler is None:
            return self._finish(
                action, False, "No trusted handler is registered for this action."
            )

        # Persist intent before the side effect. Fail closed if audit is unavailable.
        intent, persisted = self._record(
            action, False, "authorized_dispatch_pending"
        )
        if not persisted:
            return ExecutionResult(
                False, "Audit persistence unavailable; action was not executed.",
                None, intent,
            )

        try:
            output = handler(payload or {})
        except Exception:
            completion, completed_persisted = self._record(
                action, False, "registered_handler_failed"
            )
            reason = "The registered action handler failed."
            if not completed_persisted:
                reason = "The handler failed and completion audit persistence failed."
            return ExecutionResult(False, reason, None, completion)

        completion, completed_persisted = self._record(
            action, True, "action_executed"
        )
        if not completed_persisted:
            # The side effect already happened; the durable intent record remains.
            return ExecutionResult(
                True,
                "Action executed; completion audit persistence failed. Manual review required.",
                output,
                completion,
            )
        return ExecutionResult(
            True, "Action executed after permission and audit checks.",
            output, completion,
        )
