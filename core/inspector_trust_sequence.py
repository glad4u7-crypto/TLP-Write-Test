"""Monotonic acceptance gate for signed inspector trust bundles.

The backend is an independently administered monotonic anchor. Implementations
MUST provide durable compare-and-swap semantics and MUST NOT roll back during
backup/restore. This module intentionally ships no local-file or SQLite
fallback because those can be rolled back with the host.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from core.inspector_key_registry import InspectorPublicKeyRegistry
from core.inspector_trust_bundle import (
    InspectorTrustBundleError,
    load_signed_inspector_trust_bundle,
)


class InspectorTrustSequenceError(RuntimeError):
    """Raised when trust-bundle sequence acceptance cannot be made monotonic."""


@runtime_checkable
class MonotonicSequenceBackend(Protocol):
    """Independent durable high-water mark with atomic compare-and-advance.

    read_sequence returns 0 when issuer has never been initialized.
    advance_sequence must atomically change expected_current to new_sequence,
    returning False if the current value differs. It must persist before True.
    Restoring a backup must never lower the returned sequence.
    """

    def read_sequence(self, issuer_key_id: str) -> int:
        ...

    def advance_sequence(
        self, issuer_key_id: str, *, expected_current: int, new_sequence: int
    ) -> bool:
        ...


def accept_signed_inspector_trust_bundle(
    raw_bundle: str | bytes,
    *,
    root_public_key: bytes,
    expected_issuer_key_id: str,
    sequence_backend: MonotonicSequenceBackend,
    now: int | None = None,
) -> tuple[InspectorPublicKeyRegistry, int]:
    """Verify and atomically advance an issuer's monotonic sequence.

    A backend read/CAS race fails closed and requires the caller to reload the
    latest bundle. The registry is returned only after the high-water mark has
    been durably advanced. A local file or ordinary database is not accepted
    unless its adapter independently guarantees anti-rollback restore behavior.
    """
    if not isinstance(sequence_backend, MonotonicSequenceBackend):
        raise TypeError("An explicit monotonic sequence backend is required.")
    try:
        current = sequence_backend.read_sequence(expected_issuer_key_id)
    except Exception as exc:
        raise InspectorTrustSequenceError("Could not read trusted sequence anchor.") from exc
    if type(current) is not int or current < 0:
        raise InspectorTrustSequenceError("Trusted sequence anchor returned an invalid value.")

    try:
        registry, sequence = load_signed_inspector_trust_bundle(
            raw_bundle,
            root_public_key=root_public_key,
            expected_issuer_key_id=expected_issuer_key_id,
            minimum_sequence=current + 1,
            now=now,
        )
    except (InspectorTrustBundleError, TypeError, ValueError) as exc:
        raise InspectorTrustSequenceError("Signed trust bundle was rejected.") from exc

    try:
        advanced = sequence_backend.advance_sequence(
            expected_issuer_key_id,
            expected_current=current,
            new_sequence=sequence,
        )
    except Exception as exc:
        raise InspectorTrustSequenceError("Trusted sequence anchor update failed.") from exc
    if advanced is not True:
        raise InspectorTrustSequenceError(
            "Trusted sequence anchor changed concurrently; reload and retry."
        )
    return registry, sequence
