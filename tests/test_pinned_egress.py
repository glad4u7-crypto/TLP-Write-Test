from __future__ import annotations

import socket

import pytest

from core.pinned_egress import PinnedEgressError, connect_pinned, resolve_and_pin


class FakeSocket:
    def __init__(self, peer):
        self.peer = peer
        self.target = None
        self.closed = False
        self.timeout = None

    def settimeout(self, value):
        self.timeout = value

    def connect(self, target):
        self.target = target

    def getpeername(self):
        return self.peer

    def close(self):
        self.closed = True


def destination():
    records = [
        (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("8.8.8.8", 443)),
    ]
    return resolve_and_pin("example.com", 443, resolver=lambda *args: records)


def test_connect_pinned_checks_exact_ip_and_port():
    pinned = destination()
    sock = FakeSocket(("8.8.8.8", 443))
    result = connect_pinned(
        pinned, "8.8.8.8", socket_factory=lambda *args: sock,
    )
    assert result is sock
    assert sock.target == ("8.8.8.8", 443)
    assert sock.closed is False


@pytest.mark.parametrize("peer", [
    ("1.1.1.1", 443),
    ("8.8.8.8", 444),
])
def test_connect_pinned_rejects_peer_address_or_port_mismatch(peer):
    pinned = destination()
    sock = FakeSocket(peer)
    with pytest.raises(PinnedEgressError, match="address and port"):
        connect_pinned(
            pinned, "8.8.8.8", socket_factory=lambda *args: sock,
        )
    assert sock.closed is True


def test_connect_pinned_never_accepts_unpinned_dial_target():
    pinned = destination()
    sock = FakeSocket(("8.8.8.8", 443))
    with pytest.raises(PinnedEgressError, match="not part"):
        connect_pinned(
            pinned, "1.1.1.1", socket_factory=lambda *args: sock,
        )
    assert sock.closed is False


def test_resolve_and_pin_rejects_mixed_public_and_private_dns_answers():
    records = [
        (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("8.8.8.8", 443)),
        (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("127.0.0.1", 443)),
    ]
    with pytest.raises(PinnedEgressError):
        resolve_and_pin("example.com", 443, resolver=lambda *args: records)
