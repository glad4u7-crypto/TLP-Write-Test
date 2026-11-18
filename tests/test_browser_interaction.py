import pytest

from core.browser_interaction import (
    InteractionPolicyError,
    validate_click_intent,
    validate_fill_intent,
    validate_navigation_plan,
    validate_search_intent,
)

ORIGINS = ["https://example.com"]


def click(**overrides):
    raw = {
        "interaction_id": "click_0000001",
        "page_id": "page_0000001",
        "origin": "https://example.com/catalog",
        "locator": {"kind": "role", "value": "link"},
        "destination_url": "https://example.com/help",
    }
    raw.update(overrides)
    return raw


def fill(**overrides):
    raw = {
        "interaction_id": "fill_0000001",
        "page_id": "page_0000001",
        "origin": "https://example.com/form",
        "locator": {"kind": "label", "value": "Display name"},
        "field_type": "text",
        "value": "Sample User",
    }
    raw.update(overrides)
    return raw


def search(**overrides):
    raw = {
        "interaction_id": "search_000001",
        "page_id": "page_0000001",
        "origin": "https://example.com/search",
        "query": "annual report",
        "filters": [{"field": "category", "operator": "eq", "value": "documents"}],
        "max_results": 20,
    }
    raw.update(overrides)
    return raw


def test_click_allows_only_link_navigation_on_approved_origin():
    intent = validate_click_intent(click(), allowed_origins=ORIGINS)
    assert intent.destination_url == "https://example.com/help"


@pytest.mark.parametrize("locator", [
    {"kind": "role", "value": "button"},
    {"kind": "text", "value": "Submit"},
    {"kind": "css", "value": "button"},
])
def test_click_blocks_buttons_submit_and_unsupported_locator(locator):
    with pytest.raises(InteractionPolicyError):
        validate_click_intent(click(locator=locator), allowed_origins=ORIGINS)


def test_click_rejects_cross_origin_prohibited_destination_and_unknown_fields():
    with pytest.raises(InteractionPolicyError):
        validate_click_intent(click(destination_url="https://evil.example/"), allowed_origins=ORIGINS)
    with pytest.raises(InteractionPolicyError):
        validate_click_intent(click(destination_url="https://example.com/checkout"), allowed_origins=ORIGINS)
    with pytest.raises(InteractionPolicyError):
        validate_click_intent({**click(), "javascript": "alert(1)"}, allowed_origins=ORIGINS)


def test_fill_is_draft_only_typed_and_bounded():
    intent = validate_fill_intent(fill(), allowed_origins=ORIGINS)
    assert intent.value == "Sample User"
    assert intent.field_type == "text"


@pytest.mark.parametrize("field_type", ["password", "otp", "secret", "file", "payment_card"])
def test_fill_rejects_secret_and_unsupported_field_types(field_type):
    with pytest.raises(InteractionPolicyError):
        validate_fill_intent(fill(field_type=field_type), allowed_origins=ORIGINS)


def test_fill_rejects_unsupported_locator_and_purchase_content():
    with pytest.raises(InteractionPolicyError):
        validate_fill_intent(fill(locator={"kind": "text", "value": "Name"}), allowed_origins=ORIGINS)
    with pytest.raises(InteractionPolicyError):
        validate_fill_intent(fill(value="Buy now"), allowed_origins=ORIGINS)


def test_fill_never_accepts_submit_instruction():
    with pytest.raises(InteractionPolicyError):
        validate_fill_intent({**fill(), "submit": True}, allowed_origins=ORIGINS)


def test_search_supports_bounded_structured_filters():
    intent = validate_search_intent(search(), allowed_origins=ORIGINS)
    assert intent.max_results == 20
    assert intent.filters[0].field == "category"


@pytest.mark.parametrize("limit", [0, -1, 101, True, "20"])
def test_search_rejects_invalid_result_limits(limit):
    with pytest.raises(InteractionPolicyError):
        validate_search_intent(search(max_results=limit), allowed_origins=ORIGINS)


def test_search_rejects_unknown_filter_fields_operators_and_unbounded_filters():
    with pytest.raises(InteractionPolicyError):
        validate_search_intent(search(filters=[{"field": "password", "operator": "eq", "value": "x"}]), allowed_origins=ORIGINS)
    with pytest.raises(InteractionPolicyError):
        validate_search_intent(search(filters=[{"field": "title", "operator": "regex", "value": ".*"}]), allowed_origins=ORIGINS)
    with pytest.raises(InteractionPolicyError):
        validate_search_intent(search(filters=[{"field": "title", "operator": "eq", "value": "x"}] * 11), allowed_origins=ORIGINS)


def test_search_rejects_cross_origin_and_prohibited_terms():
    with pytest.raises(InteractionPolicyError):
        validate_search_intent(search(origin="https://evil.example/"), allowed_origins=ORIGINS)
    with pytest.raises(InteractionPolicyError):
        validate_search_intent(search(query="buy now"), allowed_origins=ORIGINS)


def test_navigation_plan_is_finite_unique_and_exact_origin_bound():
    plan = validate_navigation_plan({
        "plan_id": "plan_0000001",
        "steps": [
            {"step_id": "step_000001", "url": "https://example.com/one"},
            {"step_id": "step_000002", "url": "https://example.com/two"},
        ],
        "max_runtime_seconds": 30,
    }, allowed_origins=ORIGINS)
    assert len(plan.steps) == 2


def test_navigation_rejects_origin_escape_duplicate_ids_and_excess_steps():
    base = {"plan_id": "plan_0000001", "steps": [
        {"step_id": "step_000001", "url": "https://example.com/one"}
    ], "max_runtime_seconds": 30}
    with pytest.raises(InteractionPolicyError):
        validate_navigation_plan({**base, "steps": [{"step_id": "step_000001", "url": "https://evil.example"}]}, allowed_origins=ORIGINS)
    with pytest.raises(InteractionPolicyError):
        validate_navigation_plan({**base, "steps": base["steps"] * 2}, allowed_origins=ORIGINS)
    with pytest.raises(InteractionPolicyError):
        validate_navigation_plan({**base, "steps": base["steps"] * 9}, allowed_origins=ORIGINS)


def test_navigation_rejects_invalid_runtime_and_unknown_keys():
    base = {"plan_id": "plan_0000001", "steps": [
        {"step_id": "step_000001", "url": "https://example.com/one"}
    ], "max_runtime_seconds": 61}
    with pytest.raises(InteractionPolicyError):
        validate_navigation_plan(base, allowed_origins=ORIGINS)
    with pytest.raises(InteractionPolicyError):
        validate_navigation_plan({**base, "run_anyway": True}, allowed_origins=ORIGINS)
