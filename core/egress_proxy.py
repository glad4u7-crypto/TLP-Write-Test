"""Loopback-only HTTPS CONNECT egress proxy.

This proxy accepts CONNECT only, authorizes each new tunnel, and opens the
upstream socket through PinnedIPConnector. It does not intercept TLS. The
operating system/container must still deny browser direct egress; this module
cannot install or prove that network guard.
"""
from __future__ import annotations

import ipaddress
import select
import socket
import socketserver
from dataclasses import dataclass
from typing import Callable
from urllib.parse import urlsplit

from core.egress_policy import EgressAuthorizationError, EgressDestinationAuthorizer
from core.pinned_ip_connector import PinnedIPConnector
from core.proxy_worker_topology import ProxyWorkerTopology


MAX_HEADER_BYTES = 16_384
HEADER_TIMEOUT_SECONDS = 5.0
DEFAULT_ALLOWED_PORTS = frozenset({443})


class ProxyRequestError(ValueError):
    """Raised for malformed or unsupported proxy requests."""


@dataclass(frozen=True)
class ConnectRequest:
    hostname: str
    port: int


def parse_connect_request(raw: bytes, *, allowed_ports: frozenset[int] = DEFAULT_ALLOWED_PORTS) -> ConnectRequest:
    """Parse a bounded HTTP/1.1 CONNECT header; reject all other methods."""
    if not isinstance(raw, bytes) or len(raw) > MAX_HEADER_BYTES:
        raise ProxyRequestError("Proxy request header is invalid or too large.")
    if b"\r\n\r\n" not in raw:
        raise ProxyRequestError("Proxy request header is incomplete.")
    head, remainder = raw.split(b"\r\n\r\n", 1)
    if remainder:
        raise ProxyRequestError("Unexpected bytes after CONNECT headers.")
    try:
        lines = head.decode("ascii").split("\r\n")
    except UnicodeDecodeError as exc:
        raise ProxyRequestError("Proxy request must use ASCII framing.") from exc
    if not lines or len(lines) > 65:
        raise ProxyRequestError("Proxy request has an invalid header count.")
    parts = lines[0].split(" ")
    if len(parts) != 3 or parts[0] != "CONNECT" or parts[2] != "HTTP/1.1":
        raise ProxyRequestError("Only HTTP/1.1 CONNECT is supported.")
    authority = parts[1]
    if not authority or any(ch in authority for ch in "/\\?#@"):
        raise ProxyRequestError("CONNECT authority is malformed.")
    try:
        parsed = urlsplit("//" + authority)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError as exc:
        raise ProxyRequestError("CONNECT authority is malformed.") from exc
    if not hostname or port is None or parsed.username is not None or parsed.password is not None:
        raise ProxyRequestError("CONNECT authority must include a hostname and port.")
    if port not in allowed_ports:
        raise ProxyRequestError("CONNECT destination port is not allowed.")

    # Accept no headers or one exact Host header. Reject ambiguous/unused
    # headers (including duplicate Host, framing, auth and proxy overrides).
    headers = lines[1:]
    if len(headers) > 1:
        raise ProxyRequestError("Only one CONNECT Host header is supported.")
    if headers:
        if ":" not in headers[0]:
            raise ProxyRequestError("CONNECT header is malformed.")
        name, value = headers[0].split(":", 1)
        if name.strip().lower() != "host" or not value.strip():
            raise ProxyRequestError("Only a matching Host header is supported.")
        try:
            host_header = urlsplit("//" + value.strip())
            header_host, header_port = host_header.hostname, host_header.port
        except ValueError as exc:
            raise ProxyRequestError("CONNECT Host header is malformed.") from exc
        if (host_header.username is not None or host_header.password is not None
                or host_header.path or host_header.query or host_header.fragment
                or header_host is None
                or header_host.lower() != hostname.lower()
                or header_port != port):
            raise ProxyRequestError("CONNECT Host header must match the request authority.")
    return ConnectRequest(hostname=hostname, port=port)


