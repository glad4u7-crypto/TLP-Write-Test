"""Pinned-IP TCP connector for an already-authorized egress target.

The connector never passes a hostname to the socket API. TLS is deliberately
outside this module: callers must use target.hostname for SNI and certificate
hostname verification after the pinned TCP connection is established.
"""
from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from typing import Callable, Protocol

from core.egress_policy import EgressAuthorizationError, EgressTarget


class ConnectedSocket(Protocol):
    def getpeername(self): ...
    def close(self) -> None: ...


SocketDialer = Callable[[str, int, float], ConnectedSocket]


@dataclass(frozen=True)
class PinnedConnection:
    """A connected socket plus the exact authorized numeric peer address."""

    socket: ConnectedSocket
    hostname: str
    port: int
    pinned_ip: str


def _numeric_socket_dialer(address: str, port: int, timeout: float) -> socket.socket:
    """Connect to a numeric IP literal without hostname resolution."""
    ip = ipaddress.ip_address(address)
    family = socket.AF_INET6 if ip.version == 6 else socket.AF_INET
    sock = socket.socket(family, socket.SOCK_STREAM)
    try:
        sock.settimeout(timeout)
        sockaddr = (ip.compressed, port, 0, 0) if ip.version == 6 else (ip.compressed, port)
        sock.connect(sockaddr)
        return sock
    except Exception:
        sock.close()
        raise


class PinnedIPConnector:
    """Dial only validated public IP pins and verify the actual socket peer."""

    def __init__(
        self,
        dialer: SocketDialer = _numeric_socket_dialer,
        *,
        timeout: float = 5.0,
    ) -> None:
        if not callable(dialer):
            raise TypeError("dialer must be callable.")
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 0 < timeout <= 60:
            raise ValueError("timeout must be greater than 0 and at most 60 seconds.")
        self._dialer = dialer
        self._timeout = float(timeout)

    def connect(self, target: EgressTarget) -> PinnedConnection:
        """Connect to one of target's pins; fail closed on peer mismatch.

        A failed TCP attempt may move to the next already-authorized pin. A
        peer mismatch is a security violation and aborts immediately.
        """
        if not isinstance(target, EgressTarget):
            raise TypeError("target must be an EgressTarget.")
        if not target.hostname or isinstance(target.port, bool) or not 1 <= target.port <= 65535:
            raise EgressAuthorizationError("Authorized target is malformed.")
        if not target.pinned_addresses:
            raise EgressAuthorizationError("Authorized target has no IP pins.")

        last_error: Exception | None = None
        for raw_pin in target.pinned_addresses:
            try:
                address = ipaddress.ip_address(raw_pin)
            except (TypeError, ValueError) as exc:
                raise EgressAuthorizationError("Authorized target contains an invalid IP pin.") from exc
            if not address.is_global or address.compressed != raw_pin:
                raise EgressAuthorizationError("Authorized target contains a non-canonical or non-public IP pin.")

            try:
                connection = self._dialer(address.compressed, target.port, self._timeout)
            except OSError as exc:
                last_error = exc
                continue

            try:
                peer = connection.getpeername()
                peer_ip = ipaddress.ip_address(peer[0]).compressed
            except Exception as exc:
                connection.close()
                raise EgressAuthorizationError("Connected socket peer could not be verified.") from exc

            if peer_ip != address.compressed:
                connection.close()
                raise EgressAuthorizationError("Connected socket peer does not match the selected IP pin.")

            return PinnedConnection(
                socket=connection,
                hostname=target.hostname,
                port=target.port,
                pinned_ip=address.compressed,
            )

        raise EgressAuthorizationError("All authorized pinned-IP connection attempts failed.") from last_error
