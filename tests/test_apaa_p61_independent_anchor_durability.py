"""P61 conformance tests for independent monotonic anchor durability.

The backend below is a deterministic reference model, not a production anchor.
These tests specify invariants that a real independently administered adapter
must satisfy before it can be qualified.
"""
import base64
import json
import threading

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from core.inspector_trust_sequence import (
    InspectorTrustSequenceError,
    accept_signed_inspector_trust_bundle,
)
ISSUER = "control:root-001"


class DurableReferenceAnchor:
    """Thread-safe reference model with durable-store and anti-rollback semantics."""

    def __init__(self, store=None):
        self.store = {} if store is None else store
        self.lock = threading.Lock()
        self.restore_floor = dict(self.store)

    def read_sequence(self, issuer_key_id):
        with self.lock:
            return self.store.get(issuer_key_id, 0)

    def advance_sequence(self, issuer_key_id, *, expected_current, new_sequence):
        with self.lock:
            current = self.store.get(issuer_key_id, 0)
            if current != expected_current or new_sequence <= current:
                return False
            self.store[issuer_key_id] = new_sequence
            self.restore_floor[issuer_key_id] = max(
                self.restore_floor.get(issuer_key_id, 0), new_sequence
            )
            return True

    def backup(self):
        with self.lock:
            return dict(self.store)

    def restore(self, snapshot):
        with self.lock:
            for issuer, floor in self.restore_floor.items():
                if snapshot.get(issuer, 0) < floor:
                    raise RuntimeError("backup restore would roll back monotonic state")
            self.store.clear()
            self.store.update(snapshot)


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
        "issuer_key_id": ISSUER,
        "payload": payload,
    }
    signature = root.sign(json.dumps(
        signed, sort_keys=True, separators=(",", ":")
    ).encode())
    envelope = {
        **signed,
        "signature": base64.b64encode(signature).decode(),
    }
    return public, json.dumps(envelope)


def _accept(public, raw, backend):
    return accept_signed_inspector_trust_bundle(
        raw,
        root_public_key=public,
        expected_issuer_key_id=ISSUER,
        sequence_backend=backend,
        now=150,
    )


def test_sequence_survives_backend_recreation_after_durable_commit():
    public, raw = _bundle(sequence=4)
    durable_store = {}
    first_process = DurableReferenceAnchor(durable_store)
    _accept(public, raw, first_process)
    assert durable_store[ISSUER] == 4

    # New adapter instance models process restart against the same durable store.
    restarted_process = DurableReferenceAnchor(durable_store)
    assert restarted_process.read_sequence(ISSUER) == 4

    with pytest.raises(InspectorTrustSequenceError, match="rejected"):
        _accept(public, raw, restarted_process)
    assert durable_store[ISSUER] == 4


def test_old_backup_cannot_lower_committed_high_water_mark():
    public, raw = _bundle(sequence=4)
    anchor = DurableReferenceAnchor()
    old_backup = anchor.backup()
    _accept(public, raw, anchor)
    assert anchor.read_sequence(ISSUER) == 4

    with pytest.raises(RuntimeError, match="roll back"):
        anchor.restore(old_backup)
    assert anchor.read_sequence(ISSUER) == 4


def test_current_or_newer_backup_can_be_restored_without_rollback():
    public, raw = _bundle(sequence=4)
    anchor = DurableReferenceAnchor()
    _accept(public, raw, anchor)
    current_backup = anchor.backup()
    anchor.restore(current_backup)
    assert anchor.read_sequence(ISSUER) == 4


def test_concurrent_sequence_advances_have_exactly_one_winner():
    anchor = DurableReferenceAnchor()
    barrier = threading.Barrier(2)
    results = []

    def contender(new_value):
        barrier.wait()
        results.append(anchor.advance_sequence(
            ISSUER, expected_current=0, new_sequence=new_value
        ))

    threads = [
        threading.Thread(target=contender, args=(1,)),
        threading.Thread(target=contender, args=(2,)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=3)
        assert not thread.is_alive()

    assert sorted(results) == [False, True]
    assert anchor.read_sequence(ISSUER) in (1, 2)


def test_anchor_rejects_non_increasing_or_stale_compare_and_swap():
    anchor = DurableReferenceAnchor()
    assert anchor.advance_sequence(ISSUER, expected_current=0, new_sequence=3) is True
    assert anchor.advance_sequence(ISSUER, expected_current=0, new_sequence=4) is False
    assert anchor.advance_sequence(ISSUER, expected_current=3, new_sequence=3) is False
    assert anchor.read_sequence(ISSUER) == 3


def test_restore_of_newer_backup_does_not_reduce_sequence():
    anchor = DurableReferenceAnchor()
    anchor.advance_sequence(ISSUER, expected_current=0, new_sequence=2)
    newer_backup = anchor.backup()
    anchor.advance_sequence(ISSUER, expected_current=2, new_sequence=5)
    with pytest.raises(RuntimeError, match="roll back"):
        anchor.restore(newer_backup)
    assert anchor.read_sequence(ISSUER) == 5
