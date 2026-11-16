"""P60 protected signing-key lifecycle policy tests.

These tests exercise staged public-key rotation and revocation using signed
trust bundles. They do not claim to qualify a physical PKCS#11 token/HSM.
"""
import base64
import json

import pytest
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from core.inspector_trust_sequence import (
    InspectorTrustSequenceError,
    accept_signed_inspector_trust_bundle,
)


ISSUER = "control:root-001"
OLD_ID = "inspector:signer-old"
NEW_ID = "inspector:signer-new"


class MemoryMonotonicAnchor:
    """Disposable test fake; not a production anti-rollback anchor."""

    def __init__(self):
        self.sequence = 0
        self.fail_advance = False

    def read_sequence(self, issuer_key_id):
        assert issuer_key_id == ISSUER
        return self.sequence

    def advance_sequence(self, issuer_key_id, *, expected_current, new_sequence):
        assert issuer_key_id == ISSUER
        if self.fail_advance or self.sequence != expected_current:
            return False
        if new_sequence <= expected_current:
            return False
        self.sequence = new_sequence
        return True


def _raw_public(key):
    return key.public_key().public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    )


def _signed_bundle(root, sequence, records):
    payload = {
        "schema_version": 1,
        "sequence": sequence,
        "issued_at": 100,
        "expires_at": 500,
        "keys": [
            {
                "key_id": key_id,
                "public_key": base64.b64encode(_raw_public(key)).decode("ascii"),
                "not_before": 100,
                "not_after": 450,
                "revoked": revoked,
            }
            for key_id, key, revoked in records
        ],
    }
    signed = {
        "schema_version": 1,
        "issuer_key_id": ISSUER,
        "payload": payload,
    }
    canonical = json.dumps(
        signed, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
    ).encode("utf-8")
    envelope = {
        **signed,
        "signature": base64.b64encode(root.sign(canonical)).decode("ascii"),
    }
    return json.dumps(envelope)


def _accept(raw, root_public, anchor):
    return accept_signed_inspector_trust_bundle(
        raw,
        root_public_key=root_public,
        expected_issuer_key_id=ISSUER,
        sequence_backend=anchor,
        now=200,
    )


def test_staged_rotation_keeps_old_and_new_keys_during_overlap_then_revokes_old():
    root = Ed25519PrivateKey.generate()
    root_public = _raw_public(root)
    old_signer = Ed25519PrivateKey.generate()
    new_signer = Ed25519PrivateKey.generate()
    anchor = MemoryMonotonicAnchor()

    # Stage 1: original signer is trusted.
    first, seq = _accept(
        _signed_bundle(root, 1, [(OLD_ID, old_signer, False)]),
        root_public, anchor,
    )
    assert seq == 1
    assert first.require_active_key(OLD_ID, now=200) == _raw_public(old_signer)

    # Stage 2: publish new key before retiring old key (safe overlap).
    overlap, seq = _accept(
        _signed_bundle(root, 2, [
            (OLD_ID, old_signer, False),
            (NEW_ID, new_signer, False),
        ]),
        root_public, anchor,
    )
    assert seq == 2
    assert overlap.require_active_key(OLD_ID, now=200) == _raw_public(old_signer)
    assert overlap.require_active_key(NEW_ID, now=200) == _raw_public(new_signer)

    # Both signatures verify during the explicitly authorized overlap.
    message = b"APAA P60 rotation overlap test"
    old_sig = old_signer.sign(message)
    new_sig = new_signer.sign(message)
    Ed25519PublicKey.from_public_bytes(overlap.require_active_key(OLD_ID, now=200)).verify(old_sig, message)
    Ed25519PublicKey.from_public_bytes(overlap.require_active_key(NEW_ID, now=200)).verify(new_sig, message)

    # Stage 3: revoke old key while retaining new key.
    final, seq = _accept(
        _signed_bundle(root, 3, [
            (OLD_ID, old_signer, True),
            (NEW_ID, new_signer, False),
        ]),
        root_public, anchor,
    )
    assert seq == 3
    assert final.require_active_key(NEW_ID, now=200) == _raw_public(new_signer)
    with pytest.raises(ValueError, match="not currently trusted"):
        final.require_active_key(OLD_ID, now=200)

    # A previously valid bundle cannot re-enable the retired signer.
    with pytest.raises(InspectorTrustSequenceError, match="rejected"):
        _accept(
            _signed_bundle(root, 2, [
                (OLD_ID, old_signer, False),
                (NEW_ID, new_signer, False),
            ]),
            root_public, anchor,
        )
    assert anchor.sequence == 3


def test_rotation_is_not_accepted_if_anchor_cas_fails():
    root = Ed25519PrivateKey.generate()
    root_public = _raw_public(root)
    old_signer = Ed25519PrivateKey.generate()
    new_signer = Ed25519PrivateKey.generate()
    anchor = MemoryMonotonicAnchor()
    _accept(_signed_bundle(root, 1, [(OLD_ID, old_signer, False)]), root_public, anchor)

    anchor.fail_advance = True
    with pytest.raises(InspectorTrustSequenceError, match="concurrently"):
        _accept(
            _signed_bundle(root, 2, [
                (OLD_ID, old_signer, False),
                (NEW_ID, new_signer, False),
            ]),
            root_public, anchor,
        )
    assert anchor.sequence == 1


def test_tampered_rotation_bundle_does_not_advance_anchor():
    root = Ed25519PrivateKey.generate()
    root_public = _raw_public(root)
    old_signer = Ed25519PrivateKey.generate()
    anchor = MemoryMonotonicAnchor()
    raw = _signed_bundle(root, 1, [(OLD_ID, old_signer, False)])
    envelope = json.loads(raw)
    envelope["payload"]["keys"][0]["revoked"] = True

    with pytest.raises(InspectorTrustSequenceError, match="rejected"):
        _accept(json.dumps(envelope), root_public, anchor)
    assert anchor.sequence == 0
