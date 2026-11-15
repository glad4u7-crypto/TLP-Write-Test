"""Deterministic, offline task intake and planning contract.

Planning produces reviewable proposal data only. It never approves or dispatches actions.
"""
from dataclasses import asdict, dataclass
from enum import Enum
import hashlib
import re
import unicodedata

from core.models import Task


MAX_TASK_LENGTH = 4000
SCHEMA_VERSION = "1.0"


class PlanStatus(str, Enum):
    READY = "ready"
    NEEDS_CLARIFICATION = "needs_clarification"
    BLOCKED = "blocked"


class StepCategory(str, Enum):
    READ_ONLY = "read_only"
    PROPOSED_MUTATION = "proposed_mutation"
    VALIDATION = "validation"


@dataclass(frozen=True)
class IntakeResult:
    accepted: bool
    normalized_description: str
    errors: tuple[str, ...] = ()
    clarification_questions: tuple[str, ...] = ()


@dataclass(frozen=True)
class PlanStep:
    step_id: str
    title: str
    purpose: str
    category: StepCategory
    expected_output: str
    requires_human_approval: bool = False


@dataclass(frozen=True)
class TaskPlan:
    schema_version: str
    plan_id: str
    task_description: str
    status: PlanStatus
    steps: tuple[PlanStep, ...]
    clarification_questions: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    safety_notes: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        """Return a stable JSON-compatible representation (no timestamps)."""
        result = asdict(self)
        result["status"] = self.status.value
        for step in result["steps"]:
            step["category"] = step["category"].value
        return result


# These are conservative intent markers, not a replacement for action authorization.
# A blocked plan is only a refusal to plan the detected intent; it does not execute anything.
_BLOCKED_INTENT = re.compile(
    r"\b(?:pay|payment|purchase|buy|checkout|trade|trading|invest|investment|"
    r"withdraw|deposit|recharge|transfer\s+money|send\s+money|move\s+money|"
    r"place\s+order|execute\s+order|paid\s+(?:api|provider|service)|"
    r"external\s+(?:api|provider)|api\s+call)\b",
    re.IGNORECASE,
)
_MUTATION_INTENT = re.compile(
    r"\b(?:create|update|edit|delete|remove|write|save|send|publish|rename|move|"
    r"add|upload|download|share|submit)\b",
    re.IGNORECASE,
)
_AMBIGUOUS_TASKS = (
    (re.compile(r"^\s*(?:do|fix|handle|complete|finish)\s+(?:it|that|this)\s*[.!?]*\s*$", re.I),
     "What specific item or outcome should I work on?"),
    (re.compile(r"^\s*(?:make|change|improve)\s+(?:it|that|this)(?:\s+better)?\s*[.!?]*\s*$", re.I),
     "What should be changed, and what should the desired result look like?"),
)


def validate_task_intake(description: object) -> IntakeResult:
    """Validate bounds and surface obvious missing references without guessing."""
    if not isinstance(description, str):
        return IntakeResult(False, "", ("Task description must be text.",))
    if not description.strip():
        return IntakeResult(False, "", ("Task description must not be empty.",))

    # Permit ordinary whitespace controls, reject other control characters.
    if any(
        unicodedata.category(char) == "Cc" and char not in "\n\r\t"
        for char in description
    ):
        return IntakeResult(False, "", ("Task contains unsupported control characters.",))
    normalized = " ".join(description.split())
    if len(normalized) > MAX_TASK_LENGTH:
        return IntakeResult(
            False, "", (f"Task description exceeds the {MAX_TASK_LENGTH}-character limit.",)
        )

    questions = tuple(
        question for pattern, question in _AMBIGUOUS_TASKS
        if pattern.fullmatch(normalized)
    )
    return IntakeResult(True, normalized, (), questions)


def create_structured_plan(task: Task) -> TaskPlan:
    """Create a deterministic, typed proposal; never issue approval or execute."""
    if not isinstance(task, Task):
        raise TypeError("create_structured_plan expects a Task instance.")

    intake = validate_task_intake(task.description)
    if not intake.accepted:
        raise ValueError("; ".join(intake.errors))

    description = intake.normalized_description
    plan_id = "plan-" + hashlib.sha256(description.encode("utf-8")).hexdigest()[:16]

    if _BLOCKED_INTENT.search(description):
        return TaskPlan(
            schema_version=SCHEMA_VERSION,
            plan_id=plan_id,
            task_description=description,
            status=PlanStatus.BLOCKED,
            steps=(),
            safety_notes=(
                "Detected prohibited financial, trading, purchase, or external-provider intent.",
                "No action was approved, registered, or executed.",
            ),
        )

    if intake.clarification_questions:
        return TaskPlan(
            schema_version=SCHEMA_VERSION,
            plan_id=plan_id,
            task_description=description,
            status=PlanStatus.NEEDS_CLARIFICATION,
            steps=(),
            clarification_questions=intake.clarification_questions,
            safety_notes=("No assumptions were added to fill missing task details.",),
        )

    mutation = bool(_MUTATION_INTENT.search(description))
    category = StepCategory.PROPOSED_MUTATION if mutation else StepCategory.READ_ONLY
    approval_note = (
        "Any later mutation requires separate action-specific human approval."
        if mutation else
        "This plan contains no proposed mutation."
    )
    steps = (
        PlanStep(
            "step-01", "Clarify outcome and constraints",
            "Restate the requested outcome and preserve stated constraints.",
            StepCategory.VALIDATION, "Validated task statement",
        ),
        PlanStep(
            "step-02", "Inspect relevant context",
            "Identify relevant project context and available, authorized information sources.",
            StepCategory.READ_ONLY, "Context summary and identified gaps",
        ),
        PlanStep(
            "step-03", "Prepare a proposed result",
            "Prepare a reviewable proposal without performing external side effects.",
            category, "Draft proposal for human review", mutation,
        ),
        PlanStep(
            "step-04", "Validate and report",
            "Check the proposal against the request and report evidence and limitations.",
            StepCategory.VALIDATION, "Validation results and completion report",
        ),
    )
    return TaskPlan(
        schema_version=SCHEMA_VERSION,
        plan_id=plan_id,
        task_description=description,
        status=PlanStatus.READY,
        steps=steps,
        safety_notes=(approval_note, "Planning only: no handler dispatch or external action is available."),
    )


def create_plan(task: Task) -> list[str]:
    """Compatibility wrapper retaining the legacy four-step text API."""
    if not task.description.strip():
        raise ValueError("Cannot plan an empty task.")
    return [
        "Clarify the desired outcome and constraints.",
        "Inspect relevant project context and available tools.",
        "Prepare a proposed change or result.",
        "Run appropriate checks and report evidence.",
    ]
