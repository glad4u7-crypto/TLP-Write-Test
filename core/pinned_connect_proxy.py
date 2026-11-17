"""Restricted HTTP CONNECT proxy with DNS-answer validation and numeric-IP dialing."""
from __future__ import annotations

import ipaddress
import select
import socket
import socketserver
import threading
from urllib.parse import urlsplit

from core.pinned_egress import PinnedEgressError, connect_pinned, resolve_and_pin


class ProxyPolicyError(RuntimeError):
    pass


def _canonical_host(value: str) -> str:
    if type(value) is not str or not value or value.endswith(".") or "%" in value:
        raise ProxyPolicyError("invalid CONNECT hostname")
    try:
        ipaddress.ip_address(value)
    except ValueError:
        pass
    else:
        raise ProxyPolicyError("IP literals are not accepted as CONNECT hostnames")
    try:
        parsed = urlsplit("https://" + value)
        if parsed.hostname != value or parsed.port is not None or parsed.username is not None:
            raise ValueError
        host = value.encode("idna").decode("ascii").lower()
    except (UnicodeError, ValueError):
        raise ProxyPolicyError("invalid CONNECT hostname") from None
    if len(host) > 253 or any(not label or len(label) > 63 for label in host.split(".")):
        raise ProxyPolicyError("invalid CONNECT hostname")
    return host


class PinnedConnectProxy:
    """One-session CONNECT proxy. TLS passes through unchanged to preserve SNI."""

    def __init__(self, bind_address: str, port: int, *, allowed_hosts: tuple[str, ...] | list[str],
                 allowed_port: int = 443, timeout_seconds: float = 5.0, resolver=socket.getaddrinfo):
        address = ipaddress.ip_address(bind_address)
        if address.is_unspecified or address.is_multicast or address.is_loopback or address.is_link_local:
            raise ValueError("proxy must bind to the dedicated host-side veth address")
        if type(port) is not int or not 1 <= port <= 65535:
            raise ValueError("proxy listen port is invalid")
        if type(allowed_port) is not int or allowed_port != 443:
            raise ValueError("only HTTPS CONNECT port 443 is supported")
        if not isinstance(allowed_hosts, (tuple, list)) or not allowed_hosts:
            raise ValueError("at least one exact HTTPS hostname is required")
        hosts = tuple(sorted({_canonical_host(host) for host in allowed_hosts}))
        if len(hosts) != len(allowed_hosts):
            raise ValueError("duplicate or non-canonical allowed host")
        if type(timeout_seconds) not in (int, float) or not 0.1 <= timeout_seconds <= 30:
            raise ValueError("proxy timeout is outside supported bounds")
        self.bind_address = address.compressed
        self.port = port
        self.allowed_hosts = frozenset(hosts)
        self.allowed_port = allowed_port
        self.timeout = float(timeout_seconds)
        self.resolver = resolver
        self._server = None
        self._thread = None

    def start(self) -> None:
        if self._server is not None:
            raise RuntimeError("proxy is already running")
        owner = self

        class Handler(socketserver.BaseRequestHandler):
            def handle(self):
                owner._handle_client(self.request)

        class Server(socketserver.ThreadingTCPServer):
            address_family = socket.AF_INET6 if ipaddress.ip_address(owner.bind_address).version == 6 else socket.AF_INET
            allow_reuse_address = False
            daemon_threads = True
            block_on_close = True

        self._server = Server((self.bind_address, self.port), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def _handle_client(self, client: socket.socket) -> None:
        upstream = None
        try:
            client.settimeout(self.timeout)
            request = bytearray()
            while b"\r\n\r\n" not in request:
                chunk = client.recv(1024)
                if not chunk:
                    return
                request.extend(chunk)
                if len(request) > 8192:
                    self._respond(client, 431, "Request Header Fields Too Large")
                    return
            header, remainder = bytes(request).split(b"\r\n\r\n", 1)
            try:
                method, authority, version = header.split(b"\r\n", 1)[0].decode("ascii").split(" ")
            except (UnicodeDecodeError, ValueError):
                self._respond(client, 400, "Bad Request")
                return
            if method != "CONNECT" or version not in ("HTTP/1.0", "HTTP/1.1"):
                self._respond(client, 405, "Method Not Allowed")
                return
            if authority.startswith("[") or authority.count(":") != 1:
                self._respond(client, 403, "Forbidden")
                return
            host, port_text = authority.rsplit(":", 1)
            try:
                normalized = _canonical_host(host)
                port = int(port_text)
            except (ProxyPolicyError, ValueError):
                self._respond(client, 403, "Forbidden")
                return
            if normalized not in self.allowed_hosts or port != self.allowed_port:
                self._respond(client, 403, "Forbidden")
                return
            pinned = resolve_and_pin(normalized, port, resolver=self.resolver)
            last_error = None
            for address in pinned.addresses:
                try:
                    upstream = connect_pinned(pinned, address, timeout=self.timeout)
                    break
                except (OSError, PinnedEgressError) as exc:
                    last_error = exc
            if upstream is None:
                raise ProxyPolicyError("no pinned destination was reachable") from last_error
            client.sendall(b"HTTP/1.1 200 Connection Established\r\nProxy-Agent: APAA-Pinned-Proxy\r\n\r\n")
            if remainder:
                upstream.sendall(remainder)
            client.settimeout(None)
            upstream.settimeout(None)
            peers = (client, upstream)
            while True:
                readable, _, exceptional = select.select(peers, [], peers, 30)
                if exceptional or not readable:
                    return
                for source in readable:
                    data = source.recv(65536)
                    if not data:
                        return
                    (upstream if source is client else client).sendall(data)
        except (OSError, ProxyPolicyError, PinnedEgressError, ValueError):
            try:
                self._respond(client, 502, "Bad Gateway")
            except OSError:
                pass
        finally:
            if upstream is not None:
                upstream.close()
            client.close()

    @staticmethod
    def _respond(client: socket.socket, code: int, reason: str) -> None:
        client.sendall(f"HTTP/1.1 {code} {reason}\r\nConnection: close\r\nContent-Length: 0\r\n\r\n".encode("ascii"))

    def close(self) -> None:
        server, thread = self._server, self._thread
        self._server = self._thread = None
        if server is not None:
            server.shutdown()
            server.server_close()
        if thread is not None:
            thread.join(timeout=3)
            if thread.is_alive():
                raise RuntimeError("proxy listener thread did not stop")
