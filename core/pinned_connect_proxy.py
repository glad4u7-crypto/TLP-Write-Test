"""Restricted HTTP CONNECT proxy with DNS-answer validation and numeric-IP dialing."""
from __future__ import annotations

import ipaddress
import select
import socket
import socketserver
import threading

from core.browser_security import canonicalize_https_url
from core.pinned_egress import PinnedEgressError, connect_pinned, resolve_and_pin


class ProxyPolicyError(RuntimeError):
    pass


def _canonical_host(value: str) -> str:
    if (type(value) is not str or not value or value.endswith(".") or "%"
            in value or any(char in value for char in "/?#@:")
            or any(ord(char) <= 32 or ord(char) == 127 for char in value)):
        raise ProxyPolicyError("invalid CONNECT hostname")
    try:
        ipaddress.ip_address(value)
    except ValueError:
        pass
    else:
        raise ProxyPolicyError("IP literals are not accepted as CONNECT hostnames")
    try:
        return canonicalize_https_url("https://" + value + "/").hostname
    except ValueError:
        raise ProxyPolicyError("invalid CONNECT hostname") from None


def _extract_client_hello_sni(handshake: bytes) -> str:
    """Parse a bounded TLS ClientHello and return its single canonical host SNI."""
    if type(handshake) is not bytes or len(handshake) < 4 or handshake[0] != 1:
        raise ProxyPolicyError("TLS tunnel must begin with a ClientHello")
    message_length = int.from_bytes(handshake[1:4], "big")
    if message_length > 65532 or len(handshake) < 4 + message_length:
        raise ProxyPolicyError("TLS ClientHello length is invalid")
    body = memoryview(handshake)[4:4 + message_length]
    offset = 0

    def take(length: int) -> bytes:
        nonlocal offset
        if type(length) is not int or length < 0 or offset + length > len(body):
            raise ProxyPolicyError("TLS ClientHello is truncated")
        value = bytes(body[offset:offset + length])
        offset += length
        return value

    take(2)
    take(32)
    session_length = take(1)[0]
    if session_length > 32:
        raise ProxyPolicyError("TLS session ID length is invalid")
    take(session_length)
    cipher_length = int.from_bytes(take(2), "big")
    if cipher_length < 2 or cipher_length % 2:
        raise ProxyPolicyError("TLS cipher-suite vector is invalid")
    take(cipher_length)
    compression_length = take(1)[0]
    if compression_length < 1:
        raise ProxyPolicyError("TLS compression vector is invalid")
    take(compression_length)
    if offset == len(body):
        raise ProxyPolicyError("TLS ClientHello is missing its SNI extension")
    extensions_length = int.from_bytes(take(2), "big")
    extensions = take(extensions_length)
    if offset != len(body):
        raise ProxyPolicyError("TLS ClientHello has trailing malformed data")

    sni_values: list[str] = []
    ext_offset = 0
    while ext_offset < len(extensions):
        if ext_offset + 4 > len(extensions):
            raise ProxyPolicyError("TLS extension header is truncated")
        extension_type = int.from_bytes(extensions[ext_offset:ext_offset + 2], "big")
        extension_length = int.from_bytes(extensions[ext_offset + 2:ext_offset + 4], "big")
        ext_offset += 4
        extension = extensions[ext_offset:ext_offset + extension_length]
        if len(extension) != extension_length:
            raise ProxyPolicyError("TLS extension body is truncated")
        ext_offset += extension_length
        if extension_type != 0:
            continue
        if len(extension) < 2:
            raise ProxyPolicyError("TLS SNI extension is malformed")
        names_length = int.from_bytes(extension[:2], "big")
        if names_length != len(extension) - 2:
            raise ProxyPolicyError("TLS SNI name list length is invalid")
        name_offset = 2
        while name_offset < len(extension):
            if name_offset + 3 > len(extension):
                raise ProxyPolicyError("TLS SNI name entry is truncated")
            name_type = extension[name_offset]
            name_length = int.from_bytes(extension[name_offset + 1:name_offset + 3], "big")
            name_offset += 3
            name_bytes = extension[name_offset:name_offset + name_length]
            if len(name_bytes) != name_length or name_type != 0:
                raise ProxyPolicyError("TLS SNI name entry is unsupported or malformed")
            name_offset += name_length
            try:
                sni_values.append(_canonical_host(name_bytes.decode("ascii")))
            except (UnicodeDecodeError, ProxyPolicyError):
                raise ProxyPolicyError("TLS SNI hostname is invalid") from None
    if len(sni_values) != 1:
        raise ProxyPolicyError("TLS ClientHello must contain exactly one host SNI")
    return sni_values[0]


