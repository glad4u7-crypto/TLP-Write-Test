"""Out-of-band Ed25519 public-key trust registry for inspector evidence.

This module accepts already-provisioned public-key records from trusted
configuration. It never generates, imports, stores or handles private keys.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
import time
from collections.abc import Iterable


_KEY_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{2,127}$")


class InspectorKeyRegistryError(ValueError):
    """Raised when trusted inspector key configuration is invalid."""


@dataclass(frozen=True)
class InspectorPublicKeyRecord:
    """One externally provisioned Ed25519 public-key trust record."""

    key_id: str
    public_key: bytes
    not_before: int
    not_after: int
    revoked: bool = False


class InspectorPublicKeyRegistry:
    """Validate immutable trust records and expose only currently active keys.

    The registry is deliberately configuration-in/configuration-out. The
    caller must obtain records from an independently authenticated, out-of-band
    trust source. A registry object is not itself a trust anchor.
    """

    def __init__(self, records: Iterable[InspectorPublicKeyRecord]) -> None:
        if isinstance(records, (str, bytes, dict)):
            raise TypeError("Key records must be an iterable of typed records.")
        try:
            snapshot = tuple(records)
        except TypeError as exc:
            raise TypeError("Key records must be iterable.") from exc
        seen_ids: set[str] = set()
        seen_keys: set[bytes] = set()
        for record in snapshot:
            if not isinstance(record, InspectorPublicKeyRecord):
                raise TypeError("Only InspectorPublicKeyRecord entries are accepted.")
            if type(record.key_id) is not str or not _KEY_ID.fullmatch(record.key_id):
                raise InspectorKeyRegistryError("Invalid inspector key identifier.")
            if record.key_id in seen_ids:
                raise InspectorKeyRegistryError("Duplicate inspector key identifier.")
            seen_ids.add(record.key_id)
            if type(record.public_key) is not bytes or len(record.public_key) != 32:
                raise InspectorKeyRegistryError("Ed25519 public keys must be exactly 32 bytes.")
            if record.public_key in seen_keys:
                raise InspectorKeyRegistryError("A public key must not be registered under multiple IDs.")
            seen_keys.add(record.public_key)
            if (type(record.not_before) is not int or type(record.not_after) is not int
                    or record.not_before < 0 or record.not_after <= record.not_before):
                raise InspectorKeyRegistryError("Invalid public-key validity interval.")
            if type(record.revoked) is not bool:
                raise InspectorKeyRegistryError("Revocation state must be an explicit boolean.")
        self._records = snapshot

    def active_public_keys(self, *, now: int | None = None) -> dict[str, bytes]:
        """Return a fresh mapping containing only valid, non-revoked keys."""
        current = int(time.time()) if now is None else now
        if type(current) is not int or current < 0:
            raise InspectorKeyRegistryError("Registry evaluation time is invalid.")
        return {
            record.key_id: record.public_key
            for record in self._records
            if not record.revoked and record.not_before <= current < record.not_after
        }

    def require_active_key(self, key_id: str, *, now: int | None = None) -> bytes:
        """Resolve one key or fail closed for unknown, expired or revoked IDs."""
        if type(key_id) is not str or not _KEY_ID.fullmatch(key_id):
            raise InspectorKeyRegistryError("Invalid inspector key identifier.")
        key = self.active_public_keys(now=now).get(key_id)
        if key is None:
            raise InspectorKeyRegistryError("Inspector signing key is not currently trusted.")
        return key
