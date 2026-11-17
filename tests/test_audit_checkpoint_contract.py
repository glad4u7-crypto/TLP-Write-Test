from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import threading

import pytest

from core.audit_checkpoint import (
    AuditCheckpoint,
    AuditCheckpointDenied,
    GENESIS_HASH,
    advance_checkpoint,
    validate_checkpoint,
)


@dataclass
class _ProviderState:
    value: AuditCheckpoint
    lock: threading.Lock
    available: bool = True
    lose_next_ack: bool = False


class _SyntheticCheckpointProvider:
    """Shared in-memory test double; not durable or production qualified."""

    def __init__(self, state: _ProviderState):
        self._state = state

    def read(self):
        with self._state.lock:
            if not self._state.available:
                raise OSError("synthetic checkpoint outage")
            return self._state.value

    def compare_and_advance(self, *, expected, target):
        with self._state.lock:
            if not self._state.available:
                raise OSError("synthetic checkpoint outage")
            if self._state.value != expected or target.sequence != expected.sequence + 1:
                return False
            self._state.value = target
            if self._state.lose_next_ack:
                self._state.lose_next_ack = False
                raise TimeoutError("synthetic acknowledgement lost after commit")
            return True


def _provider():
    genesis = AuditCheckpoint(0, GENESIS_HASH)
    state = _ProviderState(genesis, threading.Lock())
    return _SyntheticCheckpointProvider(state), state, genesis


def _target(sequence, digit):
    return AuditCheckpoint(sequence, digit * 64)


def test_checkpoint_advances_exactly_one_sequence_and_confirms_readback():
    provider, state, genesis = _provider()
    target = _target(1, "a")
    assert advance_checkpoint(provider, expected=genesis, target=target) == target
    assert provider.read() == target


def test_checkpoint_contract_allows_only_one_concurrent_writer():
    provider, state, genesis = _provider()
    candidates = [_target(1, format(i + 1, "x")) for i in range(10)]

    def attempt(target):
        try:
            return advance_checkpoint(provider, expected=genesis, target=target)
        except AuditCheckpointDenied:
            return None

    with ThreadPoolExecutor(max_workers=len(candidates)) as pool:
        results = list(pool.map(attempt, candidates))
    assert sum(result is not None for result in results) == 1
    assert provider.read().sequence == 1


def test_checkpoint_lost_ack_is_reconciled_without_second_advance():
    provider, state, genesis = _provider()
    target = _target(1, "b")
    state.lose_next_ack = True
    assert advance_checkpoint(provider, expected=genesis, target=target) == target
    assert provider.read() == target
    assert advance_checkpoint(provider, expected=genesis, target=target) == target
    assert provider.read().sequence == 1


@pytest.mark.parametrize("target", [
    AuditCheckpoint(0, GENESIS_HASH),
    AuditCheckpoint(2, "c" * 64),
    AuditCheckpoint(-1, GENESIS_HASH),
    AuditCheckpoint(1, GENESIS_HASH),
    AuditCheckpoint(1, "G" * 64),
])
def test_invalid_or_non_monotonic_target_is_rejected(target):
    provider, _, genesis = _provider()
    with pytest.raises(AuditCheckpointDenied):
        advance_checkpoint(provider, expected=genesis, target=target)
    assert provider.read() == genesis


def test_stale_writer_cannot_overwrite_newer_checkpoint():
    provider, _, genesis = _provider()
    first = _target(1, "d")
    advance_checkpoint(provider, expected=genesis, target=first)
    with pytest.raises(AuditCheckpointDenied):
        advance_checkpoint(provider, expected=genesis, target=_target(1, "e"))
    assert provider.read() == first


def test_provider_outage_fails_closed():
    provider, state, genesis = _provider()
    state.available = False
    with pytest.raises(AuditCheckpointDenied):
        advance_checkpoint(provider, expected=genesis, target=_target(1, "f"))


def test_malformed_provider_read_fails_closed():
    class MalformedProvider:
        def read(self):
            return AuditCheckpoint(True, GENESIS_HASH)

        def compare_and_advance(self, *, expected, target):
            raise AssertionError("must not write after malformed read")

    with pytest.raises(AuditCheckpointDenied):
        advance_checkpoint(MalformedProvider(), expected=AuditCheckpoint(0, GENESIS_HASH),
                           target=_target(1, "1"))


def test_restarted_adapter_observes_shared_checkpoint_state():
    provider, state, genesis = _provider()
    target = _target(1, "2")
    advance_checkpoint(provider, expected=genesis, target=target)
    restarted = _SyntheticCheckpointProvider(state)
    assert restarted.read() == target
