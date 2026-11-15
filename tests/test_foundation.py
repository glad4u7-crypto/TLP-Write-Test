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


@pytest.mark.parametrize("action", ["read", "inspect", "plan", "summarize", "read_invoice"])
def test_registered_read_only_actions_are_allowed(action):
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


@pytest.mark.parametrize("action", [
    "payment", "make_purchase", "checkout", "billing_update",
    "auto_recharge", "paid_api_call", "premium_provider_call",
    "external_api_request", "transfer_money", "place_order",
    "fund_account", "withdraw_funds", "buy_item", "trade_stock",
    "subscription_upgrade", "refund_payment", "gemini_generate",
])
def test_payment_financial_and_external_services_are_always_blocked(action):
    decision = authorize_action(action, approved_action=action)
    assert decision.allowed is False
    assert "disabled" in decision.reason


def test_generic_boolean_approval_is_not_accepted():
    assert authorize_action("write_file", approved_action=True).allowed is False


@pytest.mark.parametrize("action", ["", "   ", None, 123])
def test_invalid_action_is_rejected(action):
    assert authorize_action(action).allowed is False


@pytest.mark.parametrize("action", [
    "run_shell", "execute_code", "open_browser", "unknown_action",
    "unpaid_report", "external_apiary", "read_secret",
])
def test_unknown_actions_fail_closed(action):
    assert authorize_action(action, approved_action=action).allowed is False


@pytest.mark.parametrize("action", [
    "provider-call", "provider_call_extra", "external api request",
    "make-payment", "purchase_now", "pay_invoice", "buy_item",
    "subscription_upgrade", "donate_money", "openai_request",
    "gemini_generate", "api_call", "provider_request",
])
def test_blocked_markers_are_normalized_and_always_rejected(action):
    assert authorize_action(action, approved_action=action).allowed is False


def test_auto_run_is_restricted_to_exact_preapproved_actions():
    assert authorize_action(
        "write_file", auto_run=True, auto_run_actions={"write_file"}
    ).allowed is True
    assert authorize_action(
        "delete_file", auto_run=True, auto_run_actions={"write_file"}
    ).allowed is False
