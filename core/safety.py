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
    # Convert punctuation and whitespace to separators before checking markers.
    return re.sub(r"[^a-z0-9]+", "_", action.strip().lower()).strip("_")


def _contains_blocked_marker(normalized: str) -> bool:
    tokens = set(normalized.split("_"))
    if tokens & {"payment", "purchase", "checkout", "billing", "recharge", "paid", "premium"}:
        return True
    # Match compound markers as whole token sequences, not arbitrary substrings
    # (for example, "unpaid" must not match "paid").
    return any(
        re.search(rf"(?:^|_){re.escape(marker)}(?:_|$)", normalized)
        for marker in ("external_api", "provider_call")
    )


def authorize_action(action: str, approved_action: str | None = None) -> SafetyDecision:
    """Authorize read-only work or one specifically approved mutation.

    A generic boolean approval is deliberately not accepted: approval must name
    the exact normalized action. Payment, purchase, billing, paid, and external
    provider actions remain blocked in the current zero-cost build.
    """
    normalized = _normalize(action)
    if not normalized:
        return SafetyDecision(False, "A valid action must be specified.")

    if _contains_blocked_marker(normalized):
        return SafetyDecision(False, "Payment, paid services, and external provider calls are disabled.")

    if normalized in _READ_ONLY_ACTIONS:
        return SafetyDecision(True, "Read-only action is allowed.")

    if approved_action is None:
        return SafetyDecision(False, "This action requires approval for the exact action name.")

    approved = _normalize(approved_action)
    if not approved or approved != normalized:
        return SafetyDecision(False, "Approval does not match this exact action.")

    return SafetyDecision(True, "Exact action-specific approval supplied.")
