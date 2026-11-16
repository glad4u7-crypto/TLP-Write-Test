from __future__ import annotations

from dataclasses import dataclass
import sqlite3
import threading

import pytest

from core.audit_checkpoint import (
    AuditCheckpoint,
    AuditCheckpointDenied,
    GENESIS_HASH,
)
from core.audit_checkpoint_sync import reconcile_audit_checkpoint
from core.sqlite_security_store import DurableAuditEvent, SQLiteSecurityStore


@dataclass
class _ProviderState:
    value: AuditCheckpoint
    lock: threading.Lock
    fail_before: bool = False
    lose_ack: bool = False


class _Provider:
    def __init__(self, state):
        self.state = state

    def read(self):
        with self.state.lock:
            if self.state.fail_before:
                raise OSError("provider offline")
            return self.state.value

    def compare_and_advance(self, *, expected, target):
        with self.state.lock:
            if self.state.fail_before:
                raise OSError("provider offline")
            if self.state.value != expected:
                return False
            self.state.value = target
            if self.state.lose_ack:
                self.state.lose_ack = False
                raise TimeoutError("ack lost after durable commit")
            return True


def _setup(tmp_path):
    store = SQLiteSecurityStore(tmp_path / "audit.sqlite3")
    state = _ProviderState(AuditCheckpoint(0, GENESIS_HASH), threading.Lock())
    return store, _Provider(state), state


def _append(store, n):
    return store.append_audit_event(DurableAuditEvent(
        action="synthetic_recovery_test",
        result="success",
        reason_code="synthetic_test_event",
        principal_fingerprint=("a" if n % 2 else "b") * 64,
        request_id=f"synthetic-request-{n:04d}",
    ))


def test_genesis_checkpoint_matches_empty_database(tmp_path):
    store, provider, _ = _setup(tmp_path)
    result = reconcile_audit_checkpoint(store, provider)
    assert result.disposition == "CONSISTENT"
    assert result.local == AuditCheckpoint(0, GENESIS_HASH)


def test_local_commit_before_checkpoint_is_resumed_exactly_once(tmp_path):
    store, provider, _ = _setup(tmp_path)
    _append(store, 1)  # crash boundary: append committed, checkpoint not advanced
    first = reconcile_audit_checkpoint(store, provider)
    second = reconcile_audit_checkpoint(store, provider)
    assert first.disposition == "LOCAL_AHEAD_RECONCILED"
    assert second.disposition == "CONSISTENT"
    assert first.local == second.external
    assert provider.read().sequence == 1


def test_checkpoint_timeout_after_commit_is_reconciled_by_exact_readback(tmp_path):
    store, provider, state = _setup(tmp_path)
    _append(store, 1)
    state.lose_ack = True
    result = reconcile_audit_checkpoint(store, provider)
    assert result.disposition == "LOCAL_AHEAD_RECONCILED"
    assert provider.read() == result.local
    assert reconcile_audit_checkpoint(store, provider).disposition == "CONSISTENT"


def test_external_checkpoint_ahead_after_database_restore_fails_closed(tmp_path):
    store, provider, _ = _setup(tmp_path)
    backup = tmp_path / "empty-backup.sqlite3"
    with sqlite3.connect(store._database_path) as src, sqlite3.connect(backup) as dst:
        src.backup(dst)
    _append(store, 1)
    reconcile_audit_checkpoint(store, provider)
    with sqlite3.connect(backup) as src, sqlite3.connect(store._database_path) as dst:
        src.backup(dst)
    with pytest.raises(AuditCheckpointDenied, match="ahead"):
        reconcile_audit_checkpoint(store, provider)


def test_multiple_local_uncheckpointed_entries_fail_closed(tmp_path):
    store, provider, _ = _setup(tmp_path)
    _append(store, 1)
    _append(store, 2)
    with pytest.raises(AuditCheckpointDenied, match="multiple"):
        reconcile_audit_checkpoint(store, provider)
    assert provider.read().sequence == 0


def test_same_sequence_different_hash_fails_closed(tmp_path):
    store, provider, _ = _setup(tmp_path)
    _append(store, 1)
    provider.state.value = AuditCheckpoint(1, "f" * 64)
    with pytest.raises(AuditCheckpointDenied, match="diverge"):
        reconcile_audit_checkpoint(store, provider)


def test_local_audit_tampering_blocks_checkpoint_advance(tmp_path):
    store, provider, _ = _setup(tmp_path)
    _append(store, 1)
    with sqlite3.connect(store._database_path) as db:
        db.execute("UPDATE durable_audit_events SET reason_code = 'tampered' WHERE sequence = 1")
        db.commit()
    with pytest.raises((AuditCheckpointDenied, ValueError)):
        reconcile_audit_checkpoint(store, provider)
    assert provider.read().sequence == 0


def test_provider_outage_leaves_local_append_pending_and_fails_closed(tmp_path):
    store, provider, state = _setup(tmp_path)
    _append(store, 1)
    state.fail_before = True
    with pytest.raises(AuditCheckpointDenied):
        reconcile_audit_checkpoint(store, provider)
    state.fail_before = False
    result = reconcile_audit_checkpoint(store, provider)
    assert result.disposition == "LOCAL_AHEAD_RECONCILED"


def test_reconciliation_does_not_silently_checkpoint_two_events(tmp_path):
    store, provider, _ = _setup(tmp_path)
    for n in range(1, 4):
        _append(store, n)
    with pytest.raises(AuditCheckpointDenied):
        reconcile_audit_checkpoint(store, provider)
    assert provider.read().sequence == 0
