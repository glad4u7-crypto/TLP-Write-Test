import pytest

from core.approvals import ApprovalAuthority
from core.execution import ExecutionGateway
from core.multi_step_executor import (
    MultiStepTaskExecutor, TaskPlan, TaskPlanError, TaskStep, validate_task_plan,
)
from core.task_conditions import Condition, evaluate_condition


def test_leaf_comparisons_and_nested_boolean_groups():
    condition = Condition(all_of=(
        Condition(path="report.score", operator="gte", value=70),
        Condition(any_of=(
            Condition(path="report.status", operator="eq", value="ready"),
            Condition(path="report.override", operator="eq", value=True),
        )),
    ))
    result = evaluate_condition(condition, {"report": {"score": 82, "status": "ready"}})
    assert result.valid and result.matched


def test_missing_path_fails_closed_except_exists_operator():
    missing = evaluate_condition(
        Condition(path="user.email", operator="eq", value="x@example.com"), {}
    )
    exists = evaluate_condition(
        Condition(path="user.email", operator="exists", value=False), {}
    )
    assert missing.valid and not missing.matched
    assert exists.valid and exists.matched


def test_private_paths_and_unsupported_operators_are_invalid():
    private = evaluate_condition(Condition(path="_secret.token", operator="exists", value=True), {})
    operator = evaluate_condition(Condition(path="x", operator="exec", value="x"), {"x": "x"})
    assert not private.valid and not private.matched
    assert not operator.valid and not operator.matched


def test_condition_depth_and_node_budgets_fail_closed():
    node = Condition(path="x", operator="eq", value=1)
    for _ in range(10):
        node = Condition(all_of=(node,))
    result = evaluate_condition(node, {"x": 1})
    assert not result.valid and not result.matched


def test_non_json_context_rejected_without_running_user_code():
    class Hostile:
        def __eq__(self, other):
            raise AssertionError("must not execute")
    result = evaluate_condition(
        Condition(path="x", operator="eq", value=1), {"x": Hostile()}
    )
    assert not result.valid and not result.matched


def test_plan_validation_rejects_duplicate_ids_and_oversized_plans():
    with pytest.raises(TaskPlanError):
        validate_task_plan(TaskPlan("bad", (
            TaskStep("same", "inspect_repository", {}),
            TaskStep("same", "inspect_repository", {}),
        )))
    with pytest.raises(TaskPlanError):
        validate_task_plan(TaskPlan("large", tuple(
            TaskStep(str(i), "inspect_repository", {}) for i in range(26)
        )))


def test_multistep_executor_runs_ordered_steps_and_skips_false_condition():
    calls = []
    gateway = ExecutionGateway({
        "inspect_repository": lambda payload: calls.append(payload["name"]) or "ok"
    })
    plan = TaskPlan("ordered", (
        TaskStep("one", "inspect_repository", {"name": "one"}),
        TaskStep("skip", "inspect_repository", {"name": "skip"},
                 Condition(path="enabled", operator="eq", value=True)),
        TaskStep("two", "inspect_repository", {"name": "two"}),
    ))
    result = MultiStepTaskExecutor(gateway).run(plan, condition_context={"enabled": False})
    assert result.status == "succeeded"
    assert [step.status for step in result.steps] == ["succeeded", "skipped", "succeeded"]
    assert calls == ["one", "two"]


def test_multistep_stops_after_first_failed_action():
    calls = []
    authority = ApprovalAuthority()
    gateway = ExecutionGateway({
        "inspect_repository": lambda payload: calls.append(payload["n"]) or "ok"
    }, approval_authority=authority)
    plan = TaskPlan("stop-on-failure", (
        TaskStep("first", "inspect_repository", {"n": 1}),
        TaskStep("bad", "write_file", {"path": "x"}),
        TaskStep("never", "inspect_repository", {"n": 3}),
    ))
    result = MultiStepTaskExecutor(gateway).run(
        plan, condition_context={},
        request_approval=lambda _plan, action, payload, _tenant: authority.issue(action, payload),
    )
    assert result.status == "failed"
    assert [step.status for step in result.steps] == ["succeeded", "failed"]
    assert calls == [1]


def test_mutating_step_requires_exact_one_time_approval():
    authority = ApprovalAuthority()
    calls = []
    payload = {"path": "notes.txt", "content": "approved"}
    gateway = ExecutionGateway(
        {"write_file": lambda data: calls.append(data) or "saved"},
        approval_authority=authority,
    )
    plan = TaskPlan("approved-write", (TaskStep("write", "write_file", payload),))
    executor = MultiStepTaskExecutor(gateway)

    blocked = executor.run(plan, condition_context={})
    assert blocked.status == "blocked"
    assert calls == []

    receipt = authority.issue("write_file", payload)
    allowed = executor.run(
        plan, condition_context={},
        request_approval=lambda *_: receipt,
    )
    assert allowed.status == "succeeded"
    assert calls == [payload]


def test_invalid_condition_blocks_plan_before_any_later_step():
    calls = []
    gateway = ExecutionGateway({"inspect_repository": lambda payload: calls.append(payload)})
    plan = TaskPlan("bad-condition", (
        TaskStep("blocked", "inspect_repository", {},
                 Condition(path="_private", operator="exists", value=True)),
        TaskStep("later", "inspect_repository", {}),
    ))
    result = MultiStepTaskExecutor(gateway).run(plan, condition_context={})
    assert result.status == "blocked"
    assert calls == []
