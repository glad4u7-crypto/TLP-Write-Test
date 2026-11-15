"""Bounded execution-control and reliability primitives for APAA S08.

These primitives coordinate decisions; they do not create permissions, register
handlers, or bypass ExecutionGateway. No eval/exec, background worker, shell,
network adapter, or automatic retry after an uncertain side effect is provided.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import time
from collections.abc import Callable, Mapping, Sequence
from typing import Any


MAX_CONDITION_DEPTH = 8
MAX_STEPS = 25
MAX_RETRY_ATTEMPTS = 3
MAX_TIMEOUT_SECONDS = 300.0


class ExecutionControlError(ValueError):
    """Base error for invalid execution-control requests."""


class ConditionOperator(str, Enum):
    EQ = "eq"
    NE = "ne"
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"
    IN = "in"
    CONTAINS = "contains"
    EXISTS = "exists"
    TRUTHY = "truthy"


@dataclass(frozen=True)
class Condition:
    path: str
    operator: ConditionOperator
    expected: Any = None


@dataclass(frozen=True)
class ConditionalDecision:
    matched: bool
    branch: str
    observed: Any = None


def _resolve_path(context: Mapping[str, Any], path: str) -> tuple[bool, Any]:
    if not isinstance(path, str) or not path or len(path) > 256:
        raise ExecutionControlError("Condition path must contain 1 to 256 characters.")
    parts = path.split(".")
    if len(parts) > MAX_CONDITION_DEPTH or any(not p or len(p) > 64 for p in parts):
        raise ExecutionControlError("Condition path exceeds its depth or segment limit.")
    current: Any = context
    for part in parts:
        if not isinstance(current, Mapping) or part not in current:
            return False, None
        current = current[part]
    return True, current


def evaluate_condition(condition: Condition, context: Mapping[str, Any]) -> ConditionalDecision:
    """Evaluate a small allowlisted predicate; never evaluates source code."""
    if not isinstance(condition, Condition) or not isinstance(context, Mapping):
        raise TypeError("Condition and mapping context are required.")
    if not isinstance(condition.operator, ConditionOperator):
        raise ExecutionControlError("Unknown condition operator.")
    exists, actual = _resolve_path(context, condition.path)
    op = condition.operator
    if op is ConditionOperator.EXISTS:
        matched = exists
    elif not exists:
        matched = False
    elif op is ConditionOperator.TRUTHY:
        matched = bool(actual)
    elif op is ConditionOperator.EQ:
        matched = type(actual) is type(condition.expected) and actual == condition.expected
    elif op is ConditionOperator.NE:
        matched = not (type(actual) is type(condition.expected) and actual == condition.expected)
    elif op in (ConditionOperator.GT, ConditionOperator.GTE, ConditionOperator.LT, ConditionOperator.LTE):
        if type(actual) not in (int, float) or type(condition.expected) not in (int, float):
            raise ExecutionControlError("Ordered comparisons require numeric values.")
        if op is ConditionOperator.GT:
            matched = actual > condition.expected
        elif op is ConditionOperator.GTE:
            matched = actual >= condition.expected
        elif op is ConditionOperator.LT:
            matched = actual < condition.expected
        else:
            matched = actual <= condition.expected
    elif op is ConditionOperator.IN:
        if not isinstance(condition.expected, (tuple, list, set, frozenset)):
            raise ExecutionControlError("'in' expects a bounded collection.")
        matched = actual in condition.expected
    elif op is ConditionOperator.CONTAINS:
        if not isinstance(actual, (str, tuple, list, set, frozenset, Mapping)):
            raise ExecutionControlError("'contains' requires a collection or text value.")
        matched = condition.expected in actual
    else:
        raise ExecutionControlError("Unsupported condition operator.")
    return ConditionalDecision(bool(matched), "true" if matched else "false", actual if exists else None)


@dataclass(frozen=True)
class StepSpec:
    step_id: str
    action: str
    payload: Mapping[str, Any]


@dataclass(frozen=True)
class StepOutcome:
    step_id: str
    succeeded: bool
    reason: str


@dataclass(frozen=True)
class MultiStepResult:
    completed: tuple[str, ...]
    failed_step: str | None
    outcomes: tuple[StepOutcome, ...]
    succeeded: bool


class MultiStepExecutor:
    """Run a bounded linear plan through a caller-supplied trusted gateway adapter.

    The callback must delegate to ExecutionGateway. This class never invokes
    arbitrary handlers itself and stops at the first failed/uncertain outcome.
    """
    def __init__(self, *, max_steps: int = MAX_STEPS) -> None:
        if type(max_steps) is not int or not 1 <= max_steps <= MAX_STEPS:
            raise ValueError(f"max_steps must be between 1 and {MAX_STEPS}.")
        self._max_steps = max_steps

    def run(
        self,
        steps: Sequence[StepSpec],
        execute_step: Callable[[StepSpec], Any],
    ) -> MultiStepResult:
        if not isinstance(steps, (tuple, list)) or not 1 <= len(steps) <= self._max_steps:
            raise ExecutionControlError("Plan must contain a bounded, non-empty step list.")
        if not callable(execute_step):
            raise TypeError("execute_step must be a trusted callable.")
        seen: set[str] = set()
        for step in steps:
            if not isinstance(step, StepSpec):
                raise TypeError("Every plan item must be a StepSpec.")
            if (not isinstance(step.step_id, str) or not step.step_id
                    or len(step.step_id) > 64 or step.step_id in seen):
                raise ExecutionControlError("Step IDs must be unique, non-empty and bounded.")
            if not isinstance(step.action, str) or not step.action.strip() or len(step.action) > 128:
                raise ExecutionControlError("Each step needs a bounded action identifier.")
            if not isinstance(step.payload, Mapping):
                raise TypeError("Step payload must be a mapping.")
            seen.add(step.step_id)

        completed: list[str] = []
        outcomes: list[StepOutcome] = []
        for step in steps:
            try:
                result = execute_step(step)
                ok = bool(getattr(result, "executed", result if isinstance(result, bool) else False))
                reason = str(getattr(result, "reason", "step completed" if ok else "step blocked"))[:300]
            except Exception as exc:
                ok, reason = False, f"step raised {type(exc).__name__}"
            outcomes.append(StepOutcome(step.step_id, ok, reason))
            if not ok:
                return MultiStepResult(tuple(completed), step.step_id, tuple(outcomes), False)
            completed.append(step.step_id)
        return MultiStepResult(tuple(completed), None, tuple(outcomes), True)


class TimeoutExceeded(TimeoutError):
    """Cooperative deadline elapsed; a dispatched side effect may have completed."""
    def __init__(self, *, side_effect_may_have_completed: bool) -> None:
        super().__init__("Execution deadline exceeded.")
        self.side_effect_may_have_completed = side_effect_may_have_completed


class ExecutionDeadline:
    """Cooperative deadline token; Python threads are never force-killed."""
    def __init__(self, timeout_seconds: float, *, clock: Callable[[], float] = time.monotonic) -> None:
        if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float)):
            raise ValueError("timeout_seconds must be numeric.")
        if not 0 < timeout_seconds <= MAX_TIMEOUT_SECONDS:
            raise ValueError(f"timeout_seconds must be greater than 0 and at most {MAX_TIMEOUT_SECONDS}.")
        self._clock = clock
        self._expires = clock() + float(timeout_seconds)
        self._dispatch_started = False

    @property
    def remaining(self) -> float:
        return max(0.0, self._expires - self._clock())

    def mark_dispatch_started(self) -> None:
        self.check()
        self._dispatch_started = True

    def check(self) -> None:
        if self._clock() >= self._expires:
            raise TimeoutExceeded(side_effect_may_have_completed=self._dispatch_started)


class RetryablePreDispatchError(RuntimeError):
    """A failure proven to occur before any side effect was dispatched."""


class DispatchOutcomeUnknown(RuntimeError):
    """The side-effect outcome is uncertain and MUST NOT be retried automatically."""


@dataclass(frozen=True)
class RetryResult:
    value: Any
    attempts: int


class SafeRetryPolicy:
    """Bounded retry for explicitly classified pre-dispatch failures only."""
    def __init__(
        self,
        *,
        max_attempts: int = 1,
        backoff_seconds: float = 0.0,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        if type(max_attempts) is not int or not 1 <= max_attempts <= MAX_RETRY_ATTEMPTS:
            raise ValueError(f"max_attempts must be between 1 and {MAX_RETRY_ATTEMPTS}.")
        if isinstance(backoff_seconds, bool) or not isinstance(backoff_seconds, (int, float)):
            raise ValueError("backoff_seconds must be numeric.")
        if not 0 <= backoff_seconds <= 30:
            raise ValueError("backoff_seconds must be between 0 and 30.")
        if not callable(sleeper):
            raise TypeError("sleeper must be callable.")
        self.max_attempts = max_attempts
        self.backoff_seconds = float(backoff_seconds)
        self._sleeper = sleeper

    def run(self, operation: Callable[[int], Any]) -> RetryResult:
        if not callable(operation):
            raise TypeError("operation must be callable.")
        for attempt in range(1, self.max_attempts + 1):
            try:
                return RetryResult(operation(attempt), attempt)
            except RetryablePreDispatchError:
                if attempt >= self.max_attempts:
                    raise
                if self.backoff_seconds:
                    self._sleeper(min(30.0, self.backoff_seconds * (2 ** (attempt - 1))))
            except DispatchOutcomeUnknown:
                raise
        raise RuntimeError("Unreachable retry state.")


@dataclass(frozen=True)
class CompletionReport:
    verified: bool
    reason: str
    evidence: str | None = None


class CompletionVerifier:
    """Read-only completion check; verifier callback must not perform mutations."""
    def verify(
        self,
        *,
        expected: Mapping[str, Any],
        observed: Mapping[str, Any],
        check: Callable[[Mapping[str, Any], Mapping[str, Any]], bool],
    ) -> CompletionReport:
        if not isinstance(expected, Mapping) or not isinstance(observed, Mapping):
            raise TypeError("Expected and observed values must be mappings.")
        if not callable(check):
            raise TypeError("A trusted read-only check callback is required.")
        try:
            verified = check(expected, observed)
        except Exception as exc:
            return CompletionReport(False, f"verification failed: {type(exc).__name__}")
        if type(verified) is not bool:
            return CompletionReport(False, "verification callback must return bool")
        return CompletionReport(
            verified,
            "completion evidence matched" if verified else "completion evidence did not match",
        )
