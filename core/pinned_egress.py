"""Resolve once, validate every answer, and dial only the selected numeric IP."""
from __future__ import annotations

from dataclasses import dataclass
import ipaddress
import socket
from typing import Callable, Sequence


class PinnedEgressError(RuntimeError):
    pass


@dataclass(frozen=True)
class PinnedDestination:
    hostname: str
    port: int
    addresses: tuple[str, ...]

    def __post_init__(self):
        if not self.hostname or type(self.port) is not int or not 1 <= self.port <= 65535:
            raise ValueError("invalid pinned destination")
        if not self.addresses or len(self.addresses) > 16:
            raise ValueError("pinned destination must contain bounded IP answers")
        canonical = []
        for value in self.addresses:
            address = ipaddress.ip_address(value)
            if not _public_unicast(address):
                raise ValueError("pinned destination contains a non-public address")
            canonical.append(address.compressed)
        if len(set(canonical)) != len(canonical):
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
        records = resolver(hostname, port, socket.AF_UNSPEC, socket.SOCK_STREAM, socket.IPPROTO_TCP)
    except OSError as exc:
        raise PinnedEgressError("DNS resolution failed") from exc
    if not records or len(records) > 64:
        raise PinnedEgressError("DNS answer set is empty or exceeds the limit")
    addresses = []
    for record in records:
        try:
            address = ipaddress.ip_address(record[4][0])
        except (IndexError, TypeError, ValueError) as exc:
            raise PinnedEgressError("DNS returned an invalid address") from exc
        if not _public_unicast(address):
            # Reject the complete answer set; never silently discard a private answer.
            raise PinnedEgressError("DNS answer set contains a blocked address")
        addresses.append(address.compressed)
    unique = tuple(dict.fromkeys(addresses))
    if not unique:
        raise PinnedEgressError("DNS returned no usable addresses")
    return PinnedDestination(hostname=hostname, port=port, addresses=unique)


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
    if address not in destination.addresses:
        raise PinnedEgressError("dial target is not part of the pinned DNS answer set")
    parsed = ipaddress.ip_address(address)
    family = socket.AF_INET if parsed.version == 4 else socket.AF_INET6
    sock = socket_factory(family, socket.SOCK_STREAM, socket.IPPROTO_TCP)
    try:
        sock.settimeout(timeout)
        target = (parsed.compressed, destination.port) if parsed.version == 4 else (parsed.compressed, destination.port, 0, 0)
        sock.connect(target)
        peer = sock.getpeername()[0]
        if ipaddress.ip_address(peer) != parsed:
            raise PinnedEgressError("connected peer differs from the pinned destination")
        return sock
    except Exception:
        sock.close()
        raise
