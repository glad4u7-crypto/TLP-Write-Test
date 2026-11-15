import pytest

from core.execution_control import (
    CompletionVerifier, Condition, ConditionOperator, DispatchOutcomeUnknown,
    ExecutionControlError, ExecutionDeadline, MultiStepExecutor, RetryablePreDispatchError,
    SafeRetryPolicy, StepSpec, TimeoutExceeded, evaluate_condition,
)


def test_conditional_comparison_and_missing_path_fail_closed():
    yes = evaluate_condition(
        Condition("report.score", ConditionOperator.GTE, 80),
        {"report": {"score": 90}},
    )
    no = evaluate_condition(
        Condition("report.missing", ConditionOperator.EQ, 1),
        {"report": {"score": 90}},
    )
    assert yes.matched and yes.branch == "true"
    assert not no.matched and no.branch == "false"


def test_condition_uses_allowlisted_operators_and_no_expression_eval():
    with pytest.raises(ExecutionControlError):
        evaluate_condition(
            Condition("__import__('os').system('id')", ConditionOperator.TRUTHY),
            {},
        )


def test_numeric_comparison_rejects_boolean_and_strings():
    with pytest.raises(ExecutionControlError):
        evaluate_condition(Condition("value", ConditionOperator.GT, 1), {"value": True})


def test_multi_step_stops_after_first_failed_step():
    seen = []
    steps = [
        StepSpec("one", "inspect_repository", {}),
        StepSpec("two", "write_file", {"path": "note.txt"}),
        StepSpec("three", "inspect_repository", {}),
    ]

    def execute(step):
        seen.append(step.step_id)
        return step.step_id == "one"

    result = MultiStepExecutor().run(steps, execute)
    assert not result.succeeded
    assert result.completed == ("one",)
    assert result.failed_step == "two"
    assert seen == ["one", "two"]


def test_multi_step_rejects_duplicate_ids_and_unbounded_plans():
    executor = MultiStepExecutor(max_steps=2)
    with pytest.raises(ExecutionControlError):
        executor.run(
            [StepSpec("x", "inspect", {}), StepSpec("x", "inspect", {})],
            lambda _: True,
        )
    with pytest.raises(ExecutionControlError):
        executor.run(
            [StepSpec("1", "inspect", {}), StepSpec("2", "inspect", {}),
             StepSpec("3", "inspect", {})],
            lambda _: True,
        )


def test_multi_step_exception_fails_closed_without_running_later_steps():
    seen = []

    def execute(step):
        seen.append(step.step_id)
        if step.step_id == "a":
            raise RuntimeError("private detail")
        return True

    result = MultiStepExecutor().run(
        [StepSpec("a", "inspect", {}), StepSpec("b", "inspect", {})], execute
    )
    assert not result.succeeded
    assert result.failed_step == "a"
    assert seen == ["a"]


def test_deadline_expiry_before_dispatch_is_safe_to_classify():
    clock = {"now": 10.0}
    deadline = ExecutionDeadline(2, clock=lambda: clock["now"])
    clock["now"] = 12.0
    with pytest.raises(TimeoutExceeded) as exc:
        deadline.mark_dispatch_started()
    assert exc.value.side_effect_may_have_completed is False


def test_deadline_expiry_after_dispatch_marks_outcome_uncertain():
    clock = {"now": 10.0}
    deadline = ExecutionDeadline(2, clock=lambda: clock["now"])
    deadline.mark_dispatch_started()
    clock["now"] = 12.0
    with pytest.raises(TimeoutExceeded) as exc:
        deadline.check()
    assert exc.value.side_effect_may_have_completed is True


def test_retry_policy_retries_only_pre_dispatch_and_is_bounded():
    attempts = []
    policy = SafeRetryPolicy(max_attempts=3, backoff_seconds=0, sleeper=lambda _: None)

    def operation(attempt):
        attempts.append(attempt)
        if attempt < 3:
            raise RetryablePreDispatchError("not dispatched")
        return "ok"

    result = policy.run(operation)
    assert result.value == "ok"
    assert result.attempts == 3
    assert attempts == [1, 2, 3]


def test_retry_policy_never_retries_unknown_dispatch_outcome():
    attempts = []
    policy = SafeRetryPolicy(max_attempts=3)

    def operation(attempt):
        attempts.append(attempt)
        raise DispatchOutcomeUnknown("unknown")

    with pytest.raises(DispatchOutcomeUnknown):
        policy.run(operation)
    assert attempts == [1]


def test_completion_verifier_reports_match_mismatch_and_callback_failure():
    verifier = CompletionVerifier()
    expected = {"status": "saved"}
    observed = {"status": "saved"}
    good = verifier.verify(
        expected=expected, observed=observed,
        check=lambda e, o: e["status"] == o["status"],
    )
    bad = verifier.verify(
        expected=expected, observed={"status": "missing"},
        check=lambda e, o: e["status"] == o["status"],
    )
    error = verifier.verify(
        expected=expected, observed=observed,
        check=lambda *_: (_ for _ in ()).throw(RuntimeError()),
    )
    assert good.verified
    assert not bad.verified
    assert not error.verified
