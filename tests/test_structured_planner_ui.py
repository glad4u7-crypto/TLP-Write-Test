from pathlib import Path

from streamlit.testing.v1 import AppTest

from core.planner import PlanStatus


def _app():
    return AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py")


def _prepare(app, description):
    # Text area 0 is the project description; text area 1 is the task workspace.
    app.text_area[1].set_value(description)
    app.run()
    assert not app.exception
    matches = [button for button in app.button if button.label == "Prepare structured plan"]
    assert len(matches) == 1
    matches[0].click().run()
    assert not app.exception


def test_ready_plan_is_rendered_as_read_only_structured_steps():
    app = _app().run()
    assert not app.exception
    _prepare(app, "Review the repository and summarize risks")

    plan = app.session_state["structured_task_plan"]
    assert plan.status is PlanStatus.READY
    assert len(plan.steps) == 4
    assert any("Structured plan review" in item.value for item in app.subheader)
    assert any("step-01" in item.value for item in app.markdown)
    assert any("cannot approve, dispatch, or execute" in item.value for item in app.caption)
    assert app.session_state["execution_gateway"].audit_events == ()


def test_mutation_step_is_visibly_marked_as_proposal_only():
    app = _app().run()
    _prepare(app, "Create a draft report")

    plan = app.session_state["structured_task_plan"]
    mutation = [step for step in plan.steps if step.requires_human_approval]
    assert len(mutation) == 1
    assert any("requires separate, action-specific" in item.value for item in app.warning)
    assert app.session_state["execution_gateway"].audit_events == ()


def test_clarification_response_replans_without_dispatch():
    app = _app().run()
    _prepare(app, "do it")

    first_plan = app.session_state["structured_task_plan"]
    assert first_plan.status is PlanStatus.NEEDS_CLARIFICATION
    assert not first_plan.steps
    assert any("NEEDS CLARIFICATION" in item.value for item in app.warning)

    app.text_area[2].set_value("Review the README and summarize the setup instructions")
    app.run()
    assert not app.exception
    buttons = [button for button in app.button if button.label == "Prepare updated plan"]
    assert len(buttons) == 1
    buttons[0].click().run()

    revised_plan = app.session_state["structured_task_plan"]
    assert revised_plan.status is PlanStatus.READY
    assert len(revised_plan.steps) == 4
    assert "Additional clarification:" in revised_plan.task_description
    assert app.session_state["execution_gateway"].audit_events == ()


def test_blocked_plan_displays_safety_notes_without_execution():
    app = _app().run()
    _prepare(app, "Trade stock now")

    plan = app.session_state["structured_task_plan"]
    assert plan.status is PlanStatus.BLOCKED
    assert plan.steps == ()
    assert any("BLOCKED" in item.value for item in app.error)
    assert app.session_state["execution_gateway"].audit_events == ()


def test_structured_planning_state_is_cleared_on_identity_change():
    from core.session_security import bind_session_identity, clear_session_identity

    state = {}
    bind_session_identity(state, "issuer-a\\nsubject-a")
    state["structured_task_plan"] = object()
    state["structured_task_source"] = "private task"
    state["structured_task_clarification"] = "private clarification"
    state["structured_task_input"] = "private draft"

    changed = bind_session_identity(state, "issuer-b\\nsubject-b")
    assert changed is True
    assert not any(
        key in state
        for key in (
            "structured_task_plan",
            "structured_task_source",
            "structured_task_clarification",
            "structured_task_input",
        )
    )

    state["structured_task_plan"] = object()
    clear_session_identity(state)
    assert "structured_task_plan" not in state
