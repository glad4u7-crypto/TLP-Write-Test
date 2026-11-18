"""Fail-closed, action-specific authorization for agent operations."""
from dataclasses import dataclass
import re
from collections.abc import Iterable


@dataclass(frozen=True)
class SafetyDecision:
    allowed: bool
    reason: str


# Exact read-only identifiers only. Do not allow arbitrary read_* names.
_READ_ONLY_ACTIONS = {
    "read", "inspect", "plan", "summarize",
    "read_invoice", "inspect_repository", "summarize_report", "browser_read",
}

# Only reviewed mutations may be approved or added to Auto-Run.
_APPROVABLE_MUTATIONS = {
    "create_project", "update_project", "delete_project",
    "write_file", "edit_file", "delete_file", "create_folder",
    "rename_file", "move_file", "create_draft_email",
    "send_email", "send_message", "publish_post",
    "create_playlist", "add_video_to_playlist",
}

_BLOCKED_TOKENS = {
    "pay", "payment", "purchase", "buy", "checkout", "billing", "recharge",
    "charge", "donate", "subscription", "subscribe", "paid", "premium",
    "order", "trade", "trading", "invest", "investment", "transfer",
    "remit", "wire", "withdraw", "deposit", "refund", "fund", "funding",
    "money", "cash", "payout", "disburse", "settle",
    "openai", "anthropic", "gemini", "claude", "gpt", "llm",
}
_BLOCKED_PHRASES = {
    "external_api", "provider_call", "api_call", "provider_request",
    "network_request", "fund_account", "add_funds", "money_transfer",
    "bank_transfer", "wire_transfer", "execute_order", "place_order",
    "move_money", "send_money", "transfer_funds", "send_funds",
    "account_top_up", "top_up_account", "cash_out", "cashout",
    "pay_vendor", "payee_transfer", "settle_invoice",
}


def _normalize(action: object) -> str:
    if not isinstance(action, str):
        return ""
    return re.sub(r"[^a-z0-9]+", "_", action.strip().lower()).strip("_")


def _contains_blocked_marker(normalized: str) -> bool:
    tokens = set(normalized.split("_"))
    return bool(tokens & _BLOCKED_TOKENS) or any(
        re.search(rf"(?:^|_){re.escape(phrase)}(?:_|$)", normalized)
        for phrase in _BLOCKED_PHRASES
    )


def authorize_action(
    action: str,
    approved_action: str | None = None,
    *,
    auto_run: bool = False,
    auto_run_actions: Iterable[str] = (),
) -> SafetyDecision:
    """Authorize exact known actions; deny unknown and prohibited actions.

    Default is Ask First. Auto-Run is opt-in and restricted to exact,
    preconfigured mutation identifiers. Financial/provider actions are
    blocked before either approval mechanism is considered.
    """
    normalized = _normalize(action)
    if not normalized:
        return SafetyDecision(False, "A valid action must be specified.")

    if _contains_blocked_marker(normalized):
        return SafetyDecision(False, "Payment, financial transactions, paid services, and external provider calls are disabled.")

    if normalized in _READ_ONLY_ACTIONS:
        return SafetyDecision(True, "Read-only action is allowed.")

    if normalized not in _APPROVABLE_MUTATIONS:
        return SafetyDecision(False, "Unknown or unregistered action is blocked by default.")

    if auto_run:
        allowed_auto_run = {_normalize(item) for item in auto_run_actions}
        if normalized in allowed_auto_run:
            return SafetyDecision(True, "Action is included in the explicitly configured Auto-Run allowlist.")
        return SafetyDecision(False, "Auto-Run is not authorized for this exact action.")

    approved = _normalize(approved_action)
    if not approved:
        return SafetyDecision(False, "This action requires approval for the exact action name.")
    if approved != normalized:
        return SafetyDecision(False, "Approval does not match this exact action.")

    return SafetyDecision(True, "Exact action-specific approval supplied.")
