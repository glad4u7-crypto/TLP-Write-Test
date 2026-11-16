from __future__ import annotations
from dataclasses import replace
import hashlib
import sqlite3
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from core.offline_owner_recovery import (
    AnchorState, OfflineOwnerRecoveryService, RecoveryDenied, RecoveryPolicy,
    RecoveryPublicKey, RecoveryRequest, SignedRecoveryRequest, canonical_request,
)
from core.sqlite_security_store import SQLiteSecurityStore

class _InMemoryMonotonicAnchor:
    """In-memory test double; never suitable for deployment."""
    def __init__(self, state): self.state, self.fail_next = state, False
    def read(self): return self.state
    def compare_and_advance(self, *, expected, target):
        if self.fail_next:
            self.fail_next = False
            raise OSError("simulated anchor outage")
        if self.state != expected or target.revision != expected.revision + 1: return False
        self.state = target
        return True

def _keypair():
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw)
    return private, public

def _setup(tmp_path):
    op, op_pub = _keypair()
    ap, ap_pub = _keypair()
    policy = RecoveryPolicy(
        (RecoveryPublicKey("operator-key-01", op_pub),),
        (RecoveryPublicKey("approver-key-01", ap_pub),))
    store = SQLiteSecurityStore(tmp_path / "security.sqlite3")
    anchor = _InMemoryMonotonicAnchor(AnchorState(0, None, None))
    return OfflineOwnerRecoveryService(store, policy, anchor), store, anchor, op, ap

def _signed(op, ap, **overrides):
    values = dict(change_id="offline-change-001", action="rekey", expected_revision=0,
        old_generation=None, new_generation=hashlib.sha256(b"synthetic-owner-config").hexdigest(),
        reason_code="owner_account_recovery", nonce="a"*64, issued_at=1000, expires_at=1600,
        operator_key_id="operator-key-01", approver_key_id="approver-key-01")
    values.update(overrides)
    request = RecoveryRequest(**values)
    message = canonical_request(request)
    return SignedRecoveryRequest(request, op.sign(message), ap.sign(message))

def test_dual_control_rekey_commits_state_and_audit(tmp_path):
    service, store, anchor, op, ap = _setup(tmp_path)
    result = service.apply(_signed(op, ap), now=1100)
    assert result.revision == 1
    assert anchor.read() == AnchorState(1, result.generation, "offline-change-001")
    assert service.inspect().disposition == "CONSISTENT"
    assert store.verify_audit_chain()

def test_invalid_independent_approval_signature_fails_closed(tmp_path):
    service, store, anchor, op, ap = _setup(tmp_path)
    envelope = replace(_signed(op, ap), approver_signature=b"x"*64)
    with pytest.raises(RecoveryDenied): service.apply(envelope, now=1100)
    assert store.read_global_owner_state().revision == 0
    assert anchor.read() == AnchorState(0, None, None)

def test_same_key_cannot_be_operator_and_approver(tmp_path):
    _, public = _keypair()
    policy = RecoveryPolicy((RecoveryPublicKey("operator-key-01", public),),
                            (RecoveryPublicKey("approver-key-01", public),))
    store = SQLiteSecurityStore(tmp_path / "same-key.sqlite3")
    with pytest.raises(RecoveryDenied):
        OfflineOwnerRecoveryService(store, policy, _InMemoryMonotonicAnchor(AnchorState(0,None,None)))

@pytest.mark.parametrize("field,value", [
    ("expires_at",999), ("expires_at",5000), ("issued_at",2000), ("nonce","short"),
    ("change_id","bad id"), ("action","first_login_claim"),
])
def test_invalid_request_rejected_without_mutation(tmp_path, field, value):
    service, store, anchor, op, ap = _setup(tmp_path)
    with pytest.raises(RecoveryDenied):
        service.apply(_signed(op, ap, **{field:value}), now=1100)
    assert store.read_global_owner_state().revision == 0
    assert anchor.read() == AnchorState(0,None,None)

