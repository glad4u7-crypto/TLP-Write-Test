"""Fail-closed destination authorization contract for a future egress gateway.

This module prepares a validated immutable destination record. It does NOT
open sockets or claim to eliminate DNS rebinding. A production gateway must
connect only to a returned pinned IP while retaining the original hostname
for TLS SNI/certificate verification, and enforce policy for every request.
"""
from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from urllib.parse import urlsplit

from core.browser_navigation import NavigationPolicy, NavigationPolicyError, _normalise_host


@dataclass(frozen=True)
class EgressTarget:
    hostname: str
    port: int
    scheme: str
    pinned_addresses: tuple[str, ...]


class EgressAuthorizationError(RuntimeError):
    """Raised when an egress destination cannot be safely authorized."""


class EgressDestinationAuthorizer:
    """Resolve exactly once and issue a destination record for a pinned dialer."""

    def __init__(self, policy: NavigationPolicy) -> None:
        if not isinstance(policy, NavigationPolicy):
            raise TypeError("policy must be a NavigationPolicy.")
        self._policy = policy

    def authorize(self, url: str) -> EgressTarget:
        """Validate URL and resolve once; never perform a network connection."""
        try:
            if not isinstance(url, str) or not url or len(url) > 4096:
                raise EgressAuthorizationError("Invalid destination URL.")
            if any(ord(ch) < 32 or ord(ch) == 127 for ch in url) or chr(92) in url:
                raise EgressAuthorizationError("Invalid destination URL.")
            parts = urlsplit(url)
            scheme = parts.scheme.lower()
            if scheme not in self._policy.allowed_schemes:
                raise EgressAuthorizationError("Destination scheme is not allowed.")
            if not parts.netloc or not parts.hostname:
                raise EgressAuthorizationError("Destination hostname is missing.")
            if parts.username is not None or parts.password is not None or "@" in parts.netloc:
                raise EgressAuthorizationError("URL credentials are not allowed.")
            port = parts.port or (443 if scheme == "https" else 80)
            host = _normalise_host(parts.hostname)
            if not 1 <= port <= 65535:
                raise EgressAuthorizationError("Destination port is invalid.")

            try:
                literal = ipaddress.ip_address(host)
            except ValueError:
                literal = None

            if literal is not None:
                if not literal.is_global or host not in self._policy.allowed_hosts:
                    raise EgressAuthorizationError("IP destination is not authorized.")
                addresses = (literal.compressed,)
            else:
                if host == "localhost" or host.endswith(".localhost"):
                    raise EgressAuthorizationError("Localhost is blocked.")
                allowed = any(
                    host == item or (
                        self._policy.allow_subdomains and host.endswith("." + item)
                    )
                    for item in self._policy.allowed_hosts
                )
                if not allowed:
                    raise EgressAuthorizationError("Hostname is not on the allowlist.")
                try:
                    addresses = tuple(dict.fromkeys(self._policy.resolver(host)))
                except Exception as exc:
                    raise EgressAuthorizationError("Destination resolution failed.") from exc
                if not addresses:
                    raise EgressAuthorizationError("Destination has no address records.")

            pins: list[str] = []
            for value in addresses:
                try:
                    address = ipaddress.ip_address(value.split("%", 1)[0])
                except ValueError as exc:
                    raise EgressAuthorizationError("Resolver returned an invalid IP.") from exc
                if not address.is_global:
                    raise EgressAuthorizationError("Non-public destination address blocked.")
                pins.append(address.compressed)

            return EgressTarget(
                hostname=host,
                port=port,
                scheme=scheme,
                pinned_addresses=tuple(pins),
            )
        except EgressAuthorizationError:
            raise
        except (NavigationPolicyError, ValueError, UnicodeError) as exc:
            raise EgressAuthorizationError("Egress destination denied.") from exc


def validate_connector_result(target: EgressTarget, connected_ip: str) -> str:
    """Verify a trusted connector reports an IP from the authorized pin set."""
    try:
        actual = ipaddress.ip_address(connected_ip).compressed
    except ValueError as exc:
        raise EgressAuthorizationError("Connector reported an invalid IP.") from exc
    if actual not in target.pinned_addresses:
        raise EgressAuthorizationError("Connector escaped the authorized IP pin set.")
    return actual
