import pytest

from core.execution_reliability import (
    AttemptOutcome, DispatchStage, ExecutionBudget, ReliabilityStatus,
    RetryPolicy, TimeoutExceeded, finalize_result, run_with_retry,
    verify_completion,
)


def test_budget_expires_and_prevents_next_step():
    budget = ExecutionBudget.start(0.001)
    import time
    time.sleep(0.003)
    with pytest.raises(TimeoutExceeded):
        budget.check()


@pytest.mark.parametrize("value", [0, -1, 301, True, "2"])
def test_timeout_bounds_reject_invalid_values(value):
    with pytest.raises(ValueError):
        ExecutionBudget.start(value)


@pytest.mark.parametrize("value", [0, -1, 4, True])
def test_retry_attempt_limit_is_bounded(value):
    with pytest.raises(ValueError):
        RetryPolicy(value)


def test_retry_repeats_only_pre_dispatch_failure():
    calls = []
    def operation(budget):
        calls.append(1)
        if len(calls) == 1:
            return AttemptOutcome(None, "temporary", DispatchStage.PRE_DISPATCH, 1)
        return AttemptOutcome("ok", "", DispatchStage.DISPATCH_STARTED, 2)
    result = run_with_retry(operation, budget=ExecutionBudget.start(5), policy=RetryPolicy(3))
    assert len(calls) == 2
    assert result.value == "ok" and result.attempts == 2


@pytest.mark.parametrize("stage", [DispatchStage.DISPATCH_STARTED, DispatchStage.OUTCOME_UNKNOWN])
def test_never_retries_after_dispatch_may_have_started(stage):
    calls = []
    def operation(budget):
        calls.append(1)
        return AttemptOutcome(None, "uncertain", stage, 1)
    result = run_with_retry(operation, budget=ExecutionBudget.start(5), policy=RetryPolicy(3))
    assert len(calls) == 1
    assert result.attempts == 1


def test_unclassified_exception_is_treated_as_unknown_and_not_retried():
    calls = []
    def operation(budget):
        calls.append(1)
        raise RuntimeError("could be after dispatch")
    result = run_with_retry(operation, budget=ExecutionBudget.start(5), policy=RetryPolicy(3))
    assert len(calls) == 1
    assert result.stage is DispatchStage.OUTCOME_UNKNOWN


def test_retry_stops_when_budget_expires():
    budget = ExecutionBudget.start(0.000001)
    import time
    time.sleep(0.002)
    calls = []
    with pytest.raises(TimeoutExceeded):
        run_with_retry(lambda b: calls.append(1), budget=budget, policy=RetryPolicy(3))
    assert calls == []


def test_retry_returns_last_pre_dispatch_failure_at_limit():
    calls = []
    result = run_with_retry(
        lambda b: (calls.append(1) or AttemptOutcome(None, "offline", DispatchStage.PRE_DISPATCH, 0)),
        budget=ExecutionBudget.start(5), policy=RetryPolicy(2),
    )
    assert len(calls) == 2 and result.attempts == 2 and result.error == "offline"


def test_completion_verification_matches_canonical_json():
    evidence = verify_completion({"b": 2, "a": 1}, lambda: {"a": 1, "b": 2})
    assert evidence.verified
    assert evidence.expected_digest == evidence.observed_digest


def test_completion_verification_detects_mismatch():
    evidence = verify_completion({"state": "done"}, lambda: {"state": "pending"})
    assert not evidence.verified


def test_completion_observer_failure_fails_closed():
    evidence = verify_completion({}, lambda: (_ for _ in ()).throw(OSError()))
    assert not evidence.verified
    assert "OSError" in evidence.reason


def test_observer_must_be_callable():
    with pytest.raises(TypeError):
        verify_completion({}, None)


def test_unknown_dispatch_outcome_requires_manual_review():
    result = finalize_result(AttemptOutcome(None, "unknown", DispatchStage.OUTCOME_UNKNOWN, 1))
    assert result.status is ReliabilityStatus.NEEDS_MANUAL_REVIEW


def test_success_requires_matching_completion_evidence_when_requested():
    outcome = AttemptOutcome("saved", "", DispatchStage.DISPATCH_STARTED, 1)
    result = finalize_result(outcome, expected_completion={"saved": True}, read_observation=lambda: {"saved": True})
    assert result.status is ReliabilityStatus.COMPLETED
    assert result.evidence and result.evidence.verified


def test_mismatched_completion_evidence_is_not_success():
    outcome = AttemptOutcome("saved", "", DispatchStage.DISPATCH_STARTED, 1)
    result = finalize_result(outcome, expected_completion={"saved": True}, read_observation=lambda: {"saved": False})
    assert result.status is ReliabilityStatus.VERIFICATION_FAILED


def test_partial_verification_configuration_fails_closed():
    outcome = AttemptOutcome("saved", "", DispatchStage.DISPATCH_STARTED, 1)
    result = finalize_result(outcome, expected_completion={"saved": True})
    assert result.status is ReliabilityStatus.VERIFICATION_FAILED


def test_plain_success_without_requested_observation_is_reported_as_unverified_return():
    outcome = AttemptOutcome("ok", "", DispatchStage.DISPATCH_STARTED, 1)
    result = finalize_result(outcome)
    assert result.status is ReliabilityStatus.COMPLETED
    assert "no external state verification" in result.reason