def test_stale_revision_or_generation_is_rejected(tmp_path):
    service, store, anchor, op, ap = _setup(tmp_path)
    other = hashlib.sha256(b"other-owner").hexdigest()
    store.compare_and_set_global_owner_generation(expected_revision=0, generation=other,
                                                   change_id="other-change-001")
    anchor.state = AnchorState(1, other, "other-change-001")
    with pytest.raises(RecoveryDenied): service.apply(_signed(op, ap), now=1100)

def test_anchor_outage_fails_closed_before_local_mutation(tmp_path):
    service, store, anchor, op, ap = _setup(tmp_path)
    anchor.fail_next = True
    with pytest.raises(RecoveryDenied): service.apply(_signed(op, ap), now=1100)
    assert store.read_global_owner_state().revision == 0
    assert anchor.read() == AnchorState(0,None,None)

def test_crash_after_anchor_advance_resumes_same_signed_request(tmp_path, monkeypatch):
    service, store, anchor, op, ap = _setup(tmp_path)
    original = store.compare_and_set_global_owner_generation
    monkeypatch.setattr(store, "compare_and_set_global_owner_generation",
                        lambda **kwargs: (_ for _ in ()).throw(OSError("simulated crash")))
    envelope = _signed(op, ap)
    with pytest.raises(RecoveryDenied): service.apply(envelope, now=1100)
    assert service.inspect().disposition == "ANCHOR_AHEAD_RESUMABLE"
    monkeypatch.setattr(store, "compare_and_set_global_owner_generation", original)
    assert service.apply(envelope, now=1100).revision == 1
    assert service.inspect().disposition == "CONSISTENT"

def test_expired_envelope_can_be_replaced_by_new_dual_signed_resume_envelope(tmp_path, monkeypatch):
    service, store, anchor, op, ap = _setup(tmp_path)
    monkeypatch.setattr(store, "compare_and_set_global_owner_generation",
                        lambda **kwargs: (_ for _ in ()).throw(OSError("simulated crash")))
    original = _signed(op, ap)
    with pytest.raises(RecoveryDenied): service.apply(original, now=1100)
    monkeypatch.undo()
    renewed = _signed(op, ap, nonce="c"*64, issued_at=2000, expires_at=2600)
    result = service.apply(renewed, now=2100)
    assert result.revision == 1
    assert service.inspect().disposition == "CONSISTENT"

def test_tampered_envelope_cannot_resume_anchor_ahead(tmp_path, monkeypatch):
    service, store, anchor, op, ap = _setup(tmp_path)
    monkeypatch.setattr(store, "compare_and_set_global_owner_generation",
                        lambda **kwargs: (_ for _ in ()).throw(OSError("simulated crash")))
    with pytest.raises(RecoveryDenied): service.apply(_signed(op, ap), now=1100)
    altered = _signed(op, ap, new_generation=hashlib.sha256(b"tampered").hexdigest())
    with pytest.raises(RecoveryDenied): service.apply(altered, now=1100)
    assert store.read_global_owner_state().revision == 0

def test_revocation_advances_to_unprovisioned_generation(tmp_path):
    service, store, anchor, op, ap = _setup(tmp_path)
    first = _signed(op, ap, new_generation=hashlib.sha256(b"initial").hexdigest())
    state = service.apply(first, now=1100)
    second = _signed(op, ap, change_id="offline-revoke-002", action="revoke",
        expected_revision=state.revision, old_generation=state.generation,
        new_generation=None, nonce="b"*64)
    revoked = service.apply(second, now=1100)
    assert revoked.revision == 2 and revoked.generation is None
    assert anchor.read() == AnchorState(2,None,"offline-revoke-002")

def test_audit_records_key_fingerprints_not_owner_credentials(tmp_path):
    service, store, anchor, op, ap = _setup(tmp_path)
    service.apply(_signed(op, ap), now=1100)
    assert store.verify_audit_chain()
    with sqlite3.connect(store._database_path) as db:
        row = db.execute("SELECT reason_code, principal_fingerprint, request_id FROM durable_audit_events").fetchone()
    assert row[0] == "offline_owner_rekey_approved"
    assert len(row[1]) == 64
    assert row[2] == "offline-change-001"
