"""P62 adversarial recovery, crash-boundary and audit-tamper tests.

All keys, stores and anchors are disposable test fixtures. These tests are
software contract evidence only; they do not qualify a physical HSM or an
independently administered production anchor.
"""
from __future__ import annotations

import hashlib
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from core.offline_owner_recovery import (
    AnchorState,
    OfflineOwnerRecoveryService,
    RecoveryDenied,
    RecoveryPolicy,
    RecoveryPublicKey,
    RecoveryRequest,
    SignedRecoveryRequest,
    canonical_request,
)
from core.sqlite_security_store import SQLiteSecurityStore


class _AtomicTestAnchor:
    def __init__(self):
        self._state = AnchorState(0, None, None)
        self._lock = threading.Lock()

    def read(self):
        with self._lock:
            return self._state

    def compare_and_advance(self, *, expected, target):
        with self._lock:
            if self._state != expected or target.revision != expected.revision + 1:
                return False
            self._state = target
            return True


def _keypair():
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return private, public


def _setup(tmp_path):
    operator, operator_public = _keypair()
    approver, approver_public = _keypair()
    policy = RecoveryPolicy(
        (RecoveryPublicKey("operator-key-01", operator_public),),
        (RecoveryPublicKey("approver-key-01", approver_public),),
    )
    store = SQLiteSecurityStore(tmp_path / "security.sqlite3")
    anchor = _AtomicTestAnchor()
    service = OfflineOwnerRecoveryService(store, policy, anchor)
    return service, store, anchor, operator, approver


def _signed(operator, approver, *, change_id="p62-change-001", nonce="a" * 64):
    request = RecoveryRequest(
        change_id=change_id,
        action="rekey",
        expected_revision=0,
        old_generation=None,
        new_generation=hashlib.sha256(change_id.encode("ascii")).hexdigest(),
        reason_code="owner_account_recovery",
        nonce=nonce,
        issued_at=1000,
        expires_at=1600,
        operator_key_id="operator-key-01",
        approver_key_id="approver-key-01",
    )
    message = canonical_request(request)
    return SignedRecoveryRequest(request, operator.sign(message), approver.sign(message))


def test_concurrent_recovery_race_has_one_winner_and_one_audit_entry(tmp_path):
    service, store, anchor, operator, approver = _setup(tmp_path)
    envelopes = [
        _signed(operator, approver, change_id="p62-race-a-001", nonce="1" * 64),
        _signed(operator, approver, change_id="p62-race-b-002", nonce="2" * 64),
    ]
    barrier = threading.Barrier(2)

    def run(envelope):
        barrier.wait(timeout=5)
        try:
            result = service.apply(envelope, now=1100)
            return ("accepted", result.change_id)
        except RecoveryDenied:
            return ("denied", None)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, envelopes))

    assert [status for status, _ in results].count("accepted") == 1
    assert [status for status, _ in results].count("denied") == 1
    assert store.read_global_owner_state().revision == 1
    assert anchor.read().revision == 1
    assert store.verify_audit_chain() is True
    with sqlite3.connect(store._database_path) as db:
        assert db.execute("SELECT COUNT(*) FROM durable_audit_events").fetchone()[0] == 1


def test_crash_during_audit_append_rolls_back_local_state_and_is_resumable(tmp_path):
    service, store, anchor, operator, approver = _setup(tmp_path)
    envelope = _signed(operator, approver)

    # Fail exactly at the durable audit INSERT, after the service has advanced
    # the independent anchor. SQLite must roll back the local owner row too.
    with sqlite3.connect(store._database_path) as db:
        db.execute("""
            CREATE TRIGGER p62_abort_audit_insert
            BEFORE INSERT ON durable_audit_events
            BEGIN SELECT RAISE(ABORT, 'P62 injected audit append crash'); END
        """)
        db.commit()

    with pytest.raises(RecoveryDenied):
        service.apply(envelope, now=1100)

    assert store.read_global_owner_state().revision == 0
    assert anchor.read().revision == 1
    assert service.inspect().disposition == "ANCHOR_AHEAD_RESUMABLE"
    assert store.verify_audit_chain() is True

    with sqlite3.connect(store._database_path) as db:
        db.execute("DROP TRIGGER p62_abort_audit_insert")
        db.commit()

    result = service.apply(envelope, now=1100)
    assert result.revision == 1
    assert service.inspect().disposition == "CONSISTENT"
    assert store.verify_audit_chain() is True


@pytest.mark.parametrize(
    "tamper_sql",
    [
        "UPDATE durable_audit_events SET reason_code='forged_reason' WHERE sequence=1",
        "UPDATE durable_audit_events SET entry_hash=lower(hex(randomblob(32))) WHERE sequence=1",
        "DELETE FROM durable_audit_events WHERE sequence=1",
    ],
)
def test_audit_field_hash_or_deletion_tampering_blocks_recovery(tmp_path, tamper_sql):
    service, store, anchor, operator, approver = _setup(tmp_path)
    first = _signed(operator, approver)
    service.apply(first, now=1100)
    assert store.verify_audit_chain() is True

    with sqlite3.connect(store._database_path) as db:
        db.execute(tamper_sql)
        db.commit()

    assert store.verify_audit_chain() is False
    next_request = RecoveryRequest(
        change_id="p62-change-next",
        action="rekey",
        expected_revision=1,
        old_generation=store.read_global_owner_state().generation,
        new_generation=hashlib.sha256(b"next-generation").hexdigest(),
        reason_code="owner_account_recovery",
        nonce="b" * 64,
        issued_at=1000,
        expires_at=1600,
        operator_key_id="operator-key-01",
        approver_key_id="approver-key-01",
    )
    message = canonical_request(next_request)
    envelope = SignedRecoveryRequest(
        next_request, operator.sign(message), approver.sign(message)
    )
    before_anchor = anchor.read()
    with pytest.raises(RecoveryDenied, match="audit integrity"):
        service.apply(envelope, now=1100)
    assert anchor.read() == before_anchor
    assert store.read_global_owner_state().revision == 1


def test_audit_reordering_is_detected(tmp_path):
    service, store, anchor, operator, approver = _setup(tmp_path)
    first = _signed(operator, approver)
    state = service.apply(first, now=1100)
    second_request = RecoveryRequest(
        change_id="p62-change-second",
        action="rekey",
        expected_revision=state.revision,
        old_generation=state.generation,
        new_generation=hashlib.sha256(b"second-generation").hexdigest(),
        reason_code="owner_account_recovery",
        nonce="c" * 64,
        issued_at=1000,
        expires_at=1600,
        operator_key_id="operator-key-01",
        approver_key_id="approver-key-01",
    )
    message = canonical_request(second_request)
    service.apply(
        SignedRecoveryRequest(second_request, operator.sign(message), approver.sign(message)),
        now=1100,
    )
    assert store.verify_audit_chain() is True

    with sqlite3.connect(store._database_path) as db:
        db.execute("UPDATE durable_audit_events SET sequence=99 WHERE sequence=1")
        db.commit()
    assert store.verify_audit_chain() is False
    assert service.inspect().disposition == "CONSISTENT"
    with pytest.raises(RecoveryDenied, match="audit integrity"):
        service.apply(_signed(operator, approver, change_id="p62-stale-003", nonce="d" * 64), now=1100)
