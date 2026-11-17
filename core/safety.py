from dataclasses import dataclass

@dataclass(frozen=True)
class SafetyDecision:
    allowed: bool
    reason: str

def authorize_action(action: str, approved: bool = False) -> SafetyDecision:
    normalized = action.strip().lower()
    if not normalized:
        return SafetyDecision(False, "Action must be specified.")
    if normalized in {"read", "inspect", "plan", "summarize"}:
        return SafetyDecision(True, "Read-only action is allowed.")
    if not approved:
        return SafetyDecision(False, "Mutation requires explicit approval.")
    return SafetyDecision(True, "Explicit approval supplied.")
