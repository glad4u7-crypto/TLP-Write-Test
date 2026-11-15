"""Fail-closed, action-specific authorization for agent operations."""
from dataclasses import dataclass
import re
from collections.abc import Iterable


@dataclass(frozen=True)
class SafetyDecision:
    allowed: bool
    reason: str


# Read-only prefixes are safe only after financial/provider markers are checked.
_READ_ONLY_ACTIONS = {"read", "inspect", "plan", "summarize"}
_READ_ONLY_PREFIXES = ("read_", "inspect_", "plan_", "summarize_")

# Only known mutation identifiers can ever be approved. Add entries only after
# reviewing the action's implementation and side effects.
_APPROVABLE_MUTATIONS = {
    "create_project",
    "update_project",
    "delete_project",
    "write_file",
    "edit_file",
    "delete_file",
    "create_folder",
    "rename_file",
    "move_file",
    "create_draft_email",
    "send_email",
    "send_message",
    "publish_post",
    "create_playlist",
    "add_video_to_playlist",
}

# These action concepts are forbidden in this zero-cost, no-payment build.
_BLOCKED_TOKENS = {
    "pay", "payment", "purchase", "buy", "checkout", "billing", "recharge",
    "charge", "donate", "subscription", "subscribe", "paid", "premium",
    "order", "trade", "trading", "invest", "investment", "transfer",
    "remit", "wire", "withdraw", "deposit", "refund", "fund", "funding",
    "openai", "anthropic", "gemini", "claude", "gpt", "llm",
}
_BLOCKED_PHRASES = {
    "external_api", "provider_call", "api_call", "provider_request",
    "network_request", "fund_account", "add_funds", "money_transfer",
    "bank_transfer", "wire_transfer", "execute_order", "place_order",
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


def _is_read_only(normalized: str) -> bool:
    return normalized in _READ_ONLY_ACTIONS or normalized.startswith(_READ_ONLY_PREFIXES)


def authorize_action(
    action: str,
    approved_action: str | None = None,
    *,
    auto_run: bool = False,
    auto_run_actions: Iterable[str] = (),
) -> SafetyDecision:
    """Authorize read-only work or a registered mutation with exact approval.

    Default is Ask First: every mutation needs approval naming the exact action.
    Auto-Run is opt-in and limited to exact, preconfigured action identifiers.
    Unknown actions and payment/provider actions fail closed in every mode.
    """
    normalized = _normalize(action)
    if not normalized:
        return SafetyDecision(False, "A valid action must be specified.")

    if _contains_blocked_marker(normalized):
        return SafetyDecision(False, "Payment, financial transactions, paid services, and external provider calls are disabled.")

    if _is_read_only(normalized):
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
