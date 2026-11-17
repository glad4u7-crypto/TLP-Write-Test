from __future__ import annotations

import pytest

from core.pinned_connect_proxy import PinnedConnectProxy, ProxyPolicyError, _canonical_host


def test_proxy_canonicalizes_exact_idna_hostname():
    assert _canonical_host("example.com") == "example.com"
    assert _canonical_host("bücher.example") == "xn--bcher-kva.example"


@pytest.mark.parametrize("host", [
    "", "example.com.", "example.com:443", "user@example.com",
    "127.0.0.1", "[::1]", "example.com/path", "example.com%00",
])
def test_proxy_rejects_non_hostname_authorities(host):
    with pytest.raises(ProxyPolicyError):
        _canonical_host(host)


def test_proxy_requires_dedicated_non_loopback_veth_bind():
    with pytest.raises(ValueError):
        PinnedConnectProxy("127.0.0.1", 3128, allowed_hosts=["example.com"])


def test_proxy_restricts_to_https_port_443_and_exact_host():
    with pytest.raises(ValueError):
        PinnedConnectProxy("198.18.0.1", 3128, allowed_hosts=["example.com"], allowed_port=80)
    proxy = PinnedConnectProxy("198.18.0.1", 3128, allowed_hosts=["example.com"])
    assert proxy.allowed_hosts == frozenset({"example.com"})
    assert proxy.allowed_port == 443
