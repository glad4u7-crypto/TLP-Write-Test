import pytest

from core.egress_policy import EgressDestinationAuthorizer, EgressAuthorizationError
from core.browser_navigation import NavigationPolicy
from core.pinned_ip_connector import PinnedIPConnector


PUBLIC4 = "93.184.216.34"
PUBLIC6 = "2606:4700:4700::1111"


class FakeSocket:
    def __init__(self, peer):
        self.peer = (peer, 443)
        self.closed = False

    def getpeername(self):
        return self.peer

    def close(self):
        self.closed = True


def make_target(addresses=(PUBLIC4,)):
    policy = NavigationPolicy(
        allowed_hosts=frozenset({"example.com"}),
        resolver=lambda host: addresses,
    )
    return EgressDestinationAuthorizer(policy).authorize("https://example.com/")


def test_connector_dials_numeric_ipv4_pin_and_verifies_peer():
    calls = []
    sock = FakeSocket(PUBLIC4)

    def dialer(address, port, timeout):
        calls.append((address, port, timeout))
        return sock

    result = PinnedIPConnector(dialer, timeout=2).connect(make_target())

    assert calls == [(PUBLIC4, 443, 2.0)]
    assert result.socket is sock
    assert result.hostname == "example.com"
    assert result.pinned_ip == PUBLIC4


def test_connector_supports_ipv6_pin():
    sock = FakeSocket(PUBLIC6)
    result = PinnedIPConnector(lambda address, port, timeout: sock).connect(
        make_target((PUBLIC6,))
    )
    assert result.pinned_ip == PUBLIC6


def test_connector_never_resolves_hostname_again_after_authorization():
    resolutions = []

    def resolver(host):
        resolutions.append(host)
        return (PUBLIC4,)

    policy = NavigationPolicy(
        allowed_hosts=frozenset({"example.com"}),
        resolver=resolver,
    )
    target = EgressDestinationAuthorizer(policy).authorize("https://example.com/")
    PinnedIPConnector(lambda address, port, timeout: FakeSocket(address)).connect(target)

    assert resolutions == ["example.com"]


def test_connector_rejects_peer_ip_mismatch_and_closes_socket():
    sock = FakeSocket("1.1.1.1")
    connector = PinnedIPConnector(lambda address, port, timeout: sock)

    with pytest.raises(EgressAuthorizationError, match="does not match"):
        connector.connect(make_target())
    assert sock.closed


def test_connector_fails_closed_after_connection_errors():
    calls = []

    def failing_dialer(address, port, timeout):
        calls.append(address)
        raise OSError("simulated connect failure")

    with pytest.raises(EgressAuthorizationError, match="attempts failed"):
        PinnedIPConnector(failing_dialer).connect(make_target((PUBLIC4, PUBLIC6)))
    assert calls == [PUBLIC4, PUBLIC6]


def test_connector_closes_socket_when_peer_cannot_be_read():
    class BrokenSocket(FakeSocket):
        def getpeername(self):
            raise OSError("peer unavailable")

    sock = BrokenSocket(PUBLIC4)
    with pytest.raises(EgressAuthorizationError, match="peer could not be verified"):
        PinnedIPConnector(lambda address, port, timeout: sock).connect(make_target())
    assert sock.closed


def test_connector_rejects_forged_private_pin_before_dial():
    from core.egress_policy import EgressTarget

    target = EgressTarget("example.com", 443, "https", ("10.0.0.2",))
    called = []
    with pytest.raises(EgressAuthorizationError, match="non-public"):
        PinnedIPConnector(lambda *args: called.append(args)).connect(target)
    assert called == []


def test_connector_rejects_empty_pin_set():
    from core.egress_policy import EgressTarget

    target = EgressTarget("example.com", 443, "https", ())
    with pytest.raises(EgressAuthorizationError, match="no IP pins"):
        PinnedIPConnector().connect(target)
