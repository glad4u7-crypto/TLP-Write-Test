"""Offline, dual-control Global Owner recovery and re-key protocol."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import re
from typing import Protocol
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from core.sqlite_security_store import GlobalOwnerState, GlobalOwnerStateConflict, SQLiteSecurityStore

_CHANGE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{2,127}$")
_KEY_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{2,63}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_NONCE = re.compile(r"^[0-9a-f]{64}$")
_REASON = re.compile(r"^[a-z][a-z0-9_]{2,63}$")
MAX_REQUEST_LIFETIME_SECONDS = 1800
CLOCK_SKEW_SECONDS = 30

class RecoveryDenied(PermissionError):
    """A recovery request failed a security gate."""

@dataclass(frozen=True)
class RecoveryRequest:
    change_id: str
    action: str
    expected_revision: int
    old_generation: str | None
    new_generation: str | None
    reason_code: str
    nonce: str
    issued_at: int
    expires_at: int
    operator_key_id: str
    approver_key_id: str

@dataclass(frozen=True)
class SignedRecoveryRequest:
    request: RecoveryRequest
    operator_signature: bytes
    approver_signature: bytes

@dataclass(frozen=True)
class RecoveryPublicKey:
    key_id: str
    raw_public_key: bytes

@dataclass(frozen=True)
class RecoveryPolicy:
    operator_keys: tuple[RecoveryPublicKey, ...]
    approver_keys: tuple[RecoveryPublicKey, ...]

@dataclass(frozen=True)
class AnchorState:
    revision: int
    generation: str | None
    change_id: str | None

class MonotonicOwnerAnchor(Protocol):
    def read(self) -> AnchorState: ...
    def compare_and_advance(self, *, expected: AnchorState, target: AnchorState) -> bool: ...

@dataclass(frozen=True)
class RecoveryInspection:
    disposition: str
    local: GlobalOwnerState
    anchor: AnchorState

def canonical_request(request: RecoveryRequest) -> bytes:
    fields = (
        "APAA-OFFLINE-OWNER-RECOVERY-V1", request.change_id, request.action,
        str(request.expected_revision), request.old_generation or "-",
        request.new_generation or "-", request.reason_code, request.nonce,
        str(request.issued_at), str(request.expires_at),
        request.operator_key_id, request.approver_key_id,
    )
    return "\n".join(fields).encode("ascii")

def _fingerprint(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()

def _validate_key(key: RecoveryPublicKey) -> None:
    if (not isinstance(key, RecoveryPublicKey) or type(key.key_id) is not str
        or not _KEY_ID.fullmatch(key.key_id) or type(key.raw_public_key) is not bytes
        or len(key.raw_public_key) != 32):
        raise RecoveryDenied("Recovery verification policy is invalid.")

def _verify_signature(key: RecoveryPublicKey, signature: bytes, message: bytes) -> None:
    try:
        if type(signature) is not bytes or len(signature) != 64:
            raise ValueError("invalid signature length")
        Ed25519PublicKey.from_public_bytes(key.raw_public_key).verify(signature, message)
    except (InvalidSignature, ValueError, TypeError):
        raise RecoveryDenied("Recovery authorization signature is invalid.") from None

class OfflineOwnerRecoveryService:
    """Dual-control coordinator; no UI or online authorization path."""
    def __init__(self, store: SQLiteSecurityStore, policy: RecoveryPolicy,
                 anchor: MonotonicOwnerAnchor) -> None:
        if not isinstance(store, SQLiteSecurityStore):
            raise TypeError("A durable SQLiteSecurityStore is required.")
        if not isinstance(policy, RecoveryPolicy):
            raise TypeError("A trusted RecoveryPolicy is required.")
        if not callable(getattr(anchor, "read", None)) or not callable(getattr(anchor, "compare_and_advance", None)):
            raise TypeError("An independent monotonic owner anchor is required.")
        self._store, self._anchor = store, anchor
        self._operators = self._index_keys(policy.operator_keys)
        self._approvers = self._index_keys(policy.approver_keys)
        op_fps = {_fingerprint(k.raw_public_key) for k in self._operators.values()}
        ap_fps = {_fingerprint(k.raw_public_key) for k in self._approvers.values()}
        if op_fps & ap_fps:
            raise RecoveryDenied("Operator and approver trust domains must be independent.")

    @staticmethod
    def _index_keys(keys: tuple[RecoveryPublicKey, ...]) -> dict[str, RecoveryPublicKey]:
        if type(keys) is not tuple or not keys:
            raise RecoveryDenied("Recovery verification policy is incomplete.")
        result = {}
        for key in keys:
            _validate_key(key)
            if key.key_id in result:
                raise RecoveryDenied("Recovery verification key identifiers are duplicated.")
            result[key.key_id] = key
        return result

    def inspect(self) -> RecoveryInspection:
        local = self._store.read_global_owner_state()
        anchor = self._anchor.read()
        if not isinstance(anchor, AnchorState):
            raise RecoveryDenied("Independent rollback anchor is unavailable.")
        local_state = AnchorState(local.revision, local.generation, local.change_id)
        if anchor == local_state:
            disposition = "CONSISTENT"
        elif (anchor.revision == local.revision + 1 and anchor.change_id is not None
              and anchor.generation != local.generation):
            disposition = "ANCHOR_AHEAD_RESUMABLE"
        else:
            disposition = "DIVERGED_BLOCKED"
        return RecoveryInspection(disposition, local, anchor)

    @staticmethod
    def _validate_request(r: RecoveryRequest, now: int) -> None:
        if not isinstance(r, RecoveryRequest):
            raise RecoveryDenied("Recovery request is malformed.")
        if (type(r.change_id) is not str or not _CHANGE_ID.fullmatch(r.change_id)
            or r.action not in ("rekey", "revoke")
            or type(r.expected_revision) is not int or r.expected_revision < 0
            or type(r.reason_code) is not str or not _REASON.fullmatch(r.reason_code)
            or type(r.nonce) is not str or not _NONCE.fullmatch(r.nonce)
            or type(r.issued_at) is not int or type(r.expires_at) is not int
            or type(now) is not int or r.issued_at > now + CLOCK_SKEW_SECONDS
            or r.expires_at <= now or r.expires_at <= r.issued_at
            or r.expires_at - r.issued_at > MAX_REQUEST_LIFETIME_SECONDS
            or type(r.operator_key_id) is not str or not _KEY_ID.fullmatch(r.operator_key_id)
            or type(r.approver_key_id) is not str or not _KEY_ID.fullmatch(r.approver_key_id)
            or r.operator_key_id == r.approver_key_id):
            raise RecoveryDenied("Recovery request fields or validity window are invalid.")
        if r.old_generation is not None and (type(r.old_generation) is not str or not _DIGEST.fullmatch(r.old_generation)):
            raise RecoveryDenied("Previous owner generation is invalid.")
        if r.action == "rekey":
            if type(r.new_generation) is not str or not _DIGEST.fullmatch(r.new_generation):
                raise RecoveryDenied("New owner generation is invalid.")
        elif r.new_generation is not None:
            raise RecoveryDenied("Revocation must not carry a replacement generation.")
        if r.old_generation == r.new_generation:
            raise RecoveryDenied("Recovery must change or revoke the current generation.")

    def apply(self, envelope: SignedRecoveryRequest, *, now: int | None = None) -> GlobalOwnerState:
        current_time = int(datetime.now(timezone.utc).timestamp()) if now is None else now
        if not isinstance(envelope, SignedRecoveryRequest):
            raise RecoveryDenied("A dual-signed offline recovery envelope is required.")
        r = envelope.request
        self._validate_request(r, current_time)
        operator, approver = self._operators.get(r.operator_key_id), self._approvers.get(r.approver_key_id)
        if operator is None or approver is None or operator.raw_public_key == approver.raw_public_key:
            raise RecoveryDenied("Authorized operator and independent approver are required.")
        message = canonical_request(r)
        _verify_signature(operator, envelope.operator_signature, message)
        _verify_signature(approver, envelope.approver_signature, message)

        local = self._store.read_global_owner_state()
        local_anchor = AnchorState(local.revision, local.generation, local.change_id)
        target = AnchorState(r.expected_revision + 1, r.new_generation, r.change_id)
        anchor = self._anchor.read()
        if not isinstance(anchor, AnchorState):
            raise RecoveryDenied("Independent rollback anchor is unavailable.")
        if local_anchor == target:
            if anchor != target:
                raise RecoveryDenied("Owner state and independent rollback anchor diverged.")
            return local
        if local.revision != r.expected_revision or local.generation != r.old_generation:
            raise RecoveryDenied("Owner state changed; recovery request is stale.")
        if anchor == local_anchor:
            try:
                advanced = self._anchor.compare_and_advance(expected=anchor, target=target)
            except Exception:
                raise RecoveryDenied("Independent rollback anchor update failed.") from None
            if advanced is not True and self._anchor.read() != target:
                raise RecoveryDenied("Independent rollback anchor rejected the update.")
        elif anchor != target:
            raise RecoveryDenied("Rollback anchor is not at the expected state.")
        anchor_after = self._anchor.read()
        if anchor_after != target:
            raise RecoveryDenied("Independent rollback anchor confirmation failed.")

        operator_fp, approver_fp = _fingerprint(operator.raw_public_key), _fingerprint(approver.raw_public_key)
        audit_fp = hashlib.sha256((operator_fp + ":" + approver_fp).encode("ascii")).hexdigest()
        try:
            committed = self._store.compare_and_set_global_owner_generation(
                expected_revision=r.expected_revision, generation=r.new_generation,
                change_id=r.change_id, audit_principal_fingerprint=audit_fp,
                audit_reason_code=("offline_owner_rekey_approved" if r.action == "rekey"
                                   else "offline_owner_revocation_approved"),
            )
        except GlobalOwnerStateConflict:
            raise RecoveryDenied("Concurrent owner recovery won the state transition.") from None
        except Exception:
            raise RecoveryDenied("Local owner-state commit failed; rollback remains blocked.") from None
        if AnchorState(committed.revision, committed.generation, committed.change_id) != anchor_after:
            raise RecoveryDenied("Committed owner state does not match the rollback anchor.")
        if not self._store.verify_audit_chain():
            raise RecoveryDenied("Owner recovery audit integrity verification failed.")
        return committed
