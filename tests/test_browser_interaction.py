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


def _click_evidence(**overrides):
    raw = {
        "interaction_id": "click_0000001",
        "page_id": "page_0000001",
        "origin": "https://example.com/catalog",
        "locator": {"kind": "role", "value": "link"},
        "match_count": 1,
        "visible": True,
        "enabled": True,
        "element_type": "link",
        "href": "https://example.com/help",
        "observed_at": 98,
    }
    raw.update(overrides)
    return raw


def _fill_evidence(**overrides):
    raw = {
        "interaction_id": "fill_0000001",
        "page_id": "page_0000001",
        "origin": "https://example.com/form",
        "locator": {"kind": "label", "value": "Display name"},
        "match_count": 1,
        "visible": True,
        "enabled": True,
        "element_type": "input_text",
        "href": None,
        "observed_at": 98,
    }
    raw.update(overrides)
    return raw


def test_target_evidence_accepts_fresh_unique_visible_link():
    from core.browser_interaction import validate_target_evidence

    intent = validate_click_intent(click(), allowed_origins=ORIGINS)
    evidence = validate_target_evidence(
        _click_evidence(), intent=intent, allowed_origins=ORIGINS, now_epoch=100
    )
    assert evidence.href == intent.destination_url
    assert evidence.observed_at == 98


@pytest.mark.parametrize("changes", [
    {"match_count": 0},
    {"match_count": 2},
    {"visible": False},
    {"enabled": False},
    {"page_id": "page_0000002"},
    {"interaction_id": "click_0000002"},
    {"href": "https://example.com/other"},
    {"origin": "https://evil.example/"},
    {"observed_at": 90},
    {"observed_at": 101},
    {"element_type": "button"},
])
def test_target_evidence_rejects_ambiguous_stale_or_changed_link(changes):
    from core.browser_interaction import validate_target_evidence

    intent = validate_click_intent(click(), allowed_origins=ORIGINS)
    with pytest.raises(InteractionPolicyError):
        validate_target_evidence(
            _click_evidence(**changes), intent=intent,
            allowed_origins=ORIGINS, now_epoch=100,
        )


def test_target_evidence_rejects_non_boolean_flags_and_unknown_fields():
    from core.browser_interaction import validate_target_evidence

    intent = validate_click_intent(click(), allowed_origins=ORIGINS)
    with pytest.raises(InteractionPolicyError):
        validate_target_evidence(
            _click_evidence(visible=1), intent=intent,
            allowed_origins=ORIGINS, now_epoch=100,
        )
    with pytest.raises(InteractionPolicyError):
        validate_target_evidence(
            {**_click_evidence(), "dom_snapshot": "untrusted"},
            intent=intent, allowed_origins=ORIGINS, now_epoch=100,
        )


def test_target_evidence_accepts_matching_draft_form_control():
    from core.browser_interaction import validate_target_evidence

    intent = validate_fill_intent(fill(), allowed_origins=ORIGINS)
    evidence = validate_target_evidence(
        _fill_evidence(), intent=intent, allowed_origins=ORIGINS, now_epoch=100
    )
    assert evidence.element_type == "input_text"


@pytest.mark.parametrize("changes", [
    {"element_type": "input_email"},
    {"element_type": "button"},
    {"href": "https://example.com/submit"},
    {"locator": {"kind": "label", "value": "Other field"}},
])
def test_target_evidence_rejects_form_control_type_or_locator_mismatch(changes):
    from core.browser_interaction import validate_target_evidence

    intent = validate_fill_intent(fill(), allowed_origins=ORIGINS)
    with pytest.raises(InteractionPolicyError):
        validate_target_evidence(
            _fill_evidence(**changes), intent=intent,
            allowed_origins=ORIGINS, now_epoch=100,
        )


def test_target_evidence_rejects_forged_intent_dataclass():
    from core.browser_interaction import FillIntent, validate_target_evidence

    forged = FillIntent(
        "fill_0000001", "page_0000001", "https://example.com/form",
        "label", "Display name", "password", "secret",
    )
    with pytest.raises(InteractionPolicyError):
        validate_target_evidence(
            _fill_evidence(), intent=forged,
            allowed_origins=ORIGINS, now_epoch=100,
        )


def _search_result(**overrides):
    raw = {
        "title": "Public guide",
        "url": "https://example.com/docs/guide?q=public&access_token=do-not-keep-this",
        "snippet": "Public description",
        "source_page_id": "page_0000001",
        "visible": True,
    }
    raw.update(overrides)
    return raw


def test_search_results_are_bounded_deduplicated_and_redacted():
    from core.browser_interaction import validate_search_results

    intent = validate_search_intent(search(), allowed_origins=ORIGINS)
    results = validate_search_results([
        _search_result(snippet="Contact user@example.com or +1 202 555 0199. Bearer abcdefghijklmnop"),
        _search_result(),
    ], intent=intent, allowed_origins=ORIGINS)
    assert len(results) == 1
    assert "[redacted-email]" in results[0].snippet
    assert "[redacted-phone]" in results[0].snippet
    assert "Bearer [redacted]" in results[0].snippet
    assert "access_token" not in results[0].url
    assert "q=public" in results[0].url


