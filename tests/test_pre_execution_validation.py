import pytest

from core.pre_execution_validation import PreExecutionValidator


def test_read_only_intent_validates_without_approval():
    result = PreExecutionValidator().validate_intent(
        "inspect_repository", {"path": "docs"}
    )
    assert result.valid
    assert not result.requires_approval
    assert result.issues == ()


def test_mutation_is_validated_but_still_requires_approval():
    result = PreExecutionValidator().validate_intent(
        "write_file", {"path": "notes.txt", "content": "draft"}
    )
    assert result.valid
    assert result.requires_approval


@pytest.mark.parametrize("action", [
    "pay_vendor", "purchase_item", "place_order", "external_api",
    "unknown_custom_action", "send_money",
])
def test_prohibited_or_unknown_actions_fail_closed(action):
    result = PreExecutionValidator().validate_intent(action, {})
    assert not result.valid
    assert any(issue.code == "action_blocked" for issue in result.issues)


def test_noncanonical_action_is_rejected():
    result = PreExecutionValidator().validate_intent("Write File", {})
    assert not result.valid
    assert "action_noncanonical" in {issue.code for issue in result.issues}


def test_non_mapping_and_non_json_payloads_are_rejected():
    validator = PreExecutionValidator()
    assert not validator.validate_intent("inspect_repository", []).valid
    assert not validator.validate_intent("inspect_repository", {"bad": object()}).valid


def test_payload_byte_and_depth_limits_are_enforced():
    validator = PreExecutionValidator(max_payload_bytes=32, max_depth=2)
    large = validator.validate_intent("inspect_repository", {"value": "x" * 40})
    deep = validator.validate_intent("inspect_repository", {"a": {"b": {"c": 1}}})
    assert not large.valid
    assert "payload_too_large" in {issue.code for issue in large.issues}
    assert not deep.valid
    assert "payload_too_deep" in {issue.code for issue in deep.issues}


def test_payload_nan_and_infinity_are_rejected():
    validator = PreExecutionValidator()
    assert not validator.validate_intent("inspect_repository", {"value": float("nan")}).valid
    assert not validator.validate_intent("inspect_repository", {"value": float("inf")}).valid


def test_plan_validates_unique_ids_and_each_action():
    result = PreExecutionValidator().validate_plan([
        {"step_id": "one", "action": "inspect_repository", "payload": {}},
        {"step_id": "two", "action": "write_file", "payload": {"path": "a"}},
    ])
    assert result.valid
    assert result.step_count == 2
    assert result.intents[0].requires_approval is False
    assert result.intents[1].requires_approval is True


def test_plan_rejects_duplicate_ids_and_invalid_step():
    result = PreExecutionValidator().validate_plan([
        {"step_id": "same", "action": "inspect_repository", "payload": {}},
        {"step_id": "same", "action": "inspect_repository", "payload": {}},
        "not-a-step",
    ])
    assert not result.valid
    codes = {issue.code for issue in result.issues}
    assert "duplicate_step_id" in codes
    assert "step_type" in codes


def test_plan_step_and_aggregate_payload_limits():
    validator = PreExecutionValidator(
        max_steps=2, max_payload_bytes=64, max_total_payload_bytes=70
    )
    too_many = validator.validate_plan([
        {"step_id": str(i), "action": "inspect_repository", "payload": {}}
        for i in range(3)
    ])
    assert not too_many.valid
    assert "plan_too_large" in {issue.code for issue in too_many.issues}

    too_large_total = validator.validate_plan([
        {"step_id": "a", "action": "inspect_repository", "payload": {"x": "a" * 30}},
        {"step_id": "b", "action": "inspect_repository", "payload": {"x": "b" * 30}},
    ])
    assert not too_large_total.valid
    assert "plan_payload_too_large" in {issue.code for issue in too_large_total.issues}


def test_validator_configuration_rejects_unsafe_bounds():
    with pytest.raises(ValueError):
        PreExecutionValidator(max_steps=0)
    with pytest.raises(ValueError):
        PreExecutionValidator(max_depth=True)
