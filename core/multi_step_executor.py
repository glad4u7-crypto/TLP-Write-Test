"""Bounded multi-step task plans dispatched through the trusted gateway only."""
from collections.abc import Callable, Mapping
from dataclasses import dataclass
import json
from typing import Any

from core.approvals import ApprovalReceipt
from core.execution import ExecutionGateway, ExecutionResult
from core.safety import authorize_action
from core.task_conditions import Condition, evaluate_condition

MAX_PLAN_STEPS = 25
MAX_STEP_ID_LENGTH = 64
MAX_STEP_PAYLOAD_BYTES = 32768


@dataclass(frozen=True)
class TaskStep:
    step_id: str
    action: str
    payload: Mapping[str, Any]
    condition: Condition | None = None


@dataclass(frozen=True)
class TaskPlan:
    plan_id: str
    steps: tuple[TaskStep, ...]


@dataclass(frozen=True)
class StepResult:
    step_id: str
    status: str
    reason: str
    execution: ExecutionResult | None = None


@dataclass(frozen=True)
class PlanResult:
    plan_id: str
    status: str
    steps: tuple[StepResult, ...]
    reason: str


ApprovalProvider = Callable[[str, str, Mapping[str, Any]], ApprovalReceipt | None]


class TaskPlanError(ValueError):
    """Raised when a plan violates its structural or size contract."""


def validate_task_plan(plan: TaskPlan) -> None:
    if not isinstance(plan, TaskPlan):
        raise TaskPlanError("plan must be a TaskPlan.")
    if not isinstance(plan.plan_id, str) or not plan.plan_id.strip() or len(plan.plan_id) > 128:
        raise TaskPlanError("plan_id must be non-empty text of at most 128 characters.")
    if type(plan.steps) is not tuple or not 1 <= len(plan.steps) <= MAX_PLAN_STEPS:
        raise TaskPlanError(f"A plan must contain 1 to {MAX_PLAN_STEPS} steps.")
    seen: set[str] = set()
    for step in plan.steps:
        if not isinstance(step, TaskStep):
            raise TaskPlanError("Every plan entry must be a TaskStep.")
        if (
            not isinstance(step.step_id, str) or not step.step_id.strip()
            or len(step.step_id) > MAX_STEP_ID_LENGTH
            or step.step_id in seen
        ):
            raise TaskPlanError("Step IDs must be unique non-empty text of at most 64 characters.")
        seen.add(step.step_id)
        if not isinstance(step.action, str) or not step.action.strip() or len(step.action) > 128:
            raise TaskPlanError("Every step requires a valid action identifier.")
        if type(step.payload) is not dict:
            raise TaskPlanError("Step payloads must be plain dictionaries.")
        try:
            encoded = json.dumps(
                step.payload, sort_keys=True, separators=(",", ":"),
                ensure_ascii=False, allow_nan=False,
            ).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise TaskPlanError("Step payload must contain JSON-compatible values.") from exc
        if len(encoded) > MAX_STEP_PAYLOAD_BYTES:
            raise TaskPlanError("Step payload exceeds the 32 KiB limit.")
        if step.condition is not None and not isinstance(step.condition, Condition):
            raise TaskPlanError("Step condition must be a Condition or None.")


class MultiStepTaskExecutor:
    """Execute a finite ordered plan; stop at the first failed or blocked step.

    This executor has no loop, dynamic code, retry, rollback, or handler fallback.
    Conditions see only the caller-supplied JSON context, never prior handler
    output. Every side effect continues through ExecutionGateway.
    """

    def __init__(self, gateway: ExecutionGateway) -> None:
        if not isinstance(gateway, ExecutionGateway):
            raise TypeError("gateway must be an ExecutionGateway.")
        self._gateway = gateway

    def run(
        self,
        plan: TaskPlan,
        *,
        condition_context: Mapping[str, Any],
        request_approval: ApprovalProvider | None = None,
    ) -> PlanResult:
        validate_task_plan(plan)
        if type(condition_context) is not dict:
            raise TaskPlanError("condition_context must be a plain dictionary.")
        if request_approval is not None and not callable(request_approval):
            raise TypeError("request_approval must be a trusted callable.")

        results: list[StepResult] = []
        for step in plan.steps:
            if step.condition is not None:
                condition_result = evaluate_condition(step.condition, condition_context)
                if not condition_result.valid:
                    results.append(StepResult(step.step_id, "blocked", condition_result.reason))
                    return PlanResult(plan.plan_id, "blocked", tuple(results), "Invalid condition; plan stopped.")
                if not condition_result.matched:
                    results.append(StepResult(step.step_id, "skipped", "Condition did not match."))
                    continue

            receipt = None
            decision = authorize_action(step.action)
            if not decision.allowed:
                if request_approval is None:
                    results.append(StepResult(step.step_id, "blocked", "Approval is required but no trusted approval provider is available."))
                    return PlanResult(plan.plan_id, "blocked", tuple(results), "Approval required; plan stopped.")
                try:
                    receipt = request_approval(plan.plan_id, step.action, step.payload)
                except Exception:
                    results.append(StepResult(step.step_id, "blocked", "Trusted approval provider failed."))
                    return PlanResult(plan.plan_id, "blocked", tuple(results), "Approval provider failed; plan stopped.")
                if not isinstance(receipt, ApprovalReceipt):
                    results.append(StepResult(step.step_id, "blocked", "No valid one-time approval receipt was supplied."))
                    return PlanResult(plan.plan_id, "blocked", tuple(results), "Approval unavailable; plan stopped.")

            execution = self._gateway.execute(
                step.action, step.payload, approval_receipt=receipt,
            )
            if not execution.executed:
                results.append(StepResult(step.step_id, "failed", execution.reason, execution))
                return PlanResult(plan.plan_id, "failed", tuple(results), "A step failed; remaining steps were not run.")
            results.append(StepResult(step.step_id, "succeeded", execution.reason, execution))

        status = "succeeded" if all(item.status in {"succeeded", "skipped"} for item in results) else "failed"
        return PlanResult(plan.plan_id, status, tuple(results), "Plan completed without automatic retries.")
