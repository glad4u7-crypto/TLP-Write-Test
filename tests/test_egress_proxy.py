import pytest

from core.browser_navigation import NavigationPolicy
from core.egress_policy import EgressDestinationAuthorizer
from core.pinned_ip_connector import PinnedIPConnector
from core.egress_proxy import (
    EgressConnectProxy,
    ProxyRequestError,
    parse_connect_request,
)


PUBLIC = "93.184.216.34"


@pytest.mark.parametrize("raw,host,port", [
    (b"CONNECT example.com:443 HTTP/1.1\r\nHost: example.com:443\r\n\r\n", "example.com", 443),
    (b"CONNECT [2606:4700:4700::1111]:443 HTTP/1.1\r\nHost: [2606:4700:4700::1111]:443\r\n\r\n", "2606:4700:4700::1111", 443),
])
def test_parse_connect_request_accepts_hostname_and_ipv6_authority(raw, host, port):
    request = parse_connect_request(raw)
    assert request.hostname == host
    assert request.port == port


@pytest.mark.parametrize("raw", [
    b"GET https://example.com/ HTTP/1.1\r\n\r\n",
    b"CONNECT example.com HTTP/1.1\r\n\r\n",
    b"CONNECT example.com:8443 HTTP/1.1\r\n\r\n",
    b"CONNECT user@example.com:443 HTTP/1.1\r\n\r\n",
    b"CONNECT example.com:443/path HTTP/1.1\r\n\r\n",
    b"CONNECT example.com:99999 HTTP/1.1\r\n\r\n",
    b"CONNECT example.com:443 HTTP/1.0\r\n\r\n",
    b"CONNECT example.com:443 HTTP/1.1\r\n\r\nEXTRA",
])
def test_parse_connect_request_rejects_unsupported_or_malformed_requests(raw):
    with pytest.raises(ProxyRequestError):
        parse_connect_request(raw)


def test_parse_connect_request_enforces_explicit_custom_port_policy():
    raw = b"CONNECT example.com:8443 HTTP/1.1\r\n\r\n"
    assert parse_connect_request(raw, allowed_ports=frozenset({8443})).port == 8443


def test_proxy_constructor_refuses_non_loopback_bind():
    policy = NavigationPolicy(allowed_hosts=frozenset({"example.com"}), resolver=lambda host: (PUBLIC,))
    authorizer = EgressDestinationAuthorizer(policy)
    connector = PinnedIPConnector(lambda address, port, timeout: None)
    with pytest.raises(ValueError, match="loopback"):
        EgressConnectProxy(authorizer, connector, bind_host="0.0.0.0")


def test_proxy_constructor_accepts_loopback_but_does_not_start_server():
    policy = NavigationPolicy(allowed_hosts=frozenset({"example.com"}), resolver=lambda host: (PUBLIC,))
    proxy = EgressConnectProxy(
        EgressDestinationAuthorizer(policy),
        PinnedIPConnector(lambda address, port, timeout: None),
    )
    assert proxy.bind_host == "127.0.0.1"
    assert proxy.bind_port == 0


@pytest.mark.parametrize("headers", [
    b"Host: attacker.example:443\r\n",
    b"Host: example.com:443\r\nHost: example.com:443\r\n",
    b"Proxy-Authorization: Basic dXNlcjpwYXNz\r\n",
    b"Content-Length: 0\r\n",
    b"Transfer-Encoding: chunked\r\n",
    b"Host example.com:443\r\n",
])
def test_parse_connect_request_rejects_ambiguous_or_unneeded_headers(headers):
    raw = b"CONNECT example.com:443 HTTP/1.1\r\n" + headers + b"\r\n"
    with pytest.raises(ProxyRequestError):
        parse_connect_request(raw)


def test_parse_connect_request_accepts_only_matching_host_header():
    request = parse_connect_request(
        b"CONNECT example.com:443 HTTP/1.1\r\nHost: example.com:443\r\n\r\n"
    )
    assert request.hostname == "example.com"
    assert request.port == 443


def test_proxy_denies_non_allowlisted_host_before_opening_upstream_socket():
    """An unauthorized CONNECT target must fail before the connector is called."""
    import socket
    import threading

    policy = NavigationPolicy(
        allowed_hosts=frozenset({"example.com"}),
        resolver=lambda host: (PUBLIC,),
    )
    authorizer = EgressDestinationAuthorizer(policy)
    dial_attempts = []

    def dialer(address, port, timeout):
        dial_attempts.append((address, port))
        raise AssertionError("connector must not run for a denied hostname")

    proxy = EgressConnectProxy(authorizer, PinnedIPConnector(dialer))
    client, server_side = socket.socketpair()
    worker = threading.Thread(target=proxy.handle_client, args=(server_side,), daemon=True)
    worker.start()
    try:
        client.sendall(
            b"CONNECT not-allowed.example:443 HTTP/1.1\r\n"
            b"Host: not-allowed.example:443\r\n\r\n"
        )
        response = client.recv(1024)
        assert response.startswith(b"HTTP/1.1 502")
        assert dial_attempts == []
    finally:
        client.close()
        worker.join(timeout=2)
        assert not worker.is_alive()