class EgressConnectProxy:
    """Serve explicitly requested HTTPS CONNECT tunnels on loopback only."""

    def __init__(
        self,
        authorizer: EgressDestinationAuthorizer,
        connector: PinnedIPConnector,
        *,
        allowed_ports: frozenset[int] = DEFAULT_ALLOWED_PORTS,
        bind_host: str = "127.0.0.1",
        bind_port: int = 0,
        topology: ProxyWorkerTopology | None = None,
    ) -> None:
        if not isinstance(authorizer, EgressDestinationAuthorizer):
            raise TypeError("authorizer must be an EgressDestinationAuthorizer.")
        if not isinstance(connector, PinnedIPConnector):
            raise TypeError("connector must be a PinnedIPConnector.")
        try:
            bind_ip = ipaddress.ip_address(bind_host)
        except ValueError as exc:
            raise ValueError("Proxy must bind to a numeric loopback address.") from exc
        if topology is None:
            if not bind_ip.is_loopback:
                raise ValueError("Non-loopback proxy binding requires an explicit validated worker topology.")
        else:
            if not isinstance(topology, ProxyWorkerTopology):
                raise TypeError("topology must be a validated ProxyWorkerTopology.")
            if (bind_ip.compressed != topology.proxy_address
                    or bind_port != topology.proxy_port
                    or allowed_ports != frozenset({topology.proxy_port})):
                raise ValueError("Proxy bind address, port and CONNECT allowlist must exactly match the topology.")
        if not allowed_ports or any(type(port) is not int or not 1 <= port <= 65535 for port in allowed_ports):
            raise ValueError("allowed_ports must contain valid TCP ports.")
        if type(bind_port) is not int or not 0 <= bind_port <= 65535:
            raise ValueError("bind_port must be between 0 and 65535.")
        self.authorizer = authorizer
        self.connector = connector
        self.allowed_ports = allowed_ports
        self.bind_host = bind_ip.compressed
        self.bind_port = bind_port

    def handle_client(self, client: socket.socket) -> None:
        """Handle one client; errors return a generic response without secrets."""
        upstream = None
        try:
            client.settimeout(HEADER_TIMEOUT_SECONDS)
            data = bytearray()
            while b"\r\n\r\n" not in data:
                chunk = client.recv(2048)
                if not chunk:
                    raise ProxyRequestError("Client closed before CONNECT headers completed.")
                data.extend(chunk)
                if len(data) > MAX_HEADER_BYTES:
                    raise ProxyRequestError("CONNECT header too large.")
            header, extra = bytes(data).split(b"\r\n\r\n", 1)
            if extra:
                raise ProxyRequestError("Unexpected bytes after CONNECT headers.")
            request = parse_connect_request(header + b"\r\n\r\n", allowed_ports=self.allowed_ports)
            target = self.authorizer.authorize(
                f"https://{_format_authority_host(request.hostname)}:{request.port}/"
            )
            pinned = self.connector.connect(target)
            upstream = pinned.socket
            client.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            client.settimeout(None)
            upstream.settimeout(None)
            self._relay(client, upstream)
        except (ProxyRequestError, EgressAuthorizationError, OSError, ValueError):
            try:
                client.sendall(b"HTTP/1.1 502 Bad Gateway\r\nConnection: close\r\nContent-Length: 0\r\n\r\n")
            except OSError:
                pass
        finally:
            if upstream is not None:
                try:
                    upstream.close()
                except OSError:
                    pass
            try:
                client.close()
            except OSError:
                pass

    @staticmethod
    def _relay(client: socket.socket, upstream: socket.socket) -> None:
        """Bidirectionally relay opaque TLS bytes; no TLS interception."""
        while True:
            readable, _, exceptional = select.select([client, upstream], [], [client, upstream])
            if exceptional:
                return
            for source in readable:
                payload = source.recv(65_536)
                if not payload:
                    return
                destination = upstream if source is client else client
                destination.sendall(payload)

    def make_server(self) -> socketserver.ThreadingTCPServer:
        """Create, but do not start, a loopback-only threaded proxy server."""
        proxy = self

        class Handler(socketserver.BaseRequestHandler):
            def handle(self) -> None:
                proxy.handle_client(self.request)

        class Server(socketserver.ThreadingTCPServer):
            allow_reuse_address = False
            daemon_threads = True
            block_on_close = True

        return Server((self.bind_host, self.bind_port), Handler)


def _format_authority_host(hostname: str) -> str:
    """Bracket IPv6 literals when rebuilding an HTTPS URL."""
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        return hostname
    return f"[{address.compressed}]" if address.version == 6 else address.compressed
