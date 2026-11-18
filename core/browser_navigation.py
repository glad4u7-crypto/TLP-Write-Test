"""URL and redirect policy for a future browser navigation adapter.

This module validates destinations; it does not perform network requests or
navigate a browser. DNS resolution is injectable so callers can fail closed
when a hostname resolves to a non-public address.
"""
from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass, field
from typing import Callable, Iterable
from urllib.parse import SplitResult, urlsplit


class NavigationPolicyError(ValueError):
    """Raised when a URL or redirect violates the navigation policy."""


AddressResolver = Callable[[str], Iterable[str]]


def _system_resolver(host: str) -> tuple[str, ...]:
    try:
        records = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise NavigationPolicyError("Destination hostname could not be resolved.") from exc
    return tuple({record[4][0] for record in records})


def _normalise_host(host: str) -> str:
    if not isinstance(host, str) or not host or "%" in host:
        raise NavigationPolicyError("A valid destination hostname is required.")
    try:
        return ipaddress.ip_address(host).compressed
    except ValueError:
        pass
    try:
        # IDNA makes allowlist comparisons deterministic for international names.
        value = host.rstrip(".").encode("idna").decode("ascii").lower()
    except UnicodeError as exc:
        raise NavigationPolicyError("Destination hostname is invalid.") from exc
    if not value or len(value) > 253:
        raise NavigationPolicyError("Destination hostname is invalid.")
    labels = value.split(".")
    if any(not label or len(label) > 63 or label.startswith("-") or label.endswith("-")
           or not all(ch.isalnum() or ch == "-" for ch in label) for label in labels):
        raise NavigationPolicyError("Destination hostname is invalid.")
    return value


def _is_public_address(value: str) -> bool:
    try:
        address = ipaddress.ip_address(value.split("%", 1)[0])
    except ValueError as exc:
        raise NavigationPolicyError("Resolver returned an invalid IP address.") from exc
    return address.is_global


@dataclass(frozen=True)
class NavigationPolicy:
    """Explicit HTTPS/HTTP destination allowlist and bounded redirect policy."""

    allowed_hosts: frozenset[str]
    allow_subdomains: bool = True
    allowed_schemes: frozenset[str] = field(default_factory=lambda: frozenset({"https"}))
    max_redirects: int = 5
    resolver: AddressResolver = field(default=_system_resolver, compare=False, repr=False)

    def __post_init__(self) -> None:
        # Keep policy configuration immutable and reject malformed runtime types.
        if not isinstance(self.allowed_hosts, frozenset) or not self.allowed_hosts:
            raise ValueError("allowed_hosts must be a non-empty frozenset.")
        if type(self.allow_subdomains) is not bool:
            raise TypeError("allow_subdomains must be a boolean.")
        if type(self.max_redirects) is not int or not 0 <= self.max_redirects <= 10:
            raise ValueError("max_redirects must be an integer from 0 to 10.")
        if not isinstance(self.allowed_schemes, frozenset) or not self.allowed_schemes:
            raise ValueError("allowed_schemes must be a non-empty frozenset.")
        if any(not isinstance(item, str) for item in self.allowed_schemes):
            raise TypeError("Every allowed scheme must be a string.")
        schemes = frozenset(item.lower() for item in self.allowed_schemes)
        if not schemes <= {"http", "https"}:
            raise ValueError("Only explicitly selected http/https schemes are supported.")
        if not callable(self.resolver):
            raise TypeError("resolver must be callable.")
        normalised = frozenset(_normalise_host(host) for host in self.allowed_hosts)
        object.__setattr__(self, "allowed_hosts", normalised)
        object.__setattr__(self, "allowed_schemes", schemes)

    def validate_url(self, url: str) -> str:
        if not isinstance(url, str) or not url or len(url) > 4096:
            raise NavigationPolicyError("URL must be a non-empty string up to 4096 characters.")
        if any(ord(ch) < 32 or ord(ch) == 127 for ch in url) or chr(92) in url:
            raise NavigationPolicyError("URL contains forbidden control or backslash characters.")
        try:
            parts: SplitResult = urlsplit(url)
            scheme = parts.scheme.lower()
            host_raw = parts.hostname
            port = parts.port  # Forces malformed/out-of-range port validation.
        except ValueError as exc:
            raise NavigationPolicyError("URL is malformed.") from exc
        if scheme not in self.allowed_schemes:
            raise NavigationPolicyError("URL scheme is not allowed.")
        if not parts.netloc or not host_raw:
            raise NavigationPolicyError("URL must include a hostname.")
        if parts.username is not None or parts.password is not None or "@" in parts.netloc:
            raise NavigationPolicyError("URL credentials are not allowed.")
        if port is not None and not 1 <= port <= 65535:
            raise NavigationPolicyError("URL port is invalid.")
        host = _normalise_host(host_raw)
        try:
            literal = ipaddress.ip_address(host)
        except ValueError:
            literal = None
        if literal is not None:
            if not literal.is_global:
                raise NavigationPolicyError("Private or special-use IP destinations are blocked.")
            if host not in self.allowed_hosts:
                raise NavigationPolicyError("IP destination is not on the explicit allowlist.")
            resolved = (str(literal),)
        else:
            if host == "localhost" or host.endswith(".localhost"):
                raise NavigationPolicyError("Localhost destinations are blocked.")
            allowed = any(
                host == item or (self.allow_subdomains and host.endswith("." + item))
                for item in self.allowed_hosts
            )
            if not allowed:
                raise NavigationPolicyError("Hostname is not on the explicit allowlist.")
            try:
                resolved = tuple(self.resolver(host))
            except NavigationPolicyError:
                raise
            except Exception as exc:
                raise NavigationPolicyError("Destination hostname could not be resolved.") from exc
            if not resolved:
                raise NavigationPolicyError("Destination hostname has no address records.")
        if any(not _is_public_address(address) for address in resolved):
            raise NavigationPolicyError("Hostname resolves to a private or special-use address.")
        return url

    def validate_redirect_chain(self, initial_url: str, redirect_urls: Iterable[str]) -> str:
        """Revalidate every hop; return final URL or fail on escape/loop/limit."""
        current = self.validate_url(initial_url)
        seen = {current}
        count = 0
        for target in redirect_urls:
            count += 1
            if count > self.max_redirects:
                raise NavigationPolicyError("Redirect limit exceeded.")
            validated = self.validate_url(target)
            if validated in seen:
                raise NavigationPolicyError("Redirect loop detected.")
            seen.add(validated)
            current = validated
        return current
