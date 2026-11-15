"""One-time, payload-bound approval receipts for trusted application UI code.

The approval authority must only be reachable from the trusted UI/controller.
Never expose it to the planner, model, or untrusted task content.
"""
from collections.abc import Mapping
from dataclasses import dataclass
import hashlib
import hmac
import json
import re
import secrets
import time
from typing import Any

from core.safety import authorize_action


def _payload_digest(payload: Mapping[str, Any] | None) -> str:
    try:
        canonical = json.dumps(
            payload or {},
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("Approval payload must contain JSON-compatible values.") from exc
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ApprovalReceipt:
    action: str
    payload_digest: str
    expires_at: int
    nonce: str
    signature: str


class ApprovalAuthority:
    """Issues short-lived, one-time receipts after a trusted UI confirmation."""

    def __init__(self) -> None:
        self._secret = secrets.token_bytes(32)
        self._consumed_nonces: set[str] = set()

    @staticmethod
    def _canonical_action(action: str) -> str:
        if not isinstance(action, str):
            return ""
        return re.sub(r"[^a-z0-9]+", "_", action.strip().lower()).strip("_")

    def _message(
        self, action: str, payload_digest: str, expires_at: int, nonce: str
    ) -> bytes:
        return f"{action}\n{payload_digest}\n{expires_at}\n{nonce}".encode("utf-8")

    def issue(
        self,
        action: str,
        payload: Mapping[str, Any] | None,
        *,
        confirmed_by_user: bool,
        ttl_seconds: int = 120,
    ) -> ApprovalReceipt:
        """Issue only after a trusted UI has received explicit user confirmation."""
        if confirmed_by_user is not True:
            raise PermissionError("Explicit user confirmation is required.")
        if not isinstance(payload, (Mapping, type(None))):
            raise ValueError("Approval payload must be a mapping.")
        canonical = self._canonical_action(action)
        decision = authorize_action(canonical, approved_action=canonical)
        if not decision.allowed:
            raise PermissionError("This action is not eligible for approval.")
        if type(ttl_seconds) is not int or not 1 <= ttl_seconds <= 300:
            raise ValueError("Approval expiry must be between 1 and 300 seconds.")

        digest = _payload_digest(payload)
        expires_at = int(time.time()) + ttl_seconds
        nonce = secrets.token_urlsafe(24)
        signature = hmac.new(
            self._secret,
            self._message(canonical, digest, expires_at, nonce),
            hashlib.sha256,
        ).hexdigest()
        return ApprovalReceipt(canonical, digest, expires_at, nonce, signature)

    def consume(
        self,
        receipt: ApprovalReceipt | None,
        action: str,
        payload: Mapping[str, Any] | None,
    ) -> bool:
        """Verify action + payload + expiry + signature, then reject replay."""
        if not isinstance(receipt, ApprovalReceipt):
            return False
        canonical = self._canonical_action(action)
        if canonical != receipt.action or receipt.nonce in self._consumed_nonces:
            return False
        if not isinstance(payload, (Mapping, type(None))):
            return False
        if int(time.time()) >= receipt.expires_at:
            return False
        try:
            digest = _payload_digest(payload)
        except ValueError:
            return False
        if not hmac.compare_digest(digest, receipt.payload_digest):
            return False
        expected = hmac.new(
            self._secret,
            self._message(
                receipt.action,
                receipt.payload_digest,
                receipt.expires_at,
                receipt.nonce,
            ),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected, receipt.signature):
            return False
        self._consumed_nonces.add(receipt.nonce)
        return True
