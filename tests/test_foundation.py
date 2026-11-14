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


@pytest.mark.parametrize("action", ["read", "inspect", "plan", "summarize"])
def test_read_only_actions_are_allowed(action):
    assert authorize_action(action).allowed is True


@pytest.mark.parametrize("action", ["write_file", "delete_file", "send_email", "publish_post"])
def test_mutations_require_exact_action_approval(action):
    decision = authorize_action(action)
    assert decision.allowed is False
    assert "exact action" in decision.reason


def test_exact_action_approval_allows_only_that_mutation():
    assert authorize_action("write_file", approved_action="write_file").allowed is True


def test_approval_for_different_action_is_rejected():
    decision = authorize_action("delete_file", approved_action="write_file")
    assert decision.allowed is False
    assert "does not match" in decision.reason


@pytest.mark.parametrize(
    "action",
    [
        "payment",
        "make_purchase",
        "checkout",
        "billing_update",
        "auto_recharge",
        "paid_api_call",
        "premium_provider_call",
        "external_api_request",
    ],
)
def test_payment_and_paid_or_external_services_are_always_blocked(action):
    decision = authorize_action(action, approved_action=action)
    assert decision.allowed is False
    assert "disabled" in decision.reason


def test_generic_boolean_approval_is_not_accepted():
    # Prevents an old broad approval flag from authorizing arbitrary actions.
    assert authorize_action("write_file", approved_action=True).allowed is False


@pytest.mark.parametrize("action", ["", "   ", None, 123])
def test_invalid_action_is_rejected(action):
    assert authorize_action(action).allowed is False

@pytest.mark.parametrize(
    "action",
    [
        "unpaid_report",
        "provider_call_extra",
        "external_apiary",
    ],
)
def test_blocked_markers_do_not_match_unrelated_substrings(action):
    # Avoid false positives from matching arbitrary substrings.
    decision = authorize_action(action, approved_action=action)
    assert decision.allowed is True


@pytest.mark.parametrize(
    "action",
    [
        "provider-call",
        "external api request",
        "make-payment",
        "purchase_now",
    ],
)
def test_blocked_markers_are_normalized_and_always_rejected(action):
    decision = authorize_action(action, approved_action=action)
    assert decision.allowed is False
