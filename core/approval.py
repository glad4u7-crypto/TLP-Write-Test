"""Explicit, in-memory approval records; approvals never execute tools."""
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
import hashlib
import json
from uuid import uuid4

from core.tool_registry import ToolRegistry


BLOCKED_CATEGORIES = frozenset({
    "payment", "purchase", "checkout", "trading", "money_movement",
    "credential_access", "security_control_change",
})
VALID_STATUSES = frozenset({"pending", "approved", "rejected", "expired"})


@dataclass(frozen=True)
class ApprovalRequest:
    request_id: str
    tool_id: str
    summary: str
    payload_digest: str
    payload_preview: str
    status: str
    created_at: str
    expires_at: str
    decision_at: str = ""
    decision_note: str = ""


def _utc(value: datetime | None = None) -> datetime:
    current = value or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("Datetime must be timezone-aware.")
    return current.astimezone(timezone.utc)


def _payload_digest(payload: object) -> str:
    try:
        encoded = json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError("Payload must contain only finite JSON-compatible values.") from exc
    return hashlib.sha256(encoded).hexdigest()


class ApprovalManager:
    """Session-scoped approval queue. No persistence and no execution methods."""

    def __init__(self, registry: ToolRegistry, ttl_minutes: int = 15) -> None:
        if ttl_minutes < 1 or ttl_minutes > 1440:
            raise ValueError("Approval TTL must be between 1 and 1440 minutes.")
        self._registry = registry
        self._ttl = timedelta(minutes=ttl_minutes)
        self._requests: dict[str, ApprovalRequest] = {}

    def request(
        self, tool_id: str, summary: str, payload: object,
        now: datetime | None = None,
    ) -> ApprovalRequest:
        spec = self._registry.get(tool_id)
        if spec is None:
            raise ValueError("Tool is not present in the allow-list.")
        if spec.category.lower() in BLOCKED_CATEGORIES:
            raise ValueError("This action category is permanently blocked.")
        if spec.enabled:
            raise ValueError("Tool execution is disabled by policy.")
        if not isinstance(summary, str) or not summary.strip():
            raise ValueError("A clear action summary is required.")
        if not isinstance(payload, dict):
            raise ValueError("Payload must be a JSON object so the proposed action can be reviewed.")
        payload_json = json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
            allow_nan=False,
        )
        if len(payload_json.encode("utf-8")) > 8192:
            raise ValueError("Payload is too large for the approval queue.")
        sensitive_names = {"password", "passwd", "secret", "token", "api_key", "authorization", "cookie"}
        def contains_sensitive_key(value: object) -> bool:
            if isinstance(value, dict):
                return any(
                    str(key).lower() in sensitive_names or contains_sensitive_key(child)
                    for key, child in value.items()
                )
            if isinstance(value, list):
                return any(contains_sensitive_key(child) for child in value)
            return False
        if contains_sensitive_key(payload):
            raise ValueError("Credential-like fields must never be placed in approval payloads.")
        created = _utc(now)
        request_id = uuid4().hex
        item = ApprovalRequest(
            request_id=request_id,
            tool_id=tool_id,
            summary=summary.strip(),
            payload_digest=_payload_digest(payload),
            payload_preview=json.dumps(payload, sort_keys=True, ensure_ascii=False, indent=2),
            status="pending",
            created_at=created.isoformat(),
            expires_at=(created + self._ttl).isoformat(),
        )
        self._requests[request_id] = item
        return item

    def decide(
        self, request_id: str, approve: bool, note: str = "",
        now: datetime | None = None,
    ) -> ApprovalRequest:
        if not isinstance(approve, bool):
            raise ValueError("Decision must be an explicit boolean.")
        item = self._requests.get(request_id)
        if item is None:
            raise KeyError("Approval request was not found.")
        if item.status != "pending":
            raise ValueError("Only pending requests can receive a decision.")
        current = _utc(now)
        expiry = datetime.fromisoformat(item.expires_at)
        if current >= expiry:
            updated = replace(
                item, status="expired", decision_at=current.isoformat(),
                decision_note="Approval window expired.",
            )
        else:
            updated = replace(
                item,
                status="approved" if approve else "rejected",
                decision_at=current.isoformat(),
                decision_note=note.strip()[:240],
            )
        self._requests[request_id] = updated
        return updated

    def get(self, request_id: str) -> ApprovalRequest | None:
        return self._requests.get(request_id)

    def list_requests(self) -> tuple[ApprovalRequest, ...]:
        return tuple(
            sorted(self._requests.values(), key=lambda item: item.created_at, reverse=True)
        )