@pytest.mark.parametrize("changes", [
    {"visible": False},
    {"visible": 1},
    {"source_page_id": "page_0000002"},
    {"url": "https://evil.example/result"},
    {"title": "x" * 201},
    {"snippet": "x" * 1001},
    {"extra": "hidden"},
])
def test_search_results_reject_untrusted_or_unbounded_records(changes):
    from core.browser_interaction import validate_search_results

    intent = validate_search_intent(search(), allowed_origins=ORIGINS)
    with pytest.raises(InteractionPolicyError):
        validate_search_results(
            [_search_result(**changes)], intent=intent, allowed_origins=ORIGINS
        )


def test_search_results_reject_result_count_above_approved_limit():
    from core.browser_interaction import validate_search_results

    intent = validate_search_intent(search(max_results=1), allowed_origins=ORIGINS)
    with pytest.raises(InteractionPolicyError):
        validate_search_results(
            [_search_result(), _search_result(url="https://example.com/another")],
            intent=intent, allowed_origins=ORIGINS,
        )


def test_search_results_revalidate_forged_search_intent():
    from core.browser_interaction import SearchIntent, validate_search_results

    forged = SearchIntent(
        "search_000001", "page_0000001", "https://example.com/search",
        "buy now", (), 10,
    )
    with pytest.raises(InteractionPolicyError):
        validate_search_results(
            [_search_result()], intent=forged, allowed_origins=ORIGINS
        )


def test_search_results_remove_api_keys_and_reject_excessive_query_parameters():
    from core.browser_interaction import validate_search_results

    intent = validate_search_intent(search(), allowed_origins=ORIGINS)
    safe = validate_search_results([
        _search_result(url="https://example.com/docs?api-key=private123456&q=ok")
    ], intent=intent, allowed_origins=ORIGINS)
    assert "api-key" not in safe[0].url
    assert "q=ok" in safe[0].url

    many = "&".join(f"p{i}=v" for i in range(101))
    with pytest.raises(InteractionPolicyError):
        validate_search_results(
            [_search_result(url=f"https://example.com/docs?{many}")],
            intent=intent, allowed_origins=ORIGINS,
        )


def test_search_results_reject_malformed_forged_filter_tuple():
    from core.browser_interaction import SearchIntent, validate_search_results

    forged = SearchIntent(
        "search_000001", "page_0000001", "https://example.com/search",
        "annual report", ({"field": "title", "operator": "eq", "value": "x"},), 10,
    )
    with pytest.raises(InteractionPolicyError):
        validate_search_results(
            [_search_result()], intent=forged, allowed_origins=ORIGINS
        )


@pytest.mark.parametrize("forged", [
    ("field_type", ["text"]),
    ("field_type", None),
    ("value", ["draft"]),
    ("value", "Please buy now"),
])
def test_target_evidence_rejects_malformed_or_prohibited_forged_fill_intent(forged):
    from core.browser_interaction import FillIntent, validate_target_evidence

    field, value = forged
    values = {
        "interaction_id": "fill_0000001",
        "page_id": "page_0000001",
        "origin": "https://example.com/form",
        "locator_kind": "label",
        "locator_value": "Display name",
        "field_type": "text",
        "value": "Sample User",
    }
    values[field] = value
    intent = FillIntent(**values)
    with pytest.raises(InteractionPolicyError):
        validate_target_evidence(
            _fill_evidence(), intent=intent,
            allowed_origins=ORIGINS, now_epoch=100,
        )


@pytest.mark.parametrize("element_type", [None, [], {}, 1])
def test_target_evidence_rejects_non_string_element_type(element_type):
    from core.browser_interaction import validate_target_evidence

    intent = validate_click_intent(click(), allowed_origins=ORIGINS)
    with pytest.raises(InteractionPolicyError):
        validate_target_evidence(
            _click_evidence(element_type=element_type), intent=intent,
            allowed_origins=ORIGINS, now_epoch=100,
        )


@pytest.mark.parametrize("secret_key", [
    "access-token", "refresh-token", "client-secret", "session-id",
    "id-token", "x-xsrf-token", "credential", "jwt",
])
def test_search_result_url_removes_hyphenated_and_common_auth_parameters(secret_key):
    from core.browser_interaction import validate_search_results

    intent = validate_search_intent(search(), allowed_origins=ORIGINS)
    result = validate_search_results(
        [_search_result(url=f"https://example.com/docs?{secret_key}=private123456&topic=public")],
        intent=intent, allowed_origins=ORIGINS,
    )[0]
    assert secret_key not in result.url
    assert "private123456" not in result.url
    assert "topic=public" in result.url


@pytest.mark.parametrize("private_path", [
    "/profiles/user%40example.com",
    "/records/202-555-0199",
    "/reset/password=supersecretvalue",
])
def test_search_result_url_redacts_sensitive_identifiers_from_path(private_path):
    from urllib.parse import quote
    from core.browser_interaction import validate_search_results

    intent = validate_search_intent(search(), allowed_origins=ORIGINS)
    result = validate_search_results(
        [_search_result(url=f"https://example.com{private_path}?topic=public")],
        intent=intent, allowed_origins=ORIGINS,
    )[0]
    assert "[redacted-path]" in result.url
    assert "topic=public" in result.url
    assert "user%40example.com" not in result.url
    assert "202-555-0199" not in result.url
    assert "supersecretvalue" not in result.url