def test_proxy_server_serves_loopback_and_fails_closed_for_denied_connect():
    """Exercise the real TCP server lifecycle without opening an upstream socket."""
    import socket
    import threading

    policy = NavigationPolicy(
        allowed_hosts=frozenset({"example.com"}),
        resolver=lambda host: (PUBLIC,),
    )
    dial_attempts = []

    def dialer(address, port, timeout):
        dial_attempts.append((address, port))
        raise AssertionError("denied destination must never reach the upstream dialer")

    proxy = EgressConnectProxy(
        EgressDestinationAuthorizer(policy),
        PinnedIPConnector(dialer),
    )
    server = proxy.make_server()
    worker = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01})
    worker.start()
    client = None
    try:
        client = socket.create_connection(server.server_address, timeout=2)
        client.settimeout(2)
        client.sendall(
            b"CONNECT denied.example:443 HTTP/1.1\r\n"
            b"Host: denied.example:443\r\n\r\n"
        )
        response = client.recv(1024)
        assert response.startswith(b"HTTP/1.1 502")
        assert dial_attempts == []
    finally:
        if client is not None:
            client.close()
        server.shutdown()
        server.server_close()
        worker.join(timeout=2)
    assert not worker.is_alive()


def test_proxy_establishes_authorized_pinned_tunnel_and_relays_bytes():
    """A permitted CONNECT must dial only the authorized IP and relay opaque bytes."""
    import socket
    import threading

    class ReportedPeerSocket:
        def __init__(self, sock):
            self.sock = sock

        def getpeername(self):
            return (PUBLIC, 443)

        def settimeout(self, value):
            self.sock.settimeout(value)

        def recv(self, size):
            return self.sock.recv(size)

        def sendall(self, payload):
            return self.sock.sendall(payload)

        def close(self):
            self.sock.close()

    policy = NavigationPolicy(
        allowed_hosts=frozenset({"example.com"}),
        resolver=lambda host: (PUBLIC,),
    )
    upstream_proxy, upstream_test = socket.socketpair()
    dialed = []

    def dialer(address, port, timeout):
        dialed.append((address, port))
        return ReportedPeerSocket(upstream_proxy)

    proxy = EgressConnectProxy(
        EgressDestinationAuthorizer(policy),
        PinnedIPConnector(dialer),
    )
    client, server_side = socket.socketpair()
    worker = threading.Thread(target=proxy.handle_client, args=(server_side,), daemon=True)
    worker.start()
    try:
        client.settimeout(2)
        upstream_test.settimeout(2)
        client.sendall(
            b"CONNECT example.com:443 HTTP/1.1\r\n"
            b"Host: example.com:443\r\n\r\n"
        )
        response = client.recv(1024)
        assert response.startswith(b"HTTP/1.1 200 Connection Established")
        assert dialed == [(PUBLIC, 443)]

        client.sendall(b"client-tls-record")
        assert upstream_test.recv(1024) == b"client-tls-record"
        upstream_test.sendall(b"server-tls-record")
        assert client.recv(1024) == b"server-tls-record"
    finally:
        client.close()
        upstream_test.close()
        worker.join(timeout=2)
    assert not worker.is_alive()


def test_proxy_returns_bad_gateway_when_all_pinned_upstream_dials_fail():
    """A proxy connection failure must return 502, never attempt direct fallback."""
    import socket
    import threading

    policy = NavigationPolicy(
        allowed_hosts=frozenset({"example.com"}),
        resolver=lambda host: (PUBLIC,),
    )
    attempts = []

    def dialer(address, port, timeout):
        attempts.append((address, port))
        raise OSError("simulated upstream outage")

    proxy = EgressConnectProxy(
        EgressDestinationAuthorizer(policy),
        PinnedIPConnector(dialer),
    )
    client, server_side = socket.socketpair()
    worker = threading.Thread(target=proxy.handle_client, args=(server_side,), daemon=True)
    worker.start()
    try:
        client.settimeout(2)
        client.sendall(
            b"CONNECT example.com:443 HTTP/1.1\r\n"
            b"Host: example.com:443\r\n\r\n"
        )
        response = client.recv(1024)
        assert response.startswith(b"HTTP/1.1 502 Bad Gateway")
        assert attempts == [(PUBLIC, 443)]
    finally:
        client.close()
        worker.join(timeout=2)
    assert not worker.is_alive()
