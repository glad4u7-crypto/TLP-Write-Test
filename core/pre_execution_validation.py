"""Pre-dispatch validation for bounded task execution intents.

Validation is not authorization: mutations still require a fresh approval
receipt at ExecutionGateway dispatch. This module never executes handlers.
"""
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import json
import re
from typing import Any

from core.safety import authorize_action


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str


@dataclass(frozen=True)
class IntentValidation:
    valid: bool
    requires_approval: bool
    normalized_action: str
    payload_bytes: int
    issues: tuple[ValidationIssue, ...] = ()


@dataclass(frozen=True)
class PlanValidation:
    valid: bool
    step_count: int
    total_payload_bytes: int
    intents: tuple[IntentValidation, ...]
    issues: tuple[ValidationIssue, ...] = ()


class PreExecutionValidator:
    """Validate shape, bounds, and known action eligibility before dispatch."""

    def __init__(
        self,
        *,
        max_payload_bytes: int = 32_768,
        max_total_payload_bytes: int = 131_072,
        max_depth: int = 8,
        max_steps: int = 25,
        max_string_length: int = 16_384,
    ) -> None:
        bounds = (
            (max_payload_bytes, 1, 1_048_576),
            (max_total_payload_bytes, 1, 4_194_304),
            (max_depth, 1, 32),
            (max_steps, 1, 100),
            (max_string_length, 1, 262_144),
        )
        if any(type(value) is not int or not low <= value <= high
               for value, low, high in bounds):
            raise ValueError("Validator bounds are outside their safe ranges.")
        self.max_payload_bytes = max_payload_bytes
        self.max_total_payload_bytes = max_total_payload_bytes
        self.max_depth = max_depth
        self.max_steps = max_steps
        self.max_string_length = max_string_length

    @staticmethod
    def _normalize_action(action: object) -> str:
        if not isinstance(action, str):
            return ""
        return re.sub(r"[^a-z0-9]+", "_", action.strip().lower()).strip("_")

    def _measure_payload(self, payload: object) -> tuple[int, tuple[ValidationIssue, ...]]:
        issues: list[ValidationIssue] = []
        if not isinstance(payload, Mapping):
            return 0, (ValidationIssue("payload_type", "Payload must be a mapping."),)

        try:
            encoded = json.dumps(
                payload, sort_keys=True, separators=(",", ":"),
                ensure_ascii=False, allow_nan=False,
            ).encode("utf-8")
        except (TypeError, ValueError, OverflowError):
            return 0, (ValidationIssue(
                "payload_encoding", "Payload must contain finite JSON-compatible values."
            ),)

        if len(encoded) > self.max_payload_bytes:
            issues.append(ValidationIssue("payload_too_large", "Payload exceeds the configured byte limit."))

        stack: list[tuple[object, int]] = [(payload, 0)]
        seen: set[int] = set()
        while stack:
            value, depth = stack.pop()
            if depth > self.max_depth:
                issues.append(ValidationIssue("payload_too_deep", "Payload nesting exceeds the configured depth."))
                break
            if isinstance(value, (Mapping, list, tuple)):
                identity = id(value)
                if identity in seen:
                    issues.append(ValidationIssue("payload_cycle", "Payload contains a repeated or cyclic container."))
                    break
                seen.add(identity)
                children = value.values() if isinstance(value, Mapping) else value
                stack.extend((child, depth + 1) for child in children)
                if isinstance(value, Mapping):
                    for key in value:
                        if not isinstance(key, str) or len(key) > 256:
                            issues.append(ValidationIssue("payload_key", "Payload keys must be short strings."))
                            break
            elif isinstance(value, str) and len(value) > self.max_string_length:
                issues.append(ValidationIssue("string_too_long", "A payload string exceeds the configured limit."))
                break
        return len(encoded), tuple(issues)

    def validate_intent(self, action: object, payload: object) -> IntentValidation:
        issues: list[ValidationIssue] = []
        normalized = self._normalize_action(action)
        if not normalized:
            issues.append(ValidationIssue("action_invalid", "Action must be non-empty text."))
        elif normalized != action:
            # Canonical action names avoid ambiguous aliases in plans and audit.
            issues.append(ValidationIssue("action_noncanonical", "Action must use its canonical lowercase identifier."))

        size, payload_issues = self._measure_payload(payload)
        issues.extend(payload_issues)

        requires_approval = False
        if normalized and normalized == action:
            read_decision = authorize_action(normalized)
            if read_decision.allowed:
                requires_approval = False
            else:
                eligible = authorize_action(normalized, approved_action=normalized)
                if eligible.allowed:
                    requires_approval = True
                else:
                    issues.append(ValidationIssue("action_blocked", eligible.reason))

        return IntentValidation(
            valid=not issues,
            requires_approval=requires_approval,
            normalized_action=normalized,
            payload_bytes=size,
            issues=tuple(issues),
        )

    def validate_plan(self, steps: Sequence[object]) -> PlanValidation:
        if not isinstance(steps, Sequence) or isinstance(steps, (str, bytes, bytearray)):
            issue = ValidationIssue("plan_type", "Plan must be a sequence of step mappings.")
            return PlanValidation(False, 0, 0, (), (issue,))
        if len(steps) > self.max_steps:
            issue = ValidationIssue("plan_too_large", "Plan exceeds the configured step limit.")
            return PlanValidation(False, len(steps), 0, (), (issue,))

        intents: list[IntentValidation] = []
        issues: list[ValidationIssue] = []
        seen_ids: set[str] = set()
        total = 0
        for index, step in enumerate(steps):
            if not isinstance(step, Mapping):
                issues.append(ValidationIssue("step_type", f"Step {index} must be a mapping."))
                continue
            step_id = step.get("step_id")
            if not isinstance(step_id, str) or not step_id or len(step_id) > 64:
                issues.append(ValidationIssue("step_id", f"Step {index} has an invalid step_id."))
                continue
            if step_id in seen_ids:
                issues.append(ValidationIssue("duplicate_step_id", f"Step ID {step_id!r} is duplicated."))
                continue
            seen_ids.add(step_id)
            intent = self.validate_intent(step.get("action"), step.get("payload", {}))
            intents.append(intent)
            total += intent.payload_bytes
            issues.extend(
                ValidationIssue(issue.code, f"Step {step_id}: {issue.message}")
                for issue in intent.issues
            )
        if total > self.max_total_payload_bytes:
            issues.append(ValidationIssue("plan_payload_too_large", "Combined plan payload exceeds the configured byte limit."))
        return PlanValidation(
            valid=not issues,
            step_count=len(steps),
            total_payload_bytes=total,
            intents=tuple(intents),
            issues=tuple(issues),
        )
