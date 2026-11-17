from __future__ import annotations

import pytest

from core.pinned_connect_proxy import PinnedConnectProxy, ProxyPolicyError, _canonical_host


def test_proxy_canonicalizes_exact_idna_hostname():
    assert _canonical_host("example.com") == "example.com"
    assert _canonical_host("bücher.example") == "xn--bcher-kva.example"


@pytest.mark.parametrize("host", [
    "", "example.com.", "example.com:443", "user@example.com", "127.0.0.1",
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


def _client_hello(host: str | None = "example.com") -> bytes:
    extensions = b""
    if host is not None:
        name = host.encode("ascii")
        entry = b"\x00" + len(name).to_bytes(2, "big") + name
        names = len(entry).to_bytes(2, "big") + entry
        extensions = b"\x00\x00" + len(names).to_bytes(2, "big") + names
    body = (
        b"\x03\x03" + b"\x01" * 32 + b"\x00"
        + b"\x00\x02\x13\x01" + b"\x01\x00"
        + len(extensions).to_bytes(2, "big") + extensions
    )
    return b"\x01" + len(body).to_bytes(3, "big") + body


def _tls_record(payload: bytes) -> bytes:
    return b"\x16\x03\x03" + len(payload).to_bytes(2, "big") + payload


def test_tls_client_hello_sni_is_parsed_and_canonicalized():
    from core.pinned_connect_proxy import _extract_client_hello_sni

    assert _extract_client_hello_sni(_client_hello("example.com")) == "example.com"
    assert _extract_client_hello_sni(_client_hello("bücher.example".encode("idna").decode("ascii"))) == "xn--bcher-kva.example"


def test_tls_client_hello_without_sni_is_rejected():
    from core.pinned_connect_proxy import _extract_client_hello_sni

    with pytest.raises(ProxyPolicyError, match="exactly one host SNI"):
        _extract_client_hello_sni(_client_hello(None))


def test_tls_client_hello_duplicate_sni_is_rejected():
    from core.pinned_connect_proxy import _extract_client_hello_sni

    hello = _client_hello("example.com")
    # A duplicate SNI extension is not a valid single-host authority.
    body = hello[4:]
    extension_length_offset = 2 + 32 + 1 + 2 + 2 + 1 + 1
    extensions_length = int.from_bytes(body[extension_length_offset:extension_length_offset + 2], "big")
    extension = body[extension_length_offset + 2:extension_length_offset + 2 + extensions_length]
    duplicate_extensions = extension + extension
    rebuilt_body = (
        body[:extension_length_offset]
        + len(duplicate_extensions).to_bytes(2, "big")
        + duplicate_extensions
    )
    duplicate = b"\x01" + len(rebuilt_body).to_bytes(3, "big") + rebuilt_body
    with pytest.raises(ProxyPolicyError, match="exactly one host SNI"):
        _extract_client_hello_sni(duplicate)


def test_tls_client_hello_reader_handles_fragmented_records():
    import socket
    from core.pinned_connect_proxy import _read_client_hello

    handshake = _client_hello("example.com")
    split = len(handshake) // 2
    wire = _tls_record(handshake[:split]) + _tls_record(handshake[split:])
    receiver, sender = socket.socketpair()
    try:
        sender.sendall(wire)
        sni, forwarded = _read_client_hello(receiver)
        assert sni == "example.com"
        assert forwarded == wire
    finally:
        receiver.close()
        sender.close()


def test_tls_client_hello_reader_rejects_non_handshake_records():
    import socket
    from core.pinned_connect_proxy import _read_client_hello

    receiver, sender = socket.socketpair()
    try:
        sender.sendall(b"\x17\x03\x03\x00\x01x")
        with pytest.raises(ProxyPolicyError, match="valid handshake record"):
            _read_client_hello(receiver)
    finally:
        receiver.close()
        sender.close()
