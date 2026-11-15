import hashlib
import json

import pytest

from core.models import Task
from core.planner import (
    PlanStatus,
    PlanStep,
    StepCategory,
    TaskPlan,
    create_structured_plan,
    validate_task_intake,
)


def test_structured_plan_is_typed_and_deterministic():
    task = Task(description="  Review   the repository\n and summarize risks ")
    first = create_structured_plan(task)
    second = create_structured_plan(task)

    assert first == second
    assert first.status is PlanStatus.READY
    assert first.plan_id == second.plan_id
    assert first.task_description == "Review the repository and summarize risks"
    assert [step.step_id for step in first.steps] == [
        "step-01", "step-02", "step-03", "step-04"
    ]
    assert first.to_dict()["schema_version"] == "1.0"


def test_mutation_is_only_proposed_and_marked_for_separate_approval():
    plan = create_structured_plan(Task(description="Create a draft report"))
    proposed = plan.steps[2]

    assert plan.status is PlanStatus.READY
    assert proposed.category is StepCategory.PROPOSED_MUTATION
    assert proposed.requires_human_approval is True
    assert "no handler dispatch" in plan.safety_notes[1].lower()


@pytest.mark.parametrize("description", [
    "Pay the invoice",
    "Purchase this item",
    "Transfer money to another account",
    "Trade stock now",
    "Call the paid API provider",
])
def test_prohibited_intent_is_blocked(description):
    plan = create_structured_plan(Task(description=description))
    assert plan.status is PlanStatus.BLOCKED
    assert plan.steps == ()
    assert any("prohibited" in note for note in plan.safety_notes)


@pytest.mark.parametrize("description", ["do it", "fix that", "make it better"])
def test_ambiguous_deictic_request_requires_clarification(description):
    plan = create_structured_plan(Task(description=description))
    assert plan.status is PlanStatus.NEEDS_CLARIFICATION
    assert plan.steps == ()
    assert plan.clarification_questions


def test_intake_normalizes_whitespace_without_changing_words():
    result = validate_task_intake("  Review\n\tthese   files  ")
    assert result.accepted is True
    assert result.normalized_description == "Review these files"


@pytest.mark.parametrize("value", [None, 1, [], {}])
def test_intake_rejects_non_text(value):
    assert validate_task_intake(value).accepted is False


def test_intake_rejects_empty_and_control_characters():
    assert validate_task_intake("  ").accepted is False
    assert validate_task_intake("hello\x00world").accepted is False


def test_intake_enforces_maximum_length():
    result = validate_task_intake("x" * 4001)
    assert result.accepted is False
    assert "4000" in result.errors[0]


def test_plan_rejects_non_task_input():
    with pytest.raises(TypeError):
        create_structured_plan("not a Task")


def test_plan_serialization_has_no_runtime_timestamp():
    result = create_structured_plan(Task(description="Inspect repository")).to_dict()
    assert "created_at" not in result
    assert "timestamp" not in result

def test_plan_serialization_is_json_compatible():
    plan = create_structured_plan(Task(description="Inspect repository"))
    encoded = json.dumps(plan.to_dict(), sort_keys=True)
    assert '"status": "ready"' in encoded
    assert '"category": "read_only"' in encoded


def test_plan_schema_rejects_ready_state_without_steps():
    with pytest.raises(ValueError, match="Ready plans require steps"):
        TaskPlan(
            schema_version="1.0",
            plan_id="plan-" + hashlib.sha256(b"Inspect repository").hexdigest()[:16],
            task_description="Inspect repository",
            status=PlanStatus.READY,
            steps=(),
        )


def test_plan_step_rejects_mutation_without_human_approval():
    with pytest.raises(ValueError, match="Only proposed mutation"):
        PlanStep(
            step_id="step-01",
            title="Write file",
            purpose="Propose a file update",
            category=StepCategory.PROPOSED_MUTATION,
            expected_output="Draft",
            requires_human_approval=False,
        )


def test_intake_checks_raw_input_length_before_whitespace_normalization():
    result = validate_task_intake(" " * 4001)
    assert result.accepted is False
    assert "4000" in result.errors[0]
