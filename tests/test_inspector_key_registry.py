import pytest

from core.inspector_key_registry import (
    InspectorPublicKeyRegistry,
    InspectorPublicKeyRegistryError,
    InspectorPublicKeyRecord,
)


def _record(key_id="inspector:key-001", key_byte=1, **overrides):
    values = {
        "key_id": key_id,
        "public_key": bytes([key_byte]) * 32,
        "not_before": 100,
        "not_after": 200,
        "revoked": False,
    }
    values.update(overrides)
    return InspectorPublicKeyRecord(**values)


def test_registry_returns_only_keys_inside_validity_window():
    registry = InspectorPublicKeyRegistry([
        _record(),
        _record("inspector:key-future", 2, not_before=150),
        _record("inspector:key-expired", 3, not_after=100),
        _record("inspector:key-revoked", 4, revoked=True),
    ])

    assert registry.active_public_keys(now=100) == {
        "inspector:key-001": bytes([1]) * 32,
    }
    assert registry.active_public_keys(now=150) == {
        "inspector:key-001": bytes([1]) * 32,
        "inspector:key-future": bytes([2]) * 32,
    }
    assert registry.active_public_keys(now=200) == {}


def test_registry_supports_explicit_rotation_overlap_without_private_keys():
    old_key = _record("inspector:key-old", 1, not_after=160)
    new_key = _record("inspector:key-new", 2, not_before=140)
    registry = InspectorPublicKeyRegistry([old_key, new_key])

    assert set(registry.active_public_keys(now=150)) == {
        "inspector:key-old", "inspector:key-new",
    }
    assert set(registry.active_public_keys(now=160)) == {"inspector:key-new"}


def test_revoked_key_is_rejected_even_inside_validity_window():
    registry = InspectorPublicKeyRegistry([_record(revoked=True)])
    assert registry.active_public_keys(now=150) == {}
    with pytest.raises(InspectorPublicKeyRegistryError, match="not currently trusted"):
        registry.require_active_key("inspector:key-001", now=150)


def test_registry_rejects_duplicate_ids_and_duplicate_public_key_material():
    with pytest.raises(InspectorPublicKeyRegistryError, match="Duplicate.*identifier"):
        InspectorPublicKeyRegistry([_record(), _record(key_byte=2)])
    with pytest.raises(InspectorPublicKeyRegistryError, match="multiple IDs"):
        InspectorPublicKeyRegistry([
            _record("inspector:key-one"),
            _record("inspector:key-two"),
        ])


@pytest.mark.parametrize("record", [
    _record(key_id="x"),
    _record(public_key=b"short"),
    _record(not_before=-1),
    _record(not_before=200, not_after=200),
    _record(revoked=1),
])
def test_registry_rejects_malformed_trust_records(record):
    with pytest.raises(InspectorPublicKeyRegistryError):
        InspectorPublicKeyRegistry([record])


def test_registry_rejects_untyped_records_and_invalid_evaluation_time():
    with pytest.raises(TypeError):
        InspectorPublicKeyRegistry([{"key_id": "inspector:key-001"}])
    registry = InspectorPublicKeyRegistry([_record()])
    with pytest.raises(InspectorPublicKeyRegistryError):
        registry.active_public_keys(now=True)
    with pytest.raises(InspectorPublicKeyRegistryError):
        registry.require_active_key("unknown:key-001", now=150)


def test_registry_snapshot_is_immutable_and_returns_fresh_mappings():
    source = [_record()]
    registry = InspectorPublicKeyRegistry(source)
    source.clear()
    first = registry.active_public_keys(now=150)
    first.clear()
    assert registry.active_public_keys(now=150) == {
        "inspector:key-001": bytes([1]) * 32,
    }
