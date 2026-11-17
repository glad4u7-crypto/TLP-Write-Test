import pytest
from core.models import Task, TaskStatus
from core.planner import create_plan
from core.safety import authorize_action

def test_task_rejects_empty_description():
    with pytest.raises(ValueError):
        Task(description="   ")

def test_task_defaults_to_draft():
    assert Task(description="Inspect repository").status is TaskStatus.DRAFT

def test_planner_returns_ordered_safe_steps():
    plan = create_plan(Task(description="Review a Python project"))
    assert len(plan) == 4
    assert "Run appropriate checks and report evidence." in plan

def test_read_only_action_is_allowed():
    assert authorize_action("inspect").allowed is True

def test_mutation_requires_approval():
    decision = authorize_action("delete_file")
    assert decision.allowed is False
    assert "approval" in decision.reason

def test_approved_mutation_is_allowed():
    assert authorize_action("write_file", approved=True).allowed is True
