import pytest
from core.browser_navigation import NavigationPolicy, NavigationPolicyError
from core.egress_policy import EgressAuthorizationError, EgressDestinationAuthorizer, EgressTarget
from core.mandatory_proxy import MandatoryProxyConnector, ProxyEndpoint
from core.pinned_ip_connector import PinnedIPConnector

PUBLIC="93.184.216.34"

def test_dns_rebinding_after_authorization_cannot_change_the_pinned_socket_target():
    answers=[(PUBLIC,),("127.0.0.1",)]
    calls=[]
    def resolver(host):
        calls.append(host)
        return answers[min(len(calls)-1,1)]
    policy=NavigationPolicy(frozenset({"example.com"}),resolver=resolver)
    target=EgressDestinationAuthorizer(policy).authorize("https://example.com/")
    dialed=[]
    class Sock:
        def getpeername(self): return (PUBLIC,443)
        def close(self): pass
    PinnedIPConnector(lambda ip,port,timeout:(dialed.append(ip) or Sock())).connect(target)
    assert calls==["example.com"]
    assert dialed==[PUBLIC]

@pytest.mark.parametrize("address",[
    "127.0.0.1","10.0.0.1","169.254.169.254","192.168.1.1",
    "::1","fe80::1","fc00::1","::ffff:127.0.0.1"
])
def test_ssrf_sensitive_resolver_answers_are_denied(address):
    policy=NavigationPolicy(frozenset({"example.com"}),resolver=lambda host:(address,))
    with pytest.raises(NavigationPolicyError):
        policy.validate_url("https://example.com/")

def test_mixed_public_private_a_aaaa_answer_is_denied_as_a_whole():
    policy=NavigationPolicy(frozenset({"example.com"}),resolver=lambda host:(PUBLIC,"10.1.2.3"))
    with pytest.raises(NavigationPolicyError):
        EgressDestinationAuthorizer(policy).authorize("https://example.com/")

def test_redirect_to_loopback_or_metadata_is_denied():
    policy=NavigationPolicy(frozenset({"example.com"}),resolver=lambda host:(PUBLIC,))
    with pytest.raises(NavigationPolicyError):
        policy.validate_redirect_chain("https://example.com/",["http://127.0.0.1/"])
    with pytest.raises(NavigationPolicyError):
        policy.validate_redirect_chain("https://example.com/",["http://169.254.169.254/latest/meta-data/"])

@pytest.mark.parametrize("pin",["127.0.0.1","169.254.169.254","::ffff:127.0.0.1","10.0.0.1"])
def test_proxy_boundary_rejects_forged_private_origin_pins_before_dial(pin):
    proxy=ProxyEndpoint(EgressTarget("proxy.example",443,"https",(PUBLIC,)))
    origin=EgressTarget("internal.example",443,"https",(pin,))
    called=[]
    class Connector:
        def connect(self,target):
            called.append(target)
            raise AssertionError("proxy must not be contacted for invalid origin")
    # TLS contexts are not reached; default verified contexts are safe defaults.
    connector=MandatoryProxyConnector(proxy,connector=Connector())
    with pytest.raises(EgressAuthorizationError):
        connector.connect(origin)
    assert called==[]
