"""Bounded reliability primitives for trusted task controllers.

Timeouts are cooperative: Python cannot safely kill a running handler thread.
Retries are permitted only for failures proven to occur before dispatch. Once
dispatch may have started, the outcome is uncertain and must never be retried
automatically. Completion checks are read-only callbacks.
"""
from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import time
from typing import Any, Callable, Mapping


MAX_TIMEOUT_SECONDS = 300
MAX_ATTEMPTS = 3


class TimeoutExceeded(TimeoutError):
    """The task's cooperative execution budget has expired."""


class DispatchStage(str, Enum):
    PRE_DISPATCH = "pre_dispatch"
    DISPATCH_STARTED = "dispatch_started"
    OUTCOME_UNKNOWN = "outcome_unknown"


class ReliabilityStatus(str, Enum):
    COMPLETED = "completed"
    TIMED_OUT = "timed_out"
    FAILED = "failed"
    NEEDS_MANUAL_REVIEW = "needs_manual_review"
    VERIFICATION_FAILED = "verification_failed"


@dataclass(frozen=True)
class ExecutionBudget:
    deadline: float

    @classmethod
    def start(cls, timeout_seconds: float, *, clock: Callable[[], float] = time.monotonic) -> "ExecutionBudget":
        if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float)):
            raise ValueError("timeout_seconds must be a number.")
        if not 0 < timeout_seconds <= MAX_TIMEOUT_SECONDS:
            raise ValueError(f"timeout_seconds must be greater than 0 and at most {MAX_TIMEOUT_SECONDS}.")
        return cls(clock() + float(timeout_seconds))

    def remaining(self, *, clock: Callable[[], float] = time.monotonic) -> float:
        return max(0.0, self.deadline - clock())

    def check(self, *, clock: Callable[[], float] = time.monotonic) -> None:
        if clock() >= self.deadline:
            raise TimeoutExceeded("Execution budget expired; no further step may begin.")


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 1

    def __post_init__(self) -> None:
        if type(self.max_attempts) is not int or not 1 <= self.max_attempts <= MAX_ATTEMPTS:
            raise ValueError(f"max_attempts must be between 1 and {MAX_ATTEMPTS}.")


@dataclass(frozen=True)
class AttemptOutcome:
    value: Any
    error: str
    stage: DispatchStage
    attempts: int


@dataclass(frozen=True)
class CompletionEvidence:
    verified: bool
    expected_digest: str
    observed_digest: str
    reason: str


@dataclass(frozen=True)
class ReliabilityResult:
    status: ReliabilityStatus
    attempts: int
    value: Any = None
    reason: str = ""
    evidence: CompletionEvidence | None = None


def run_with_retry(
    operation: Callable[[ExecutionBudget], AttemptOutcome],
    *,
    budget: ExecutionBudget,
    policy: RetryPolicy = RetryPolicy(),
    clock: Callable[[], float] = time.monotonic,
) -> AttemptOutcome:
    """Retry only explicitly classified pre-dispatch failures within budget."""
    if not callable(operation):
        raise TypeError("operation must be callable.")
    last: AttemptOutcome | None = None
    for attempt in range(1, policy.max_attempts + 1):
        budget.check(clock=clock)
        try:
            outcome = operation(budget)
        except TimeoutExceeded:
            raise
        except Exception as exc:
            # An unclassified exception may have occurred during dispatch.
            return AttemptOutcome(None, type(exc).__name__, DispatchStage.OUTCOME_UNKNOWN, attempt)
        if not isinstance(outcome, AttemptOutcome):
            raise TypeError("operation must return AttemptOutcome.")
        last = AttemptOutcome(outcome.value, outcome.error, outcome.stage, attempt)
        if not outcome.error:
            return last
        if outcome.stage is not DispatchStage.PRE_DISPATCH:
            return last
        if attempt >= policy.max_attempts:
            return last
    assert last is not None
    return last


def _canonical_digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def verify_completion(
    expected: Any,
    read_observation: Callable[[], Any],
) -> CompletionEvidence:
    """Compare canonical JSON evidence using a read-only observation callback."""
    if not callable(read_observation):
        raise TypeError("read_observation must be callable.")
    try:
        expected_digest = _canonical_digest(expected)
        observed = read_observation()
        observed_digest = _canonical_digest(observed)
    except Exception as exc:
        return CompletionEvidence(False, "", "", f"Read-only completion check failed: {type(exc).__name__}.")
    matched = expected_digest == observed_digest
    return CompletionEvidence(
        matched,
        expected_digest,
        observed_digest,
        "Observed state matches expected state." if matched else "Observed state does not match expected state.",
    )


def finalize_result(
    outcome: AttemptOutcome,
    *,
    expected_completion: Any | None = None,
    read_observation: Callable[[], Any] | None = None,
) -> ReliabilityResult:
    """Require explicit evidence when a completion observation is requested."""
    if outcome.stage is DispatchStage.OUTCOME_UNKNOWN:
        return ReliabilityResult(
            ReliabilityStatus.NEEDS_MANUAL_REVIEW, outcome.attempts,
            reason="Dispatch outcome is unknown; automatic retry is prohibited.",
        )
    if outcome.error:
        return ReliabilityResult(ReliabilityStatus.FAILED, outcome.attempts, reason=outcome.error)
    if expected_completion is None and read_observation is None:
        return ReliabilityResult(ReliabilityStatus.COMPLETED, outcome.attempts, value=outcome.value, reason="Operation returned successfully; no external state verification was requested.")
    if expected_completion is None or read_observation is None:
        return ReliabilityResult(ReliabilityStatus.VERIFICATION_FAILED, outcome.attempts, value=outcome.value, reason="Both expected completion data and a read-only observer are required.")
    evidence = verify_completion(expected_completion, read_observation)
    if not evidence.verified:
        return ReliabilityResult(ReliabilityStatus.VERIFICATION_FAILED, outcome.attempts, value=outcome.value, reason=evidence.reason, evidence=evidence)
    return ReliabilityResult(ReliabilityStatus.COMPLETED, outcome.attempts, value=outcome.value, reason=evidence.reason, evidence=evidence)
