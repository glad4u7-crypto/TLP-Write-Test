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
import threading
from typing import Any

from core.safety import authorize_action
from core.storage import TenantKey


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

    def __init__(self, *, nonce_store: Any | None = None, signing_secret: bytes | None = None) -> None:
        if signing_secret is not None and (not isinstance(signing_secret, bytes) or len(signing_secret) < 32):
            raise ValueError("Signing secret must contain at least 32 bytes.")
        self._secret = signing_secret if signing_secret is not None else secrets.token_bytes(32)
        self._consumed_nonces: set[str] = set()
        self._nonce_store = nonce_store
        self._consume_lock = threading.Lock()

    @staticmethod
    def _canonical_action(action: str) -> str:
        if not isinstance(action, str):
            return ""
        return re.sub(r"[^a-z0-9]+", "_", action.strip().lower()).strip("_")

    def _message(
        self, action: str, payload_digest: str, expires_at: int, nonce: str,
        tenant: TenantKey | None = None,
        session_scope: str = "",
    ) -> bytes:
        issuer = tenant.issuer if tenant is not None else ""
        subject = tenant.subject if tenant is not None else ""
        return f"{action}\n{payload_digest}\n{expires_at}\n{nonce}\n{issuer}\n{subject}\n{session_scope}".encode("utf-8")

    def issue(
        self,
        action: str,
        payload: Mapping[str, Any] | None,
        *,
        ttl_seconds: int = 120,
        tenant: TenantKey | None = None,
        session_scope: str = "",
    ) -> ApprovalReceipt:
        """Issue a receipt for a caller that is already inside the trusted UI boundary.

        This method is a capability, not an authentication mechanism. Do not
        expose an ApprovalAuthority instance to the planner or task content.
        """
        if not isinstance(payload, (Mapping, type(None))):
            raise ValueError("Approval payload must be a mapping.")
        if not isinstance(session_scope, str) or len(session_scope) > 256:
            raise ValueError("Approval session scope must be text of at most 256 characters.")
        if self._nonce_store is not None and not isinstance(tenant, TenantKey):
            raise ValueError("Durable approvals require a validated tenant identity.")
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
            self._message(canonical, digest, expires_at, nonce, tenant, session_scope),
            hashlib.sha256,
        ).hexdigest()
        return ApprovalReceipt(canonical, digest, expires_at, nonce, signature)

    def consume(
        self,
        receipt: ApprovalReceipt | None,
        action: str,
        payload: Mapping[str, Any] | None,
        *,
        tenant: TenantKey | None = None,
        session_scope: str = "",
    ) -> bool:
        """Atomically verify and consume a one-time receipt."""
        with self._consume_lock:
            return self._consume_locked(
                receipt, action, payload, tenant=tenant, session_scope=session_scope
            )

    def _consume_locked(
        self,
        receipt: ApprovalReceipt | None,
        action: str,
        payload: Mapping[str, Any] | None,
        *,
        tenant: TenantKey | None = None,
        session_scope: str = "",
    ) -> bool:
        """Verify action + payload + expiry + signature, then reject replay."""
        if not isinstance(receipt, ApprovalReceipt):
            return False
        if not isinstance(session_scope, str) or len(session_scope) > 256:
            return False

        # Dataclass annotations are not runtime validation. Treat every receipt
        # field as untrusted input and fail closed before hashing or set access.
        if (
            type(receipt.action) is not str
            or type(receipt.payload_digest) is not str
            or type(receipt.expires_at) is not int
            or type(receipt.nonce) is not str
            or type(receipt.signature) is not str
        ):
            return False
        if (
            not receipt.action
            or self._canonical_action(receipt.action) != receipt.action
            or re.fullmatch(r"[0-9a-f]{64}", receipt.payload_digest) is None
            or not receipt.nonce
            or re.fullmatch(r"[0-9a-f]{64}", receipt.signature) is None
        ):
            return False

        canonical = self._canonical_action(action)
        if canonical != receipt.action:
            return False
        if self._nonce_store is None and receipt.nonce in self._consumed_nonces:
            return False
        if self._nonce_store is not None and not isinstance(tenant, TenantKey):
            return False
        if not isinstance(payload, (Mapping, type(None))):
            return False
        if int(time.time()) >= receipt.expires_at:
            return False
        try:
            digest = _payload_digest(payload)
        except (TypeError, ValueError, OverflowError):
            return False
        if not hmac.compare_digest(digest, receipt.payload_digest):
            return False
        try:
            expected = hmac.new(
                self._secret,
                self._message(
                    receipt.action,
                    receipt.payload_digest,
                    receipt.expires_at,
                    receipt.nonce,
                    tenant,
                    session_scope,
                ),
                hashlib.sha256,
            ).hexdigest()
        except (TypeError, ValueError, UnicodeError):
            return False
        if not hmac.compare_digest(expected, receipt.signature):
            return False
        if self._nonce_store is not None:
            try:
                return bool(self._nonce_store.consume_approval_nonce(tenant, receipt.nonce, receipt.expires_at))
            except Exception:
                return False
        self._consumed_nonces.add(receipt.nonce)
        return True
