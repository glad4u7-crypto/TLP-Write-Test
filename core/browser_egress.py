"""Offline connection-time egress decision primitives for a future proxy.

No socket, resolver, proxy server or firewall is started here. The deployment
proxy must call this policy for every CONNECT/request, resolve on its own trusted
side, pin the returned validated IP set for the actual connection, and prevent
the worker from reaching any destination except that proxy.
"""
from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Sequence

from core.browser_security import (
    BrowserPolicyError,
    Resolver,
    canonicalize_https_url,
    validate_destination,
    validate_dns_answers,
)


class EgressPolicyError(ValueError):
    """Raised when a proxy connection request violates egress policy."""


@dataclass(frozen=True)
class PinnedEgressDecision:
    hostname: str
    port: int
    origin: str
    validated_addresses: tuple[str, ...]
    tls_server_name: str


def validate_proxy_connect(
    target_url: object,
    allowed_origins: Sequence[str],
    resolved_addresses: Sequence[str],
) -> PinnedEgressDecision:
    """Validate one HTTPS proxy target and return the exact addresses to pin.

    The proxy must pass the DNS answers it just resolved itself. No fallback
    resolver is used. Only TCP/443 is allowed in the initial browser tier.
    """
    try:
        target = canonicalize_https_url(target_url)
        if target.port != 443:
            raise EgressPolicyError("Only HTTPS TCP port 443 is allowed.")
        addresses = validate_dns_answers(target.hostname, resolved_addresses)
        checked = validate_destination(
            target.url,
            allowed_origins,
            resolver=lambda _host: addresses,
        )
    except (BrowserPolicyError, TypeError) as exc:
        raise EgressPolicyError("Proxy destination rejected by browser egress policy.") from exc
    return PinnedEgressDecision(
        hostname=checked.hostname,
        port=443,
        origin=checked.origin,
        validated_addresses=addresses,
        tls_server_name=checked.hostname,
    )
