import base64
import json

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from core.inspector_trust_bundle import (
    InspectorTrustBundleError,
    load_signed_inspector_trust_bundle,
)


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def _signed_bundle(*, sequence=4, issued_at=100, expires_at=300, revoked=False):
    root = Ed25519PrivateKey.generate()
    root_public = root.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    payload = {
        "schema_version": 1,
        "sequence": sequence,
        "issued_at": issued_at,
        "expires_at": expires_at,
        "keys": [{
            "key_id": "inspector:worker-001",
            "public_key": base64.b64encode(bytes([7]) * 32).decode(),
            "not_before": 100,
            "not_after": 250,
            "revoked": revoked,
        }],
    }
    signed = {"schema_version": 1, "issuer_key_id": "control:root-001", "payload": payload}
    envelope = {
        **signed,
        "signature": base64.b64encode(root.sign(_canonical(signed))).decode(),
    }
    return root_public, json.dumps(envelope), envelope


def test_signed_bundle_loads_public_keys_and_sequence():
    root_public, raw, _ = _signed_bundle()
    registry, sequence = load_signed_inspector_trust_bundle(
        raw, root_public_key=root_public,
        expected_issuer_key_id="control:root-001",
        minimum_sequence=3, now=150,
    )
    assert sequence == 4
    assert registry.require_active_key("inspector:worker-001", now=150) == bytes([7]) * 32


def test_bundle_rejects_tampering_and_wrong_pinned_root():
    root_public, raw, envelope = _signed_bundle()
    envelope["payload"]["sequence"] = 5
    with pytest.raises(InspectorTrustBundleError, match="signature"):
        load_signed_inspector_trust_bundle(
            json.dumps(envelope), root_public_key=root_public,
            expected_issuer_key_id="control:root-001", minimum_sequence=1, now=150,
        )
    other_root, valid_raw, _ = _signed_bundle()
    with pytest.raises(InspectorTrustBundleError, match="signature"):
        load_signed_inspector_trust_bundle(
            valid_raw, root_public_key=other_root,
            expected_issuer_key_id="control:root-001", minimum_sequence=1, now=150,
        )


@pytest.mark.parametrize("kwargs,match", [
    ({"minimum_sequence": 5}, "rolled back"),
    ({"minimum_sequence": 0}, "positive integer"),
    ({"expected_issuer_key_id": "control:other-001"}, "pinned issuer"),
    ({"now": 300}, "currently valid"),
    ({"now": 99}, "currently valid"),
])
def test_bundle_rejects_rollback_wrong_issuer_and_invalid_time(kwargs, match):
    root_public, raw, _ = _signed_bundle()
    args = {
        "root_public_key": root_public,
        "expected_issuer_key_id": "control:root-001",
        "minimum_sequence": 1,
        "now": 150,
    }
    args.update(kwargs)
    with pytest.raises(InspectorTrustBundleError, match=match):
        load_signed_inspector_trust_bundle(raw, **args)


def test_bundle_rejects_revoked_only_key_and_duplicate_json_keys():
    root_public, raw, _ = _signed_bundle(revoked=True)
    with pytest.raises(InspectorTrustBundleError, match="no currently active"):
        load_signed_inspector_trust_bundle(
            raw, root_public_key=root_public,
            expected_issuer_key_id="control:root-001", minimum_sequence=1, now=150,
        )
    with pytest.raises(InspectorTrustBundleError, match="Duplicate JSON"):
        load_signed_inspector_trust_bundle(
            '{"schema_version":1,"schema_version":1}',
            root_public_key=root_public,
            expected_issuer_key_id="control:root-001", minimum_sequence=1, now=150,
        )


def test_bundle_rejects_unknown_fields_and_malformed_public_key():
    root_public, _, envelope = _signed_bundle()
    envelope["unexpected"] = True
    with pytest.raises(InspectorTrustBundleError, match="unknown fields"):
        load_signed_inspector_trust_bundle(
            json.dumps(envelope), root_public_key=root_public,
            expected_issuer_key_id="control:root-001", minimum_sequence=1, now=150,
        )
    _, _, malformed = _signed_bundle()
    malformed["payload"]["keys"][0]["public_key"] = "not-base64!"
    signed = {key: malformed[key] for key in ("schema_version", "issuer_key_id", "payload")}
    root = Ed25519PrivateKey.generate()
    root_public2 = root.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    malformed["signature"] = base64.b64encode(root.sign(_canonical(signed))).decode()
    with pytest.raises(InspectorTrustBundleError, match="encoding"):
        load_signed_inspector_trust_bundle(
            json.dumps(malformed), root_public_key=root_public2,
            expected_issuer_key_id="control:root-001", minimum_sequence=1, now=150,
        )
