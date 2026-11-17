"""Safe, bounded condition evaluation without eval or executable expressions."""
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

MAX_DEPTH = 8
MAX_NODES = 64
MAX_PATH_LENGTH = 256
_MISSING = object()
_ALLOWED_OPERATORS = frozenset({
    "eq", "ne", "gt", "gte", "lt", "lte", "contains", "in", "exists",
})


class ConditionError(ValueError):
    """Raised for malformed or unsafe condition definitions."""


@dataclass(frozen=True)
class Condition:
    """A leaf comparison or a boolean group.

    Leaf: Condition(path="report.score", operator="gte", value=70)
    Group: Condition(all_of=(...), any_of=(...), negate=False)
    Exactly one shape must be selected.
    """
    path: str | None = None
    operator: str | None = None
    value: Any = None
    all_of: tuple["Condition", ...] = ()
    any_of: tuple["Condition", ...] = ()
    negate: bool = False


@dataclass(frozen=True)
class ConditionResult:
    matched: bool
    valid: bool
    reason: str


def _validate_json(value: Any, depth: int = 0, budget: list[int] | None = None) -> None:
    if budget is None:
        budget = [0]
    budget[0] += 1
    if budget[0] > 2048 or depth > 12:
        raise ConditionError("Condition data complexity limit exceeded.")
    if value is None or type(value) in (str, int, float, bool):
        if type(value) is float and (value != value or value in (float("inf"), float("-inf"))):
            raise ConditionError("Non-finite numbers are not supported.")
        return
    if type(value) is list:
        for item in value:
            _validate_json(item, depth + 1, budget)
        return
    if type(value) is dict:
        for key, item in value.items():
            if type(key) is not str:
                raise ConditionError("Condition data keys must be strings.")
            _validate_json(item, depth + 1, budget)
        return
    raise ConditionError("Condition data must contain JSON-compatible primitive values.")


def _lookup(context: Mapping[str, Any], path: str) -> Any:
    if not isinstance(path, str) or not path or len(path) > MAX_PATH_LENGTH:
        raise ConditionError("Condition path is invalid.")
    parts = path.split(".")
    if any(not part or part.startswith("_") for part in parts):
        raise ConditionError("Private or empty path segments are not allowed.")
    current: Any = context
    for part in parts:
        if not isinstance(current, Mapping) or part not in current:
            return _MISSING
        current = current[part]
    return current


def _compare(actual: Any, operator: str, expected: Any) -> bool:
    if operator not in _ALLOWED_OPERATORS:
        raise ConditionError("Unsupported condition operator.")
    if operator == "exists":
        if type(expected) is not bool:
            raise ConditionError("exists expects a boolean value.")
        return (actual is not _MISSING) is expected
    if actual is _MISSING:
        return False
    if operator == "eq":
        return type(actual) is type(expected) and actual == expected
    if operator == "ne":
        return not (type(actual) is type(expected) and actual == expected)
    if operator in {"gt", "gte", "lt", "lte"}:
        if type(actual) not in (int, float) or type(expected) not in (int, float):
            return False
        if operator == "gt": return actual > expected
        if operator == "gte": return actual >= expected
        if operator == "lt": return actual < expected
        return actual <= expected
    if operator == "contains":
        if isinstance(actual, (str, list, tuple)):
            return expected in actual
        if isinstance(actual, Mapping):
            return expected in actual
        return False
    if operator == "in":
        return isinstance(expected, (list, tuple, set, frozenset)) and actual in expected
    return False


def evaluate_condition(condition: Condition, context: Mapping[str, Any]) -> ConditionResult:
    """Evaluate a bounded declarative condition; malformed input never matches."""
    count = 0

    def visit(node: Condition, depth: int) -> bool:
        nonlocal count
        count += 1
        if count > MAX_NODES or depth > MAX_DEPTH:
            raise ConditionError("Condition complexity limit exceeded.")
        if not isinstance(node, Condition) or type(node.negate) is not bool:
            raise ConditionError("Condition node is invalid.")
        leaf = node.path is not None or node.operator is not None
        group = bool(node.all_of) or bool(node.any_of)
        if leaf == group:
            raise ConditionError("Condition must be exactly one leaf or boolean group.")
        if leaf:
            if node.path is None or node.operator is None:
                raise ConditionError("Condition leaf requires path and operator.")
            _validate_json(node.value)
            result = _compare(_lookup(context, node.path), node.operator, node.value)
        else:
            if node.all_of and node.any_of:
                raise ConditionError("A condition group cannot mix all_of and any_of.")
            children = node.all_of or node.any_of
            if not isinstance(children, tuple) or not children:
                raise ConditionError("Condition groups require a non-empty tuple.")
            values = [visit(child, depth + 1) for child in children]
            result = all(values) if node.all_of else any(values)
        return not result if node.negate else result

    try:
        if type(context) is not dict:
            raise ConditionError("Condition context must be a plain dictionary.")
        _validate_json(context)
        matched = visit(condition, 0)
        return ConditionResult(matched, True, "condition_matched" if matched else "condition_not_matched")
    except Exception as exc:
        return ConditionResult(False, False, f"condition_invalid:{type(exc).__name__}")
