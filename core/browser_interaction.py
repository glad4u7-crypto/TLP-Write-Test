"""Offline, typed and fail-closed website interaction intent validation.

This module does not launch a browser, perform I/O, dispatch jobs, or consume
approval receipts. It only validates bounded plans for a separately reviewed
execution boundary. No submit or financial operation exists in this API.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from collections.abc import Mapping, Sequence
from typing import Literal

from core.browser_security import BrowserPolicyError, validate_destination


class InteractionPolicyError(ValueError):
    """An interaction intent violates the closed website-interaction contract."""


LocatorKind = Literal["role", "label", "placeholder", "text", "test_id"]
_ALLOWED_LOCATORS = frozenset({"role", "label", "placeholder", "text", "test_id"})
_ALLOWED_FIELD_TYPES = frozenset({"text", "email", "number", "date", "select"})
_ALLOWED_FILTER_OPERATORS = frozenset({"eq", "contains", "gte", "lte", "in"})
_ALLOWED_FILTER_FIELDS = frozenset({"title", "name", "category", "date", "status", "price"})
_PROHIBITED_TERMS = re.compile(
    r"\b(payment|checkout|purchase|buy now|subscribe|subscription|trade|"
    r"transfer|withdraw|deposit|send money|place order)\b",
    re.IGNORECASE,
)
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{7,63}$")


def _closed_mapping(raw: object, fields: frozenset[str], label: str) -> Mapping:
    if not isinstance(raw, Mapping) or any(type(k) is not str for k in raw):
        raise InteractionPolicyError(f"{label} must be an object with string keys.")
    if set(raw) != fields:
        raise InteractionPolicyError(f"{label} fields do not match the closed schema.")
    return raw


def _bounded_string(value: object, label: str, limit: int, *, allow_empty: bool = False) -> str:
    if type(value) is not str or len(value) > limit or (not allow_empty and not value.strip()):
        raise InteractionPolicyError(f"{label} must be a bounded string.")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise InteractionPolicyError(f"{label} contains control characters.")
    return value


def _validate_id(value: object, label: str) -> str:
    if type(value) is not str or not _ID.fullmatch(value):
        raise InteractionPolicyError(f"{label} is malformed.")
    return value


def _validate_origin_url(url: object, origins: Sequence[str]) -> str:
    try:
        return validate_destination(url, origins).url
    except (BrowserPolicyError, TypeError) as exc:
        raise InteractionPolicyError("URL is not within the exact approved HTTPS origins.") from exc


def _validate_locator(raw: object) -> tuple[str, str]:
    item = _closed_mapping(raw, frozenset({"kind", "value"}), "locator")
    kind = item["kind"]
    if type(kind) is not str or kind not in _ALLOWED_LOCATORS:
        raise InteractionPolicyError("Locator kind is unsupported.")
    value = _bounded_string(item["value"], "locator value", 160)
    if kind == "role" and value.lower() not in {
        "link", "button", "textbox", "checkbox", "radio", "combobox", "option"
    }:
        raise InteractionPolicyError("Accessible role is not supported.")
    return kind, value


@dataclass(frozen=True)
class ClickIntent:
    interaction_id: str
    page_id: str
    origin: str
    locator_kind: str
    locator_value: str
    destination_url: str


@dataclass(frozen=True)
class FillIntent:
    interaction_id: str
    page_id: str
    origin: str
    locator_kind: str
    locator_value: str
    field_type: str
    value: str


@dataclass(frozen=True)
class SearchFilter:
    field: str
    operator: str
    value: str


@dataclass(frozen=True)
class SearchIntent:
    interaction_id: str
    page_id: str
    origin: str
    query: str
    filters: tuple[SearchFilter, ...]
    max_results: int


@dataclass(frozen=True)
class NavigationStep:
    step_id: str
    url: str


@dataclass(frozen=True)
class NavigationPlan:
    plan_id: str
    steps: tuple[NavigationStep, ...]
    max_runtime_seconds: int


def validate_click_intent(raw: object, *, allowed_origins: Sequence[str]) -> ClickIntent:
    """Allow only a link click that resolves to an approved destination.

    Generic buttons and submit controls are intentionally not executable here.
    """
    fields = frozenset({"interaction_id", "page_id", "origin", "locator", "destination_url"})
    item = _closed_mapping(raw, fields, "click intent")
    interaction_id = _validate_id(item["interaction_id"], "interaction_id")
    page_id = _validate_id(item["page_id"], "page_id")
    origin = _validate_origin_url(item["origin"], allowed_origins)
    kind, value = _validate_locator(item["locator"])
    if kind != "role" or value.lower() != "link":
        raise InteractionPolicyError("Only explicit link navigation clicks are supported; buttons are blocked.")
    destination = _validate_origin_url(item["destination_url"], allowed_origins)
    if _PROHIBITED_TERMS.search(value):
        raise InteractionPolicyError("Prohibited action wording is blocked.")
    return ClickIntent(interaction_id, page_id, origin, kind, value, destination)


def validate_fill_intent(raw: object, *, allowed_origins: Sequence[str]) -> FillIntent:
    """Validate draft-only, non-secret form field filling; never submits."""
    fields = frozenset({
        "interaction_id", "page_id", "origin", "locator", "field_type", "value"
    })
    item = _closed_mapping(raw, fields, "fill intent")
    interaction_id = _validate_id(item["interaction_id"], "interaction_id")
    page_id = _validate_id(item["page_id"], "page_id")
    origin = _validate_origin_url(item["origin"], allowed_origins)
    kind, locator_value = _validate_locator(item["locator"])
    field_type = item["field_type"]
    if type(field_type) is not str or field_type not in _ALLOWED_FIELD_TYPES:
        raise InteractionPolicyError("Field type is unsupported or may contain a secret.")
    value = _bounded_string(item["value"], "form value", 2048, allow_empty=True)
    if _PROHIBITED_TERMS.search(value):
        raise InteractionPolicyError("Financial or purchase-related form content is out of scope.")
    if kind not in {"label", "placeholder", "test_id"}:
        raise InteractionPolicyError("Form fields require a label, placeholder or test-id locator.")
    if field_type == "email" and value and (len(value) > 254 or "@" not in value):
        raise InteractionPolicyError("Email value is malformed.")
    return FillIntent(interaction_id, page_id, origin, kind, locator_value, field_type, value)


def validate_search_intent(raw: object, *, allowed_origins: Sequence[str]) -> SearchIntent:
    """Validate a bounded, read-only search and filter request."""
    fields = frozenset({"interaction_id", "page_id", "origin", "query", "filters", "max_results"})
    item = _closed_mapping(raw, fields, "search intent")
    interaction_id = _validate_id(item["interaction_id"], "interaction_id")
    page_id = _validate_id(item["page_id"], "page_id")
    origin = _validate_origin_url(item["origin"], allowed_origins)
    query = _bounded_string(item["query"], "search query", 256, allow_empty=True)
    if _PROHIBITED_TERMS.search(query):
        raise InteractionPolicyError("Financial or purchase-related search is out of scope.")
    raw_filters = item["filters"]
    if not isinstance(raw_filters, Sequence) or isinstance(raw_filters, (str, bytes)) or len(raw_filters) > 10:
        raise InteractionPolicyError("At most 10 structured filters are supported.")
    filters: list[SearchFilter] = []
    for raw_filter in raw_filters:
        entry = _closed_mapping(raw_filter, frozenset({"field", "operator", "value"}), "filter")
        field, operator = entry["field"], entry["operator"]
        if type(field) is not str or field not in _ALLOWED_FILTER_FIELDS:
            raise InteractionPolicyError("Filter field is unsupported.")
        if type(operator) is not str or operator not in _ALLOWED_FILTER_OPERATORS:
            raise InteractionPolicyError("Filter operator is unsupported.")
        value = _bounded_string(entry["value"], "filter value", 128)
        if _PROHIBITED_TERMS.search(value):
            raise InteractionPolicyError("Financial or purchase-related filter is out of scope.")
        filters.append(SearchFilter(field, operator, value))
    limit = item["max_results"]
    if type(limit) is not int or not 1 <= limit <= 100:
        raise InteractionPolicyError("max_results must be an integer from 1 to 100.")
    return SearchIntent(interaction_id, page_id, origin, query, tuple(filters), limit)


def validate_navigation_plan(raw: object, *, allowed_origins: Sequence[str]) -> NavigationPlan:
    """Validate a finite same-allowlist page sequence; performs no navigation."""
    fields = frozenset({"plan_id", "steps", "max_runtime_seconds"})
    item = _closed_mapping(raw, fields, "navigation plan")
    plan_id = _validate_id(item["plan_id"], "plan_id")
    raw_steps = item["steps"]
    if not isinstance(raw_steps, Sequence) or isinstance(raw_steps, (str, bytes)) or not 1 <= len(raw_steps) <= 8:
        raise InteractionPolicyError("Navigation plan must contain 1 to 8 steps.")
    steps: list[NavigationStep] = []
    seen: set[str] = set()
    for raw_step in raw_steps:
        entry = _closed_mapping(raw_step, frozenset({"step_id", "url"}), "navigation step")
        step_id = _validate_id(entry["step_id"], "step_id")
        if step_id in seen:
            raise InteractionPolicyError("Navigation step IDs must be unique.")
        seen.add(step_id)
        url = _validate_origin_url(entry["url"], allowed_origins)
        steps.append(NavigationStep(step_id, url))
    runtime = item["max_runtime_seconds"]
    if type(runtime) is not int or not 1 <= runtime <= 60:
        raise InteractionPolicyError("Navigation runtime must be an integer from 1 to 60 seconds.")
    return NavigationPlan(plan_id, tuple(steps), runtime)
