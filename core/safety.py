"""Fail-closed, action-specific authorization for agent operations."""
from dataclasses import dataclass
import re


@dataclass(frozen=True)
class SafetyDecision:
    allowed: bool
    reason: str


_READ_ONLY_ACTIONS = {"read", "inspect", "plan", "summarize"}
_NEVER_ALLOWED_MARKERS = {
    "payment", "purchase", "checkout", "billing", "recharge",
    "paid", "premium", "external_api", "provider_call",
}


def _normalize(action: str) -> str:
    if not isinstance(action, str):
        return ""
    return re.sub(r"[-\s]+", "_", action.strip().lower())


def authorize_action(action: str, approved_action: str | None = None) -> SafetyDecision:
    """Authorize read-only work or one specifically approved mutation.

    A generic boolean approval is deliberately not accepted: approval must name
    the exact action. Payment, purchase, billing, and paid/external provider
    actions remain blocked in the current zero-cost build, even if approved.
    """
    normalized = _normalize(action)
    if not normalized:
        return SafetyDecision(False, "A valid action must be specified.")

    tokens = set(normalized.split("_"))
    if tokens & _NEVER_ALLOWED_MARKERS or any(marker in normalized for marker in _NEVER_ALLOWED_MARKERS):
        return SafetyDecision(False, "Payment, paid services, and external provider calls are disabled.")

    if normalized in _READ_ONLY_ACTIONS:
        return SafetyDecision(True, "Read-only action is allowed.")

    if approved_action is None:
        return SafetyDecision(False, "This action requires approval for the exact action name.")

    approved = _normalize(approved_action)
    if not approved or approved != normalized:
        return SafetyDecision(False, "Approval does not match this exact action.")

    return SafetyDecision(True, "Exact action-specific approval supplied.")