def _read_client_hello(client: socket.socket, initial: bytes = b"") -> tuple[str, bytes]:
    """Read complete bounded TLS handshake records without forwarding them yet."""
    wire = bytearray(initial)
    offset = 0
    handshake = bytearray()
    message_length: int | None = None
    while True:
        while len(wire) - offset >= 5:
            content_type, major, minor = wire[offset], wire[offset + 1], wire[offset + 2]
            record_length = int.from_bytes(wire[offset + 3:offset + 5], "big")
            if content_type != 22 or major != 3 or minor > 4 or not 1 <= record_length <= 18432:
                raise ProxyPolicyError("TLS tunnel did not begin with a valid handshake record")
            record_end = offset + 5 + record_length
            if record_end > len(wire):
                break
            handshake.extend(wire[offset + 5:record_end])
            offset = record_end
            if len(handshake) >= 4 and message_length is None:
                if handshake[0] != 1:
                    raise ProxyPolicyError("TLS tunnel did not begin with a ClientHello")
                body_length = int.from_bytes(handshake[1:4], "big")
                if body_length > 65532:
                    raise ProxyPolicyError("TLS ClientHello exceeds the size limit")
                message_length = 4 + body_length
            if message_length is not None and len(handshake) >= message_length:
                sni = _extract_client_hello_sni(bytes(handshake[:message_length]))
                return sni, bytes(wire)
        if len(wire) >= 65536:
            raise ProxyPolicyError("TLS ClientHello exceeds the read limit")
        chunk = client.recv(min(4096, 65536 - len(wire)))
        if not chunk:
            raise ProxyPolicyError("TLS client closed before sending a complete ClientHello")
        wire.extend(chunk)


