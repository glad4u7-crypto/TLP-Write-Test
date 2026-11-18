import pytest

from core.browser_navigation import NavigationPolicy
from core.egress_policy import (
    EgressAuthorizationError,
    EgressDestinationAuthorizer,
    validate_connector_result,
)


PUBLIC = "93.184.216.34"


def make_policy(resolver=None, hosts=("example.com",)):
    return NavigationPolicy(
        allowed_hosts=frozenset(hosts),
        resolver=resolver or (lambda host: (PUBLIC,)),
    )


def test_authorize_returns_exact_pinned_public_address_and_default_https_port():
    authorizer = EgressDestinationAuthorizer(make_policy())

    target = authorizer.authorize("https://example.com/path")

    assert target.hostname == "example.com"
    assert target.port == 443
    assert target.scheme == "https"
    assert target.pinned_addresses == (PUBLIC,)


def test_authorize_resolves_hostname_exactly_once():
    calls = []

    def resolver(host):
        calls.append(host)
        return (PUBLIC,)

    EgressDestinationAuthorizer(make_policy(resolver)).authorize(
        "https://example.com/"
    )

    assert calls == ["example.com"]


def test_authorize_rejects_private_or_mixed_dns_answers():
    authorizer = EgressDestinationAuthorizer(
        make_policy(lambda host: (PUBLIC, "10.0.0.7"))
    )

    with pytest.raises(EgressAuthorizationError, match="Non-public"):
        authorizer.authorize("https://example.com/")


@pytest.mark.parametrize("url", [
    "http://127.0.0.1/",
    "https://evil.test/",
    "javascript:alert(1)",
    "https://user:pass@example.com/",
    "https://example.com:99999/",
    "file:///etc/passwd",
])
def test_authorize_rejects_unsafe_urls(url):
    authorizer = EgressDestinationAuthorizer(make_policy())

    with pytest.raises(EgressAuthorizationError):
        authorizer.authorize(url)


def test_authorize_supports_explicit_allowlisted_http_only():
    policy = NavigationPolicy(
        allowed_hosts=frozenset({"example.com"}),
        allowed_schemes=frozenset({"http", "https"}),
        resolver=lambda host: (PUBLIC,),
    )

    target = EgressDestinationAuthorizer(policy).authorize("http://example.com/")

    assert target.scheme == "http"
    assert target.port == 80


def test_connector_result_must_match_one_of_the_pinned_addresses():
    target = EgressDestinationAuthorizer(make_policy()).authorize(
        "https://example.com/"
    )

    assert validate_connector_result(target, PUBLIC) == PUBLIC
    with pytest.raises(EgressAuthorizationError, match="escaped"):
        validate_connector_result(target, "1.1.1.1")


def test_public_ip_literal_requires_explicit_allowlist():
    authorizer = EgressDestinationAuthorizer(make_policy())

    with pytest.raises(EgressAuthorizationError):
        authorizer.authorize("https://1.1.1.1/")

    allowed = EgressDestinationAuthorizer(make_policy(hosts=("1.1.1.1",)))
    assert allowed.authorize("https://1.1.1.1/").pinned_addresses == ("1.1.1.1",)
