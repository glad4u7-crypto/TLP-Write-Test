"""Permission-gated dispatch for explicitly registered agent actions.

This gateway does not provide shell, browser, network, or provider adapters.
Only trusted application code may register handlers, and every dispatch is
checked by the fail-closed policy before the handler is called.
"""
from collections.abc import Callable, Mapping, Iterable
from dataclasses import dataclass
import re
from typing import Any

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
    """Dispatch registered handlers only after action-specific authorization.

    No handlers are installed by default. Handler registration is an explicit
    trusted-code decision; this class does not create shell/network capabilities.
    """

    def __init__(
        self,
        handlers: Mapping[str, ActionHandler] | None = None,
    ) -> None:
        self._handlers: dict[str, ActionHandler] = {}
        for action, handler in (handlers or {}).items():
            canonical = _canonical_action(action)
            if not canonical or not callable(handler):
                raise ValueError("Each handler needs a valid action and callable.")
            # This validates the action against the same fail-closed registry.
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
        approved_action: str | None = None,
        auto_run: bool = False,
        auto_run_actions: Iterable[str] = (),
    ) -> ExecutionResult:
        """Run one registered action after the permission policy allows it."""
        decision = authorize_action(
            action,
            approved_action=approved_action,
            auto_run=auto_run,
            auto_run_actions=auto_run_actions,
        )
        if not decision.allowed:
            return ExecutionResult(False, decision.reason)

        canonical = _canonical_action(action)
        handler = self._handlers.get(canonical)
        if handler is None:
            return ExecutionResult(False, "No trusted handler is registered for this action.")

        if payload is not None and not isinstance(payload, Mapping):
            return ExecutionResult(False, "Action payload must be a mapping.")

        try:
            output = handler(payload or {})
        except Exception:
            # Avoid leaking internal exception details into the user-facing result.
            return ExecutionResult(False, "The registered action handler failed.")

        return ExecutionResult(True, "Action executed after permission approval.", output)
