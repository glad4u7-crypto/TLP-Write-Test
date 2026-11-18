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
    if type(url) is str and _PROHIBITED_TERMS.search(url):
        raise InteractionPolicyError("Financial or purchase-related destinations are out of scope.")
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


@dataclass(frozen=True)
class TargetEvidence:
    """Short-lived adapter observation; not an approval or execution capability."""

    interaction_id: str
    page_id: str
    locator_kind: str
    locator_value: str
    element_type: str
    href: str | None
    observed_at: int


def validate_target_evidence(
    raw: object,
    *,
    intent: ClickIntent | FillIntent,
    allowed_origins: Sequence[str],
    now_epoch: int,
    max_age_seconds: int = 5,
) -> TargetEvidence:
    """Require a unique, visible, enabled, fresh target on the intended page.

    This validates a controller/adapter observation only. It does not prove the
    adapter is honest, bind an Owner approval, or make a browser action safe.
    """
    fields = frozenset({
        "interaction_id", "page_id", "origin", "locator", "match_count",
        "visible", "enabled", "element_type", "href", "observed_at",
    })
    item = _closed_mapping(raw, fields, "target evidence")
    if type(intent) not in (ClickIntent, FillIntent):
        raise InteractionPolicyError("Target evidence requires a validated click or fill intent.")
    # Frozen dataclasses can still be constructed directly with invalid values.
    # Re-check their security-relevant fields at this boundary.
    _validate_id(intent.interaction_id, "intent interaction_id")
    _validate_id(intent.page_id, "intent page_id")
    _validate_origin_url(intent.origin, allowed_origins)
    _validate_locator({"kind": intent.locator_kind, "value": intent.locator_value})
    if type(intent) is ClickIntent:
        if intent.locator_kind != "role" or intent.locator_value.lower() != "link":
            raise InteractionPolicyError("Click intent is not a link-only operation.")
        _validate_origin_url(intent.destination_url, allowed_origins)
    else:
        if intent.field_type not in _ALLOWED_FIELD_TYPES:
            raise InteractionPolicyError("Fill intent field type is unsupported.")
        _bounded_string(intent.value, "intent form value", 2048, allow_empty=True)
    interaction_id = _validate_id(item["interaction_id"], "interaction_id")
    page_id = _validate_id(item["page_id"], "page_id")
    if interaction_id != intent.interaction_id or page_id != intent.page_id:
        raise InteractionPolicyError("Target evidence does not match the intended interaction and page.")
    observed_origin = _validate_origin_url(item["origin"], allowed_origins)
    expected_origin = _validate_origin_url(intent.origin, allowed_origins)
    try:
        observed_parts = validate_destination(observed_origin, allowed_origins)
        expected_parts = validate_destination(expected_origin, allowed_origins)
    except (BrowserPolicyError, TypeError) as exc:
        raise InteractionPolicyError("Target evidence origin is not approved.") from exc
    if observed_parts.origin != expected_parts.origin:
        raise InteractionPolicyError("Target evidence belongs to a different origin.")

    locator_kind, locator_value = _validate_locator(item["locator"])
    if (locator_kind, locator_value) != (intent.locator_kind, intent.locator_value):
        raise InteractionPolicyError("Observed locator differs from the approved intent.")
    if type(item["match_count"]) is not int or item["match_count"] != 1:
        raise InteractionPolicyError("Target locator must resolve to exactly one element.")
    if type(item["visible"]) is not bool or item["visible"] is not True:
        raise InteractionPolicyError("Target element must be visible.")
    if type(item["enabled"]) is not bool or item["enabled"] is not True:
        raise InteractionPolicyError("Target element must be enabled.")

    element_type = item["element_type"]
    href = item["href"]
    if isinstance(intent, ClickIntent):
        if element_type != "link" or type(href) is not str:
            raise InteractionPolicyError("Click target must be an observed link with an href.")
        observed_href = _validate_origin_url(href, allowed_origins)
        if observed_href != intent.destination_url:
            raise InteractionPolicyError("Observed link destination changed after planning.")
    else:
        expected_types = {
            "text": {"input_text", "textarea"},
            "email": {"input_email"},
            "number": {"input_number"},
            "date": {"input_date"},
            "select": {"select"},
        }
        if element_type not in expected_types[intent.field_type] or href is not None:
            raise InteractionPolicyError("Observed form control type does not match the draft-fill intent.")

    observed_at = item["observed_at"]
    if type(now_epoch) is not int or type(observed_at) is not int:
        raise InteractionPolicyError("Target evidence timestamps must be integer Unix seconds.")
    if type(max_age_seconds) is not int or not 1 <= max_age_seconds <= 30:
        raise InteractionPolicyError("Target evidence age limit is invalid.")
    if observed_at > now_epoch or now_epoch - observed_at > max_age_seconds:
        raise InteractionPolicyError("Target evidence is stale or from the future.")

    return TargetEvidence(
        interaction_id, page_id, locator_kind, locator_value,
        element_type, href, observed_at,
    )


