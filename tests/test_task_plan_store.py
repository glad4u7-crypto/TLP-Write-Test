from __future__ import annotations

import json

import pytest

from core.memory import SQLiteMemoryStore
from core.models import Task
from core.planner import create_structured_plan, task_plan_from_dict
from core.storage import TenantKey


OWNER = TenantKey("local://apaa-personal", "local-owner")
OTHER = TenantKey("local://apaa-personal", "different-owner")


def _ready_plan():
    return create_structured_plan(Task(
        description="Review the project files and prepare a safe implementation summary."
    ))


def test_task_plan_requires_explicit_owner_consent(tmp_path):
    store = SQLiteMemoryStore(tmp_path / "memory.sqlite3")
    plan = _ready_plan()
    with pytest.raises(PermissionError, match="consent"):
        store.save_task_plan(
            OWNER, project_id="project-1", plan_id=plan.plan_id,
            task_description=plan.task_description, plan=plan.to_dict(),
        )
    assert store.list_task_plans(OWNER, project_id="project-1") == []


def test_task_plan_persists_across_store_restart_and_revalidates(tmp_path):
    database = tmp_path / "memory.sqlite3"
    plan = _ready_plan()
    first = SQLiteMemoryStore(database)
    saved = first.save_task_plan(
        OWNER, project_id="project-1", plan_id=plan.plan_id,
        task_description=plan.task_description, plan=plan.to_dict(), consent=True,
    )

    restarted = SQLiteMemoryStore(database)
    records = restarted.list_task_plans(OWNER, project_id="project-1")
    assert len(records) == 1
    assert records[0].saved_plan_id == saved.saved_plan_id
    restored = task_plan_from_dict(json.loads(records[0].plan_json))
    assert restored == plan
    assert restored.status.value == "ready"


def test_task_plans_are_isolated_by_owner_and_project(tmp_path):
    store = SQLiteMemoryStore(tmp_path / "memory.sqlite3")
    plan = _ready_plan()
    store.save_task_plan(
        OWNER, project_id="project-1", plan_id=plan.plan_id,
        task_description=plan.task_description, plan=plan.to_dict(), consent=True,
    )
    assert store.list_task_plans(OTHER, project_id="project-1") == []
    assert store.list_task_plans(OWNER, project_id="project-2") == []


def test_task_plan_rejects_mismatched_snapshot_and_secret_like_content(tmp_path):
    store = SQLiteMemoryStore(tmp_path / "memory.sqlite3")
    plan = _ready_plan()
    wrong = plan.to_dict()
    wrong["task_description"] = "Different description"
    with pytest.raises(ValueError, match="does not match"):
        store.save_task_plan(
            OWNER, project_id="project-1", plan_id=plan.plan_id,
            task_description=plan.task_description, plan=wrong, consent=True,
        )

    secret_like = plan.to_dict()
    secret_like["task_description"] = "password=supersecret"
    secret_like["plan_id"] = plan.plan_id
    with pytest.raises(ValueError):
        store.save_task_plan(
            OWNER, project_id="project-1", plan_id=plan.plan_id,
            task_description=plan.task_description, plan=secret_like, consent=True,
        )


def test_task_plan_snapshot_parser_rejects_tampered_step_approval_flag():
    plan = _ready_plan().to_dict()
    plan["steps"][2]["requires_human_approval"] = False
    with pytest.raises(ValueError, match="approval flag"):
        task_plan_from_dict(plan)


def test_task_plan_delete_requires_consent_and_is_tenant_scoped(tmp_path):
    store = SQLiteMemoryStore(tmp_path / "memory.sqlite3")
    plan = _ready_plan()
    store.save_task_plan(
        OWNER, project_id="project-1", plan_id=plan.plan_id,
        task_description=plan.task_description, plan=plan.to_dict(), consent=True,
    )
    with pytest.raises(PermissionError):
        store.delete_task_plan(
            OWNER, project_id="project-1", plan_id=plan.plan_id,
        )
    assert not store.delete_task_plan(
        OTHER, project_id="project-1", plan_id=plan.plan_id, consent=True,
    )
    assert store.delete_task_plan(
        OWNER, project_id="project-1", plan_id=plan.plan_id, consent=True,
    )
