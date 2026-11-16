"""Verify an out-of-band signed inspector trust bundle.

The bundle is signed by an independently provisioned Ed25519 root public key.
This module handles public keys only: it never creates, imports or stores
private signing material. Callers must persist the highest accepted sequence
outside the worker to prevent rollback across process restarts.
"""
from __future__ import annotations

import base64
import binascii
import json
import re
import time
from collections.abc import Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from core.inspector_key_registry import (
    InspectorPublicKeyRecord,
    InspectorPublicKeyRegistry,
    InspectorKeyRegistryError,
)


class InspectorTrustBundleError(ValueError):
    """Raised when a signed out-of-band trust bundle is invalid."""


_KEY_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{2,127}$")
_BUNDLE_FIELDS = frozenset({"schema_version", "issuer_key_id", "payload", "signature"})
_PAYLOAD_FIELDS = frozenset({"schema_version", "sequence", "issued_at", "expires_at", "keys"})
_RECORD_FIELDS = frozenset({"key_id", "public_key", "not_before", "not_after", "revoked"})


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise InspectorTrustBundleError("Duplicate JSON object keys are not permitted.")
        result[key] = value
    return result


def _canonical(value: object) -> bytes:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"),
            ensure_ascii=True, allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise InspectorTrustBundleError("Trust bundle is not canonical JSON data.") from exc


def load_signed_inspector_trust_bundle(
    raw_bundle: str | bytes,
    *,
    root_public_key: bytes,
    expected_issuer_key_id: str,
    minimum_sequence: int,
    now: int | None = None,
) -> tuple[InspectorPublicKeyRegistry, int]:
    """Verify a signed bundle and return its immutable registry + sequence.

    `root_public_key` and `expected_issuer_key_id` must be pinned by trusted
    control-plane configuration, not supplied by the bundle or worker.
    `minimum_sequence` must be loaded from durable, rollback-protected
    control-plane state and updated atomically after successful acceptance.
    """
    if type(root_public_key) is not bytes or len(root_public_key) != 32:
        raise InspectorTrustBundleError("Pinned Ed25519 root public key must be exactly 32 bytes.")
    if type(expected_issuer_key_id) is not str or not _KEY_ID.fullmatch(expected_issuer_key_id):
        raise InspectorTrustBundleError("Pinned trust-bundle issuer ID is invalid.")
    if type(minimum_sequence) is not int or minimum_sequence < 1:
        raise InspectorTrustBundleError("Minimum trust-bundle sequence must be a positive integer.")
    current = int(time.time()) if now is None else now
    if type(current) is not int or current < 0:
        raise InspectorTrustBundleError("Trust-bundle evaluation time is invalid.")
    if type(raw_bundle) not in (str, bytes):
        raise TypeError("Trust bundle must be UTF-8 JSON text or bytes.")
    try:
        text = raw_bundle.decode("utf-8") if type(raw_bundle) is bytes else raw_bundle
        envelope = json.loads(text, object_pairs_hook=_unique_object)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise InspectorTrustBundleError("Trust bundle is not valid UTF-8 JSON.") from exc
    if not isinstance(envelope, dict) or set(envelope) != _BUNDLE_FIELDS:
        raise InspectorTrustBundleError("Trust bundle envelope has missing or unknown fields.")
    if type(envelope["schema_version"]) is not int or envelope["schema_version"] != 1:
        raise InspectorTrustBundleError("Unsupported trust-bundle envelope schema.")
    issuer = envelope["issuer_key_id"]
    if issuer != expected_issuer_key_id:
        raise InspectorTrustBundleError("Trust-bundle issuer does not match the pinned issuer.")
    payload = envelope["payload"]
    if not isinstance(payload, dict) or set(payload) != _PAYLOAD_FIELDS:
        raise InspectorTrustBundleError("Trust-bundle payload has missing or unknown fields.")
    if type(payload["schema_version"]) is not int or payload["schema_version"] != 1:
        raise InspectorTrustBundleError("Unsupported trust-bundle payload schema.")
    sequence = payload["sequence"]
    issued_at = payload["issued_at"]
    expires_at = payload["expires_at"]
    if type(sequence) is not int or sequence < minimum_sequence:
        raise InspectorTrustBundleError("Trust bundle is stale or its sequence rolled back.")
    if (type(issued_at) is not int or type(expires_at) is not int
            or issued_at < 0 or expires_at <= issued_at
            or issued_at > current + 5 or current >= expires_at):
        raise InspectorTrustBundleError("Trust bundle is not currently valid.")
    signature_text = envelope["signature"]
    if type(signature_text) is not str:
        raise InspectorTrustBundleError("Trust-bundle signature must be base64 text.")
    try:
        signature = base64.b64decode(signature_text, validate=True)
        Ed25519PublicKey.from_public_bytes(root_public_key).verify(
            signature,
            _canonical({
                "schema_version": 1,
                "issuer_key_id": issuer,
                "payload": payload,
            }),
        )
    except (ValueError, binascii.Error, InvalidSignature) as exc:
        raise InspectorTrustBundleError("Trust-bundle signature verification failed.") from exc

    raw_records = payload["keys"]
    if not isinstance(raw_records, list) or not raw_records or len(raw_records) > 64:
        raise InspectorTrustBundleError("Trust bundle must contain between 1 and 64 key records.")
    records: list[InspectorPublicKeyRecord] = []
    for item in raw_records:
        if not isinstance(item, dict) or set(item) != _RECORD_FIELDS:
            raise InspectorTrustBundleError("Inspector key record has missing or unknown fields.")
        if type(item["key_id"]) is not str or not _KEY_ID.fullmatch(item["key_id"]):
            raise InspectorTrustBundleError("Inspector key record ID is invalid.")
        if type(item["public_key"]) is not str:
            raise InspectorTrustBundleError("Inspector public key must be base64 text.")
        try:
            public_key = base64.b64decode(item["public_key"], validate=True)
        except (ValueError, binascii.Error) as exc:
            raise InspectorTrustBundleError("Inspector public-key encoding is invalid.") from exc
        if (type(item["not_before"]) is not int or type(item["not_after"]) is not int
                or type(item["revoked"]) is not bool):
            raise InspectorTrustBundleError("Inspector key metadata has invalid types.")
        records.append(InspectorPublicKeyRecord(
            key_id=item["key_id"],
            public_key=public_key,
            not_before=item["not_before"],
            not_after=item["not_after"],
            revoked=item["revoked"],
        ))
    try:
        registry = InspectorPublicKeyRegistry(records)
    except (InspectorKeyRegistryError, TypeError) as exc:
        raise InspectorTrustBundleError("Inspector key registry rejected the signed records.") from exc
    if not registry.active_public_keys(now=current):
        raise InspectorTrustBundleError("Trust bundle contains no currently active inspector key.")
    return registry, sequence