@dataclass(frozen=True)
class SearchResult:
    """Normalized visible search result with sensitive text/query values redacted."""

    title: str
    url: str
    snippet: str
    source_page_id: str


_EMAIL_PATTERN = re.compile(r"(?i)\\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\\.[A-Z]{2,}\\b")
_PHONE_PATTERN = re.compile(r"(?<!\\w)\\+?\\d[\\d\\s().-]{7,}\\d(?!\\w)")
_BEARER_PATTERN = re.compile(r"(?i)\\bBearer\\s+[A-Za-z0-9._~+/=-]{8,}")
_NAMED_SECRET_PATTERN = re.compile(
    r"(?i)\\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token|secret|password)\\s*[:=]\\s*[^\\s,;]{6,}"
)
_SENSITIVE_QUERY_KEYS = frozenset({
    "access_token", "apikey", "api_key", "auth", "auth_token", "authorization",
    "client_secret", "code", "csrf", "key", "otp", "password",
    "refresh_token", "secret", "session", "session_id", "signature", "token", "xsrf",
})


def _redact_result_text(value: str) -> str:
    value = _EMAIL_PATTERN.sub("[redacted-email]", value)
    value = _PHONE_PATTERN.sub("[redacted-phone]", value)
    value = _BEARER_PATTERN.sub("Bearer [redacted]", value)
    return _NAMED_SECRET_PATTERN.sub("[redacted-secret]", value)


def _sanitize_result_url(value: object, allowed_origins: Sequence[str]) -> str:
    from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

    canonical = _validate_origin_url(value, allowed_origins)
    parsed = urlsplit(canonical)
    safe_query = []
    try:
        query_items = parse_qsl(parsed.query, keep_blank_values=True, max_num_fields=100)
    except ValueError as exc:
        raise InteractionPolicyError("Search result URL has too many query parameters.") from exc
    for key, item in query_items:
        normalized_key = re.sub(r"[^a-z0-9_]", "", key.lower())
        if normalized_key in _SENSITIVE_QUERY_KEYS:
            continue
        if (_EMAIL_PATTERN.search(item) or _PHONE_PATTERN.search(item)
                or _BEARER_PATTERN.search(item) or _NAMED_SECRET_PATTERN.search(item)):
            continue
        safe_query.append((key, item))
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(safe_query), ""))


def validate_search_results(
    raw_results: object,
    *,
    intent: SearchIntent,
    allowed_origins: Sequence[str],
) -> tuple[SearchResult, ...]:
    """Normalize a bounded list of adapter-reported visible results.

    This is a data-validation/redaction boundary, not a DOM extractor. The
    browser adapter must independently prove that each record came from
    visible page content; this function rejects records not marked visible.
    """
    if type(intent) is not SearchIntent:
        raise InteractionPolicyError("Search results require a validated search intent.")
    # Revalidate dataclass values; frozen records may be directly constructed.
    if type(intent.filters) is not tuple or len(intent.filters) > 10:
        raise InteractionPolicyError("Search intent filters are malformed or exceed their limit.")
    filter_items = []
    for filter_item in intent.filters:
        if type(filter_item) is not SearchFilter:
            raise InteractionPolicyError("Search intent contains an invalid filter record.")
        filter_items.append({
            "field": filter_item.field,
            "operator": filter_item.operator,
            "value": filter_item.value,
        })
    intent = validate_search_intent({
        "interaction_id": intent.interaction_id,
        "page_id": intent.page_id,
        "origin": intent.origin,
        "query": intent.query,
        "filters": filter_items,
        "max_results": intent.max_results,
    }, allowed_origins=allowed_origins)
    if not isinstance(raw_results, Sequence) or isinstance(raw_results, (str, bytes)):
        raise InteractionPolicyError("Search results must be a bounded sequence.")
    if len(raw_results) > intent.max_results:
        raise InteractionPolicyError("Adapter returned more results than the approved limit.")

    normalized: list[SearchResult] = []
    seen_urls: set[str] = set()
    total_bytes = 0
    fields = frozenset({"title", "url", "snippet", "source_page_id", "visible"})
    for raw_result in raw_results:
        item = _closed_mapping(raw_result, fields, "search result")
        if item["visible"] is not True or type(item["visible"]) is not bool:
            raise InteractionPolicyError("Only explicitly visible page results may be normalized.")
        source_page_id = _validate_id(item["source_page_id"], "source_page_id")
        if source_page_id != intent.page_id:
            raise InteractionPolicyError("Search result came from an unexpected page.")
        title = _redact_result_text(_bounded_string(item["title"], "result title", 200))
        snippet = _redact_result_text(_bounded_string(item["snippet"], "result snippet", 1000, allow_empty=True))
        url = _sanitize_result_url(item["url"], allowed_origins)
        if url in seen_urls:
            continue
        seen_urls.add(url)
        total_bytes += len(title.encode("utf-8")) + len(snippet.encode("utf-8")) + len(url.encode("utf-8"))
        if total_bytes > 256_000:
            raise InteractionPolicyError("Normalized search results exceed the total byte budget.")
        normalized.append(SearchResult(title, url, snippet, source_page_id))
    return tuple(normalized)
