from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import threading

import pytest

from core.offline_owner_recovery import AnchorState, RecoveryDenied


class _SyntheticProviderState:
    """Shared test fixture modelling a provider's atomic conditional-write API.

    This is deliberately in-memory. It is not durable storage or a production
    monotonic anchor; sharing the object models multiple adapter instances.
    """
    def __init__(self, initial: AnchorState):
        self.value = initial
        self.lock = threading.Lock()
        self.available = True
        self.lose_next_ack = False


class _ContractTestAdapter:
    """Test-only adapter implementing the coordinator's narrow anchor contract."""
    def __init__(self, provider: _SyntheticProviderState):
        self._provider = provider

    def read(self) -> AnchorState:
        with self._provider.lock:
            if not self._provider.available:
                raise OSError("synthetic provider unavailable")
            return self._provider.value

    def compare_and_advance(self, *, expected: AnchorState, target: AnchorState) -> bool:
        with self._provider.lock:
            if not self._provider.available:
                raise OSError("synthetic provider unavailable")
            if (not isinstance(expected, AnchorState) or not isinstance(target, AnchorState)
                    or type(expected.revision) is not int or type(target.revision) is not int
                    or expected.revision < 0 or target.revision != expected.revision + 1
                    or target.change_id is None):
                return False
            if self._provider.value != expected:
                return False
            self._provider.value = target
            if self._provider.lose_next_ack:
                self._provider.lose_next_ack = False
                raise TimeoutError("synthetic acknowledgement lost after commit")
            return True


def test_anchor_contract_exactly_one_concurrent_writer_wins():
    initial = AnchorState(0, None, None)
    provider = _SyntheticProviderState(initial)
    adapters = [_ContractTestAdapter(provider) for _ in range(12)]
    barrier = threading.Barrier(len(adapters))

    def attempt(index: int) -> bool:
        target = AnchorState(1, f"{index:064x}", f"contract-change-{index:03d}")
        barrier.wait(timeout=5)
        return adapters[index].compare_and_advance(expected=initial, target=target)

    with ThreadPoolExecutor(max_workers=len(adapters)) as pool:
        results = list(pool.map(attempt, range(len(adapters))))

    assert sum(results) == 1
    assert adapters[0].read().revision == 1


@pytest.mark.parametrize("target", [
    AnchorState(0, None, None),
    AnchorState(2, "a" * 64, "skip-revision-001"),
    AnchorState(-1, None, None),
])
def test_anchor_contract_rejects_non_monotonic_or_skipped_revision(target):
    initial = AnchorState(0, None, None)
    adapter = _ContractTestAdapter(_SyntheticProviderState(initial))
    assert adapter.compare_and_advance(expected=initial, target=target) is False
    assert adapter.read() == initial


def test_anchor_contract_rejects_stale_expected_state():
    current = AnchorState(2, "b" * 64, "current-change-002")
    stale = AnchorState(1, "a" * 64, "old-change-001")
    adapter = _ContractTestAdapter(_SyntheticProviderState(current))
    target = AnchorState(2, "c" * 64, "stale-writer-003")
    assert adapter.compare_and_advance(expected=stale, target=target) is False
    assert adapter.read() == current


def test_anchor_contract_restart_reads_same_shared_committed_state():
    provider = _SyntheticProviderState(AnchorState(0, None, None))
    first_process = _ContractTestAdapter(provider)
    target = AnchorState(1, "d" * 64, "restart-change-001")
    assert first_process.compare_and_advance(expected=first_process.read(), target=target)
    restarted_process = _ContractTestAdapter(provider)
    assert restarted_process.read() == target


def test_anchor_contract_lost_ack_is_reconciled_by_read_not_second_advance():
    initial = AnchorState(0, None, None)
    provider = _SyntheticProviderState(initial)
    adapter = _ContractTestAdapter(provider)
    target = AnchorState(1, "e" * 64, "lost-ack-change-001")
    provider.lose_next_ack = True
    with pytest.raises(TimeoutError):
        adapter.compare_and_advance(expected=initial, target=target)
    assert adapter.read() == target
    # Retrying the same CAS cannot increment or rewrite the committed target.
    assert adapter.compare_and_advance(expected=initial, target=target) is False
    assert adapter.read() == target


def test_anchor_contract_unavailable_provider_fails_closed():
    provider = _SyntheticProviderState(AnchorState(0, None, None))
    adapter = _ContractTestAdapter(provider)
    provider.available = False
    with pytest.raises(OSError):
        adapter.read()
    with pytest.raises(OSError):
        adapter.compare_and_advance(
            expected=AnchorState(0, None, None),
            target=AnchorState(1, "f" * 64, "outage-change-001"),
        )
