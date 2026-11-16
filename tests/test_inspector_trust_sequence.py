import base64
import json

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from core.inspector_trust_sequence import (
    InspectorTrustSequenceError,
    accept_signed_inspector_trust_bundle,
)


class MemoryMonotonicAnchor:
    """Test-only CAS fake; production must use an independent anti-rollback anchor."""

    def __init__(self, initial=0, *, race=False):
        self.sequence = initial
        self.race = race

    def read_sequence(self, issuer_key_id):
        assert issuer_key_id == "control:root-001"
        return self.sequence

    def advance_sequence(self, issuer_key_id, *, expected_current, new_sequence):
        assert issuer_key_id == "control:root-001"
        if self.race or self.sequence != expected_current:
            return False
        if new_sequence <= expected_current:
            return False
        self.sequence = new_sequence
        return True


def _bundle(sequence=4):
    root = Ed25519PrivateKey.generate()
    public = root.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    payload = {
        "schema_version": 1,
        "sequence": sequence,
        "issued_at": 100,
        "expires_at": 300,
        "keys": [{
            "key_id": "inspector:worker-001",
            "public_key": base64.b64encode(bytes([7]) * 32).decode(),
            "not_before": 100,
            "not_after": 250,
            "revoked": False,
        }],
    }
    signed = {
        "schema_version": 1,
        "issuer_key_id": "control:root-001",
        "payload": payload,
    }
    envelope = {
        **signed,
        "signature": base64.b64encode(
            root.sign(json.dumps(signed, sort_keys=True, separators=(",", ":")).encode())
        ).decode(),
    }
    return public, json.dumps(envelope)


def test_accepts_bundle_only_after_advancing_monotonic_anchor():
    public, raw = _bundle()
    anchor = MemoryMonotonicAnchor(initial=3)
    registry, sequence = accept_signed_inspector_trust_bundle(
        raw,
        root_public_key=public,
        expected_issuer_key_id="control:root-001",
        sequence_backend=anchor,
        now=150,
    )
    assert sequence == 4
    assert anchor.sequence == 4
    assert registry.require_active_key("inspector:worker-001", now=150) == bytes([7]) * 32


def test_rejects_replay_and_does_not_change_anchor():
    public, raw = _bundle()
    anchor = MemoryMonotonicAnchor(initial=4)
    with pytest.raises(InspectorTrustSequenceError, match="rejected"):
        accept_signed_inspector_trust_bundle(
            raw, root_public_key=public,
            expected_issuer_key_id="control:root-001",
            sequence_backend=anchor, now=150,
        )
    assert anchor.sequence == 4


def test_rejects_concurrent_compare_and_swap_race():
    public, raw = _bundle()
    anchor = MemoryMonotonicAnchor(initial=3, race=True)
    with pytest.raises(InspectorTrustSequenceError, match="concurrently"):
        accept_signed_inspector_trust_bundle(
            raw, root_public_key=public,
            expected_issuer_key_id="control:root-001",
            sequence_backend=anchor, now=150,
        )
    assert anchor.sequence == 3


def test_rejects_backend_without_monotonic_contract():
    public, raw = _bundle()
    with pytest.raises(TypeError, match="monotonic sequence backend"):
        accept_signed_inspector_trust_bundle(
            raw, root_public_key=public,
            expected_issuer_key_id="control:root-001",
            sequence_backend=object(), now=150,
        )


def test_rejects_invalid_anchor_value():
    class InvalidAnchor(MemoryMonotonicAnchor):
        def read_sequence(self, issuer_key_id):
            return -1

    public, raw = _bundle()
    with pytest.raises(InspectorTrustSequenceError, match="invalid value"):
        accept_signed_inspector_trust_bundle(
            raw, root_public_key=public,
            expected_issuer_key_id="control:root-001",
            sequence_backend=InvalidAnchor(), now=150,
        )
