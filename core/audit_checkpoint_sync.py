"""Crash-consistent reconciliation of a local audit head with an external checkpoint.

The local audit append is committed first. This coordinator then advances the
independent checkpoint by exactly one entry. A crash after local commit is
resumable; a checkpoint ahead of local storage, a multi-entry gap, or a
same-sequence hash mismatch is blocked. This module does not mutate owner
configuration and is not wired into request execution.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from core.audit_checkpoint import (
    AuditCheckpoint,
    AuditCheckpointDenied,
    IndependentAuditCheckpoint,
    advance_checkpoint,
    validate_checkpoint,
)


class LocalAuditHead(Protocol):
    def read_audit_checkpoint(self) -> AuditCheckpoint: ...


@dataclass(frozen=True)
class AuditReconciliation:
    disposition: str
    local: AuditCheckpoint
    external: AuditCheckpoint


def reconcile_audit_checkpoint(
    local_store: LocalAuditHead,
    provider: IndependentAuditCheckpoint,
) -> AuditReconciliation:
    """Reconcile only an exact match or one locally committed pending entry."""
    try:
        local = validate_checkpoint(local_store.read_audit_checkpoint())
        external = validate_checkpoint(provider.read())
    except AuditCheckpointDenied:
        raise
    except Exception:
        raise AuditCheckpointDenied("Audit reconciliation state is unavailable.") from None

    if local == external:
        return AuditReconciliation("CONSISTENT", local, external)

    if local.sequence == external.sequence + 1:
        try:
            confirmed = advance_checkpoint(provider, expected=external, target=local)
        except AuditCheckpointDenied:
            raise
        except Exception:
            raise AuditCheckpointDenied("Audit checkpoint reconciliation failed.") from None
        if confirmed != local:
            raise AuditCheckpointDenied("Audit checkpoint reconciliation mismatched.")
        return AuditReconciliation("LOCAL_AHEAD_RECONCILED", local, confirmed)

    if external.sequence > local.sequence:
        raise AuditCheckpointDenied("External audit checkpoint is ahead; local restore or deletion suspected.")
    if local.sequence > external.sequence + 1:
        raise AuditCheckpointDenied("Local audit log has multiple uncheckpointed entries.")
    raise AuditCheckpointDenied("Local and external audit checkpoint hashes diverge.")
