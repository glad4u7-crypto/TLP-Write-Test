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
    b"Host: attacker.example:443\\r\\n",
    b"Host: example.com:443\\r\\nHost: example.com:443\\r\\n",
    b"Proxy-Authorization: Basic dXNlcjpwYXNz\\r\\n",
    b"Content-Length: 0\\r\\n",
    b"Transfer-Encoding: chunked\\r\\n",
    b"Host example.com:443\\r\\n",
])
def test_parse_connect_request_rejects_ambiguous_or_unneeded_headers(headers):
    raw = b"CONNECT example.com:443 HTTP/1.1\\r\\n" + headers + b"\\r\\n"
    with pytest.raises(ProxyRequestError):
        parse_connect_request(raw)


def test_parse_connect_request_accepts_only_matching_host_header():
    request = parse_connect_request(
        b"CONNECT example.com:443 HTTP/1.1\\r\\nHost: example.com:443\\r\\n\\r\\n"
    )
    assert request.hostname == "example.com"
    assert request.port == 443
