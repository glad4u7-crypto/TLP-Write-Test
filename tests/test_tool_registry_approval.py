from datetime import datetime, timedelta, timezone

import pytest

from core.approval import ApprovalManager
from core.tool_registry import ToolRegistry, ToolSpec, build_default_registry


def test_default_registry_is_metadata_only_and_disabled():
    registry = build_default_registry()
    assert {item.tool_id for item in registry.list_tools()} == {
        "repository.inspect_zip", "web.search", "browser.navigate", "file.modify"
    }
    assert all(item.enabled is False for item in registry.list_tools())


def test_registry_rejects_duplicate_ids_and_enabled_tools():
    registry = ToolRegistry()
    spec = ToolSpec("demo.read", "Demo", "Read demo", "local_read", True)
    registry.register(spec)
    with pytest.raises(ValueError):
        registry.register(spec)
    with pytest.raises(ValueError):
        ToolSpec("unsafe", "Unsafe", "Enabled tool", "local_read", True, enabled=True)


def test_registry_rejects_invalid_types_and_empty_metadata():
    registry = ToolRegistry()
    with pytest.raises(TypeError):
        registry.register(object())
    with pytest.raises(ValueError):
        ToolSpec("", "Name", "Description", "local_read", True)


def test_mutation_request_is_pending_until_explicit_decision():
    registry = build_default_registry()
    manager = ApprovalManager(registry)
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    item = manager.request("file.modify", "Edit a local note", {"path": "note.txt"}, now)
    assert item.status == "pending"
    assert manager.get(item.request_id) == item
    decided = manager.decide(item.request_id, True, "User confirmed", now + timedelta(seconds=1))
    assert decided.status == "approved"
    assert decided.decision_note == "User confirmed"


def test_rejection_is_final_and_cannot_be_reversed():
    manager = ApprovalManager(build_default_registry())
    item = manager.request("file.modify", "Change a file", {}, datetime(2026, 1, 1, tzinfo=timezone.utc))
    rejected = manager.decide(item.request_id, False)
    assert rejected.status == "rejected"
    with pytest.raises(ValueError):
        manager.decide(item.request_id, True)


def test_request_expires_and_cannot_be_approved_after_deadline():
    manager = ApprovalManager(build_default_registry(), ttl_minutes=1)
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    item = manager.request("file.modify", "Change a file", {}, now)
    expired = manager.decide(item.request_id, True, now=now + timedelta(minutes=1))
    assert expired.status == "expired"


def test_approval_is_bound_to_canonical_payload_digest():
    manager = ApprovalManager(build_default_registry())
    item_a = manager.request("file.modify", "Change a file", {"b": 2, "a": 1})
    item_b = manager.request("file.modify", "Change a file", {"a": 1, "b": 2})
    item_c = manager.request("file.modify", "Change a file", {"a": 9, "b": 2})
    assert item_a.payload_digest == item_b.payload_digest
    assert item_a.payload_digest != item_c.payload_digest


def test_non_json_payload_and_naive_datetime_are_rejected():
    manager = ApprovalManager(build_default_registry())
    with pytest.raises(ValueError):
        manager.request("file.modify", "Bad payload", {"not_json": object()})
    with pytest.raises(ValueError):
        manager.request("file.modify", "Bad time", {}, datetime(2026, 1, 1))


def test_unknown_tool_and_empty_summary_are_rejected():
    manager = ApprovalManager(build_default_registry())
    with pytest.raises(ValueError):
        manager.request("not.registered", "Try it", {})
    with pytest.raises(ValueError):
        manager.request("file.modify", "  ", {})


def test_explicitly_blocked_action_category_cannot_be_requested():
    registry = ToolRegistry()
    registry.register(ToolSpec("trade.place", "Place trade", "Blocked", "trading", False))
    manager = ApprovalManager(registry)
    with pytest.raises(ValueError):
        manager.request("trade.place", "Place a trade", {"symbol": "XYZ"})


def test_approval_ttl_is_bounded():
    with pytest.raises(ValueError):
        ApprovalManager(build_default_registry(), ttl_minutes=0)
    with pytest.raises(ValueError):
        ApprovalManager(build_default_registry(), ttl_minutes=1441)


def test_credentials_are_rejected_from_approval_payload():
    manager = ApprovalManager(build_default_registry())
    with pytest.raises(ValueError):
        manager.request("file.modify", "Do not include secrets", {"api_key": "secret-value"})


def test_approval_decision_requires_a_boolean():
    manager = ApprovalManager(build_default_registry())
    item = manager.request("file.modify", "Change a file", {})
    with pytest.raises(ValueError):
        manager.decide(item.request_id, "yes")
