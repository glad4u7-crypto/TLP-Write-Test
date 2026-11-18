import pytest

from core.safety import authorize_action


@pytest.mark.parametrize("action", [
    "read", "inspect", "plan", "summarize",
    "read_invoice", "inspect_repository", "summarize_report", "browser_read",
])
def test_registered_read_only_actions_are_allowed(action):
    assert authorize_action(action).allowed is True


@pytest.mark.parametrize("action", [
    "write_file", "delete_file", "send_email", "publish_post",
    "create_project", "delete_project",
])
def test_registered_mutations_require_exact_action_approval(action):
    decision = authorize_action(action)
    assert decision.allowed is False
    assert "exact action" in decision.reason


def test_exact_action_approval_allows_registered_mutation():
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
    "send_money", "move_money", "transfer_funds", "send_funds",
    "account_top_up", "top_up_account", "cash_out", "cashout",
    "pay_vendor", "payee_transfer", "settle_invoice",
])
def test_financial_and_external_provider_actions_are_always_blocked(action):
    decision = authorize_action(action, approved_action=action)
    assert decision.allowed is False
    assert "disabled" in decision.reason


@pytest.mark.parametrize("action", [
    "run_shell", "execute_code", "open_browser", "unknown_action",
    "unpaid_report", "external_apiary", "read_secret", "read_all_files",
    "inspect_private_keys",
])
def test_unknown_actions_fail_closed_even_when_named_in_approval(action):
    assert authorize_action(action, approved_action=action).allowed is False


def test_generic_boolean_approval_is_not_accepted():
    assert authorize_action("write_file", approved_action=True).allowed is False


@pytest.mark.parametrize("action", ["", "   ", None, 123])
def test_invalid_action_is_rejected(action):
    assert authorize_action(action).allowed is False


def test_auto_run_is_off_by_default_for_mutations():
    assert authorize_action("write_file", auto_run=True).allowed is False


def test_auto_run_allows_only_exact_preconfigured_action():
    assert authorize_action(
        "write_file", auto_run=True, auto_run_actions={"write_file"}
    ).allowed is True
    assert authorize_action(
        "delete_file", auto_run=True, auto_run_actions={"write_file"}
    ).allowed is False


def test_auto_run_cannot_override_blocked_financial_action():
    decision = authorize_action(
        "place_order", auto_run=True, auto_run_actions={"place_order"}
    )
    assert decision.allowed is False


def test_auto_run_cannot_override_unknown_action():
    decision = authorize_action(
        "run_shell", auto_run=True, auto_run_actions={"run_shell"}
    )
    assert decision.allowed is False
