"""Trusted control-plane orchestration for signed inspector evidence.

This module composes existing offline signature verification, the externally
provisioned public-key registry, and durable one-time challenge consumption.
It does not collect host evidence, launch workers, or mutate host networking.
"""
from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Sequence

from core.browser_inspector import (
    InspectorEvidenceError,
    VerifiedInspectorEvidence,
    verify_signed_inspector_evidence,
)
from core.browser_runtime import WorkerLaunchSpec
from core.inspector_key_registry import InspectorPublicKeyRegistry
from core.sqlite_security_store import SQLiteSecurityStore
from core.storage import TenantKey


class InspectorControlPlaneError(ValueError):
    """Raised when trusted inspector evidence cannot be accepted."""


@dataclass(frozen=True)
class InspectorChallenge:
    """Challenge issued by the trusted control plane before host inspection."""

    value: str
    expires_at: int
    runtime_id: str
    worker_id: str


@dataclass(frozen=True)
class AcceptedInspectorEvidence:
    """Evidence accepted only after signature, identity and replay checks."""

    evidence: VerifiedInspectorEvidence
    accepted_at: int


class InspectorEvidenceControlPlane:
    """Compose key trust, signed evidence verification and durable replay guard.

    The caller is responsible for authenticating the tenant and obtaining the
    launch spec, expected runtime/worker IDs and proxy IP allowlist from trusted
    control-plane state. Registry records must come from authenticated,
    out-of-band configuration.
    """

    def __init__(
        self,
        *,
        security_store: SQLiteSecurityStore,
        key_registry: InspectorPublicKeyRegistry,
    ) -> None:
        if not isinstance(security_store, SQLiteSecurityStore):
            raise TypeError("A SQLiteSecurityStore instance is required.")
        if not isinstance(key_registry, InspectorPublicKeyRegistry):
            raise TypeError("An InspectorPublicKeyRegistry instance is required.")
        self._store = security_store
        self._registry = key_registry

    def issue_challenge(
        self,
        tenant: TenantKey,
        *,
        runtime_id: str,
        worker_id: str,
        ttl_seconds: int = 60,
        now: int | None = None,
    ) -> InspectorChallenge:
        """Persist and issue a tenant/runtime/worker-bound single-use challenge."""
        try:
            value, expires_at = self._store.issue_inspector_challenge(
                tenant,
                runtime_id=runtime_id,
                worker_id=worker_id,
                ttl_seconds=ttl_seconds,
                now=now,
            )
        except (TypeError, ValueError) as exc:
            raise InspectorControlPlaneError("Inspector challenge issuance was rejected.") from exc
        return InspectorChallenge(value, expires_at, runtime_id, worker_id)

    def verify_and_consume(
        self,
        tenant: TenantKey,
        spec: WorkerLaunchSpec,
        envelope: object,
        *,
        expected_challenge: str,
        expected_runtime_id: str,
        expected_worker_id: str,
        expected_proxy_addresses: Sequence[str],
        now: int | None = None,
        max_age_seconds: int = 60,
    ) -> AcceptedInspectorEvidence:
        """Verify every claim, then atomically consume the issued challenge once.

        Ordering is deliberate: resolve an active trusted key, verify the
        Ed25519 signature and evidence semantics, compare the attested runtime
        and worker to trusted expected IDs, and only then consume the durable
        challenge. Any failure before consumption leaves the challenge
        unconsumed; any failed consume rejects the evidence.
        """
        if not isinstance(tenant, TenantKey):
            raise TypeError("A validated TenantKey is required.")
        if type(expected_runtime_id) is not str or type(expected_worker_id) is not str:
            raise InspectorControlPlaneError("Trusted runtime and worker identifiers are required.")
        try:
            if not isinstance(envelope, dict):
                raise InspectorEvidenceError("Inspector envelope must be an object.")
            key_id = envelope.get("key_id")
            trusted_keys = self._registry.active_public_keys(now=now)
            public_key = self._registry.require_active_key(key_id, now=now)
            if trusted_keys.get(key_id) != public_key:
                raise InspectorEvidenceError("Inspector signing key is not active.")
            evidence = verify_signed_inspector_evidence(
                spec,
                envelope,
                trusted_public_keys=trusted_keys,
                expected_challenge=expected_challenge,
                expected_proxy_addresses=expected_proxy_addresses,
                now=now,
                max_age_seconds=max_age_seconds,
            )
        except (InspectorEvidenceError, ValueError, TypeError) as exc:
            raise InspectorControlPlaneError("Signed inspector evidence verification failed.") from exc

        if (evidence.runtime.runtime_id != expected_runtime_id
                or evidence.runtime.worker_id != expected_worker_id
                or evidence.firewall.runtime_id != expected_runtime_id
                or evidence.firewall.worker_id != expected_worker_id):
            raise InspectorControlPlaneError("Inspector evidence runtime/worker identity mismatch.")

        try:
            consumed = self._store.consume_inspector_challenge(
                tenant,
                expected_challenge,
                runtime_id=expected_runtime_id,
                worker_id=expected_worker_id,
                now=now,
            )
        except (TypeError, ValueError) as exc:
            raise InspectorControlPlaneError("Inspector challenge consumption failed.") from exc
        if consumed is not True:
            raise InspectorControlPlaneError("Inspector challenge is unknown, expired, mismatched or replayed.")

        accepted_at = now
        if accepted_at is None:
            import time
            accepted_at = int(time.time())
        return AcceptedInspectorEvidence(evidence=evidence, accepted_at=accepted_at)
