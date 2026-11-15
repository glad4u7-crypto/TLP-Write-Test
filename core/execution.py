"""Permission-gated dispatch for explicitly registered agent actions.

This gateway has no shell, browser, network, or provider adapters. Real
handlers must be registered only by trusted application code.
"""
from collections.abc import Callable, Mapping, Iterable
from dataclasses import dataclass
import re
from typing import Any

from core.approvals import ApprovalAuthority, ApprovalReceipt
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


class ExecutionGateway:
    """Dispatch registered handlers only after policy + trusted approval.

    The ApprovalAuthority must remain private to trusted UI/controller code.
    Never pass model-generated text as a user approval receipt.
    """

    def __init__(
        self,
        handlers: Mapping[str, ActionHandler] | None = None,
        *,
        approval_authority: ApprovalAuthority | None = None,
    ) -> None:
        self._handlers: dict[str, ActionHandler] = {}
        self._approval_authority = approval_authority
        for action, handler in (handlers or {}).items():
            canonical = _canonical_action(action)
            if not canonical or not callable(handler):
                raise ValueError("Each handler needs a valid action and callable.")
            if not authorize_action(canonical, approved_action=canonical).allowed:
                raise ValueError(f"Action is not registered for execution: {canonical}")
            if canonical in self._handlers:
                raise ValueError(f"Duplicate action handler: {canonical}")
            self._handlers[canonical] = handler

    def execute(
        self,
        action: str,
        payload: Mapping[str, Any] | None = None,
        *,
        approval_receipt: ApprovalReceipt | None = None,
        auto_run: bool = False,
        auto_run_actions: Iterable[str] = (),
    ) -> ExecutionResult:
        """Run one handler only after read-only, Auto-Run, or receipt authorization."""
        if payload is not None and not isinstance(payload, Mapping):
            return ExecutionResult(False, "Action payload must be a mapping.")

        decision = authorize_action(action)
        authorized = decision.allowed

        if not authorized and auto_run:
            auto_decision = authorize_action(
                action,
                auto_run=True,
                auto_run_actions=auto_run_actions,
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
            return ExecutionResult(False, decision.reason)

        canonical = _canonical_action(action)
        handler = self._handlers.get(canonical)
        if handler is None:
            return ExecutionResult(False, "No trusted handler is registered for this action.")

        try:
            output = handler(payload or {})
        except Exception:
            return ExecutionResult(False, "The registered action handler failed.")

        return ExecutionResult(True, "Action executed after permission approval.", output)
