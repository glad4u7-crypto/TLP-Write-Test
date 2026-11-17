"""Resolve once, validate every answer, and dial only the selected numeric IP."""
from __future__ import annotations

from dataclasses import dataclass
import ipaddress
import socket
from typing import Callable, Sequence

from core.browser_security import canonicalize_https_url


class PinnedEgressError(RuntimeError):
    pass


@dataclass(frozen=True)
class PinnedDestination:
    hostname: str
    port: int
    addresses: tuple[str, ...]

    def __post_init__(self):
        if type(self.hostname) is not str or type(self.port) is not int or not 1 <= self.port <= 65535:
            raise ValueError("invalid pinned destination")
        try:
            canonical = canonicalize_https_url(f"https://{self.hostname}/").hostname
        except ValueError as exc:
            raise ValueError("pinned destination hostname is invalid") from exc
        if canonical != self.hostname:
            raise ValueError("pinned destination hostname must be canonical lowercase IDNA")
        if type(self.addresses) is not tuple or not self.addresses or len(self.addresses) > 16:
            raise ValueError("pinned destination must contain a bounded tuple of IP answers")
        canonical_addresses = []
        for value in self.addresses:
            if type(value) is not str:
                raise ValueError("pinned destination address must be text")
            address = ipaddress.ip_address(value)
            if not _public_unicast(address) or address.compressed != value:
                raise ValueError("pinned destination contains a non-public or non-canonical address")
            canonical_addresses.append(address.compressed)
        if len(set(canonical_addresses)) != len(canonical_addresses):
            raise ValueError("duplicate pinned addresses are not accepted")


def _public_unicast(address):
    return bool(
        address.is_global and not address.is_private and not address.is_reserved
        and not address.is_loopback and not address.is_link_local
        and not address.is_multicast and not address.is_unspecified
    )


Resolver = Callable[..., Sequence[tuple]]
SocketFactory = Callable[..., socket.socket]


def resolve_and_pin(hostname: str, port: int, *, resolver: Resolver = socket.getaddrinfo) -> PinnedDestination:
    if type(hostname) is not str or not hostname or "/" in hostname or "%" in hostname:
        raise ValueError("hostname is invalid")
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError("port is invalid")
    try:
        canonical_hostname = canonicalize_https_url(f"https://{hostname}/").hostname
        records = resolver(canonical_hostname, port, socket.AF_UNSPEC, socket.SOCK_STREAM, socket.IPPROTO_TCP)
    except ValueError as exc:
        raise ValueError("hostname is invalid") from exc
    except OSError as exc:
        raise PinnedEgressError("DNS resolution failed") from exc
    if not records or len(records) > 64:
        raise PinnedEgressError("DNS answer set is empty or exceeds the limit")
    addresses = []
    for record in records:
        try:
            family, socktype, protocol, _canonical, sockaddr = record
            address = ipaddress.ip_address(sockaddr[0])
            answer_port = sockaddr[1]
        except (IndexError, TypeError, ValueError) as exc:
            raise PinnedEgressError("DNS returned an invalid address record") from exc
        expected_family = socket.AF_INET if address.version == 4 else socket.AF_INET6
        if family != expected_family or socktype != socket.SOCK_STREAM or protocol not in (0, socket.IPPROTO_TCP):
            raise PinnedEgressError("DNS returned an unexpected address family or transport")
        if answer_port != port:
            raise PinnedEgressError("DNS returned an unexpected destination port")
        if not _public_unicast(address):
            raise PinnedEgressError("DNS answer set contains a blocked address")
        addresses.append(address.compressed)
    unique = tuple(dict.fromkeys(addresses))
    if not unique:
        raise PinnedEgressError("DNS returned no usable addresses")
    return PinnedDestination(hostname=canonical_hostname, port=port, addresses=unique)


def connect_pinned(
    destination: PinnedDestination,
    address: str,
    *,
    timeout: float = 5.0,
    socket_factory: SocketFactory = socket.socket,
) -> socket.socket:
    """Connect to the exact validated numeric IP; performs no second DNS lookup.

    The caller must preserve destination.hostname as TLS SNI/verification name.
    No alternate IP, proxy bypass, or hostname-based fallback is attempted.
    """
    if type(address) is not str or address not in destination.addresses:
        raise PinnedEgressError("dial target is not part of the pinned DNS answer set")
    if type(timeout) not in (int, float) or not 0 < timeout <= 30:
        raise ValueError("dial timeout is outside supported bounds")
    parsed = ipaddress.ip_address(address)
    family = socket.AF_INET if parsed.version == 4 else socket.AF_INET6
    sock = socket_factory(family, socket.SOCK_STREAM, socket.IPPROTO_TCP)
    try:
        sock.settimeout(float(timeout))
        target = (parsed.compressed, destination.port) if parsed.version == 4 else (parsed.compressed, destination.port, 0, 0)
        sock.connect(target)
        peer = sock.getpeername()
        if (ipaddress.ip_address(peer[0]) != parsed or type(peer[1]) is not int
                or peer[1] != destination.port):
            raise PinnedEgressError("connected peer differs from the pinned destination and port")
        return sock
    except Exception:
        sock.close()
        raise