class PinnedConnectProxy:
    """One-session CONNECT proxy. TLS passes through unchanged to preserve SNI."""

    def __init__(
        self,
        bind_address: str,
        port: int,
        *,
        allowed_hosts: tuple[str, ...] | list[str],
        allowed_port: int = 443,
        timeout_seconds: float = 5.0,
        resolver=socket.getaddrinfo,
    ):
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
        self._stats_lock = threading.Lock()
        self._dialed_addresses: list[str] = []
        self._accepted_connections = 0
        self._rejected_requests = 0
        self._connection_slots = threading.BoundedSemaphore(32)
        self._active_lock = threading.Lock()
        self._active_sockets: set[socket.socket] = set()

    @property
    def dialed_addresses(self) -> tuple[str, ...]:
        with self._stats_lock:
            return tuple(self._dialed_addresses)

    @property
    def accepted_connections(self) -> int:
        with self._stats_lock:
            return self._accepted_connections

    @property
    def rejected_requests(self) -> int:
        with self._stats_lock:
            return self._rejected_requests

    def start(self) -> None:
        if self._server is not None:
            raise RuntimeError("proxy is already running")
        owner = self

        class Handler(socketserver.BaseRequestHandler):
            def handle(self):
                owner._handle_client(self.request)

        class Server(socketserver.ThreadingTCPServer):
            address_family = socket.AF_INET6 if ipaddress.ip_address(owner.bind_address).version == 6 else socket.AF_INET
            request_queue_size = 32
            allow_reuse_address = False
            daemon_threads = True
            block_on_close = True

            def process_request(self, request, client_address):
                if not owner._connection_slots.acquire(blocking=False):
                    owner._respond(request, 503, "Proxy Capacity Exhausted")
                    self.shutdown_request(request)
                    return
                try:
                    super().process_request(request, client_address)
                except Exception:
                    owner._connection_slots.release()
                    raise

            def process_request_thread(self, request, client_address):
                try:
                    super().process_request_thread(request, client_address)
                finally:
                    owner._connection_slots.release()

        server = Server((self.bind_address, self.port), Handler)
        self._server = server
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.1}, daemon=True)
        self._thread = thread
        thread.start()

    def _handle_client(self, client: socket.socket) -> None:
        upstream = None
        tunnel_established = False
        with self._active_lock:
            self._active_sockets.add(client)
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
                with self._stats_lock:
                    self._rejected_requests += 1
                self._respond(client, 403, "Forbidden")
                return
            host, port_text = authority.rsplit(":", 1)
            try:
                normalized = _canonical_host(host)
                port = int(port_text)
            except (ProxyPolicyError, ValueError):
                with self._stats_lock:
                    self._rejected_requests += 1
                self._respond(client, 403, "Forbidden")
                return
            if normalized not in self.allowed_hosts or port != self.allowed_port:
                with self._stats_lock:
                    self._rejected_requests += 1
                self._respond(client, 403, "Forbidden")
                return

            pinned = resolve_and_pin(normalized, port, resolver=self.resolver)
            last_error = None
            for address in pinned.addresses:
                try:
                    upstream = connect_pinned(pinned, address, timeout=self.timeout)
                    with self._stats_lock:
                        self._dialed_addresses.append(address)
                    with self._active_lock:
                        self._active_sockets.add(upstream)
                    break
                except (OSError, PinnedEgressError) as exc:
                    last_error = exc
            if upstream is None:
                raise ProxyPolicyError("no pinned destination was reachable") from last_error

            client.sendall(b"HTTP/1.1 200 Connection Established\r\nProxy-Agent: APAA-Pinned-Proxy\r\n\r\n")
            tunnel_established = True
            sni, client_hello = _read_client_hello(client, remainder)
            if sni != normalized:
                with self._stats_lock:
                    self._rejected_requests += 1
                raise ProxyPolicyError("TLS SNI does not match the approved CONNECT hostname")
            upstream.sendall(client_hello)
            with self._stats_lock:
                self._accepted_connections += 1
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
            if not tunnel_established:
                try:
                    self._respond(client, 502, "Bad Gateway")
                except OSError:
                    pass
        finally:
            if upstream is not None:
                upstream.close()
                with self._active_lock:
                    self._active_sockets.discard(upstream)
            client.close()
            with self._active_lock:
                self._active_sockets.discard(client)

    @staticmethod
    def _respond(client: socket.socket, code: int, reason: str) -> None:
        client.sendall(
            f"HTTP/1.1 {code} {reason}\r\nConnection: close\r\nContent-Length: 0\r\n\r\n".encode("ascii")
        )

    def close(self) -> None:
        server, thread = self._server, self._thread
        self._server = self._thread = None
        shutdown_thread = None
        if server is not None:
            # Calling shutdown directly can race with serve_forever startup.
            shutdown_thread = threading.Thread(target=server.shutdown, daemon=True)
            shutdown_thread.start()
            shutdown_thread.join(timeout=3)
        if thread is not None:
            thread.join(timeout=3)
        with self._active_lock:
            active_sockets = tuple(self._active_sockets)
        for active in active_sockets:
            try:
                active.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                active.close()
            except OSError:
                pass
        if server is not None:
            server.server_close()
        if ((shutdown_thread is not None and shutdown_thread.is_alive())
                or (thread is not None and thread.is_alive())):
            raise RuntimeError("proxy listener or shutdown thread did not stop")
