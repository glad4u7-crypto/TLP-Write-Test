"""Fail-closed destination authorization contract for a future egress gateway.

This module prepares a validated, immutable destination record. It does NOT
open sockets or claim to eliminate DNS rebinding. A production gateway must
connect only to one of the returned pinned IP addresses while retaining the
original hostname for TLS SNI/certificate verification, and must enforce the
same policy for every redirect and subresource.
"""
from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from typing import Iterable

from core.browser_navigation import NavigationPolicy, NavigationPolicyError


@dataclass(frozen=True)
class EgressTarget:
    hostname: str
    port: int
    scheme: str
    pinned_addresses: tuple[str, ...]


class EgressAuthorizationError(RuntimeError):
    """Raised when an egress destination cannot be safely authorized."""


class EgressDestinationAuthorizer:
    """Resolve once and issue a destination record for a pinned connector."""

    def __init__(self, policy: NavigationPolicy) -> None:
        if not isinstance(policy, NavigationPolicy):
            raise TypeError("policy must be a NavigationPolicy.")
        self._policy = policy

    def authorize(self, url: str) -> EgressTarget:
        """Return validated host/port and exact public IPs for a trusted dialer.

        The injected NavigationPolicy resolver is called during validation.
        This authorizer does not connect, retry DNS, or permit the dialer to
        resolve the hostname independently.
        """
        try:
            self._policy.validate_url(url)
            from urllib.parse import urlsplit

            parts = urlsplit(url)
            hostname = parts.hostname
            if hostname is None:
                raise EgressAuthorizationError("Destination hostname is missing.")
            port = parts.port or (443 if parts.scheme.lower() == "https" else 80)
            addresses = tuple(dict.fromkeys(self._policy.resolver(hostname)))
            if not addresses:
                raise EgressAuthorizationError("Destination has no pinned addresses.")
            normalised: list[str] = []
            for value in addresses:
                address = ipaddress.ip_address(value.split("%", 1)[0])
                if not address.is_global:
                    raise EgressAuthorizationError("Non-public destination address blocked.")
                normalised.append(address.compressed)
            return EgressTarget(
                hostname=hostname.encode("idna").decode("ascii").lower(),
                port=port,
                scheme=parts.scheme.lower(),
                pinned_addresses=tuple(normalised),
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
