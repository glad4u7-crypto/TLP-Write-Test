"""Provider-neutral contract for an independently protected audit high-water mark.

This module defines a narrow contract only. It contains no provider adapter,
credentials, network client, or automatic integration with the SQLite audit log.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Protocol

_DIGEST = re.compile(r"^[0-9a-f]{64}$")
GENESIS_HASH = "0" * 64


class AuditCheckpointDenied(PermissionError):
    """A checkpoint transition was invalid, conflicting, or unavailable."""


@dataclass(frozen=True)
class AuditCheckpoint:
    sequence: int
    entry_hash: str


class IndependentAuditCheckpoint(Protocol):
    """Independent durable CAS checkpoint; not stored in the APAA DB domain."""

    def read(self) -> AuditCheckpoint: ...

    def compare_and_advance(
        self, *, expected: AuditCheckpoint, target: AuditCheckpoint
    ) -> bool: ...


def validate_checkpoint(value: object) -> AuditCheckpoint:
    if (
        not isinstance(value, AuditCheckpoint)
        or type(value.sequence) is not int
        or value.sequence < 0
        or type(value.entry_hash) is not str
        or not _DIGEST.fullmatch(value.entry_hash)
        or (value.sequence == 0 and value.entry_hash != GENESIS_HASH)
        or (value.sequence > 0 and value.entry_hash == GENESIS_HASH)
    ):
        raise AuditCheckpointDenied("Independent audit checkpoint is malformed.")
    return value


def advance_checkpoint(
    provider: IndependentAuditCheckpoint,
    *,
    expected: AuditCheckpoint,
    target: AuditCheckpoint,
) -> AuditCheckpoint:
    """Advance exactly one entry; reconcile a lost acknowledgement by reading.

    A caller must supply the hash of the exact locally committed audit entry.
    This helper does not decide whether a local database is trustworthy and is
    deliberately not wired into the current SQLite audit transaction.
    """
    expected = validate_checkpoint(expected)
    target = validate_checkpoint(target)
    if target.sequence != expected.sequence + 1:
        raise AuditCheckpointDenied("Audit checkpoint must advance by one sequence.")
    if target.entry_hash == expected.entry_hash:
        raise AuditCheckpointDenied("Audit checkpoint hash must change.")

    try:
        current = validate_checkpoint(provider.read())
    except Exception:
        raise AuditCheckpointDenied("Independent audit checkpoint is unavailable.") from None
    if current == target:
        return current
    if current != expected:
        raise AuditCheckpointDenied("Independent audit checkpoint has diverged.")

    try:
        advanced = provider.compare_and_advance(expected=expected, target=target)
    except Exception:
        # A timeout may mean the provider committed but the acknowledgement was
        # lost. Only an exact read-back of the requested target is success.
        try:
            observed = validate_checkpoint(provider.read())
        except Exception:
            raise AuditCheckpointDenied("Audit checkpoint outcome is unknown.") from None
        if observed == target:
            return observed
        raise AuditCheckpointDenied("Independent audit checkpoint update failed.") from None

    if advanced is not True:
        try:
            observed = validate_checkpoint(provider.read())
        except Exception:
            raise AuditCheckpointDenied("Audit checkpoint outcome is unknown.") from None
        if observed == target:
            return observed
        raise AuditCheckpointDenied("Independent audit checkpoint rejected the update.")
    try:
        observed = validate_checkpoint(provider.read())
    except Exception:
        raise AuditCheckpointDenied("Audit checkpoint confirmation failed.") from None
    if observed != target:
        raise AuditCheckpointDenied("Audit checkpoint confirmation mismatched.")
    return observed
