import pytest

from core.browser_navigation import NavigationPolicy, NavigationPolicyError


PUBLIC = "93.184.216.34"


def policy(hosts=("example.com",), *, resolver=None, max_redirects=5):
    return NavigationPolicy(
        allowed_hosts=frozenset(hosts),
        resolver=resolver or (lambda host: (PUBLIC,)),
        max_redirects=max_redirects,
    )


def test_allows_allowlisted_https_host_and_subdomain():
    p = policy()
    assert p.validate_url("https://example.com/path?q=1") == "https://example.com/path?q=1"
    assert p.validate_url("https://docs.example.com/") == "https://docs.example.com/"


@pytest.mark.parametrize("url", [
    "javascript:alert(1)",
    "file:///etc/passwd",
    "ftp://example.com/",
    "https://user:pass@example.com/",
    "https://example.com:99999/",
    "https://example.com" + chr(92) + "@evil.test/",
    "https://localhost/",
    "http://127.0.0.1/",
    "http://10.0.0.8/",
    "http://169.254.169.254/latest/meta-data/",
    "http://[::1]/",
    "https://notexample.com/",
])
def test_rejects_unsafe_or_non_allowlisted_urls(url):
    with pytest.raises(NavigationPolicyError):
        policy().validate_url(url)


def test_allowlist_can_disable_subdomains():
    p = NavigationPolicy(
        allowed_hosts=frozenset({"example.com"}),
        allow_subdomains=False,
        resolver=lambda host: (PUBLIC,),
    )
    assert p.validate_url("https://example.com") == "https://example.com"
    with pytest.raises(NavigationPolicyError):
        p.validate_url("https://docs.example.com")


def test_public_ip_literal_requires_explicit_allowlist():
    with pytest.raises(NavigationPolicyError, match="explicit allowlist"):
        policy().validate_url("https://93.184.216.34/")
    p = NavigationPolicy(allowed_hosts=frozenset({"93.184.216.34"}))
    assert p.validate_url("https://93.184.216.34/") == "https://93.184.216.34/"


def test_rejects_hostname_that_resolves_to_private_address():
    p = policy(resolver=lambda host: ("93.184.216.34", "192.168.1.5"))
    with pytest.raises(NavigationPolicyError, match="private"):
        p.validate_url("https://example.com")


def test_rejects_empty_or_failed_dns_resolution():
    with pytest.raises(NavigationPolicyError, match="no address"):
        policy(resolver=lambda host: ()).validate_url("https://example.com")

    def broken(host):
        raise OSError("dns unavailable")

    with pytest.raises(NavigationPolicyError, match="could not be resolved"):
        policy(resolver=broken).validate_url("https://example.com")


def test_redirect_chain_revalidates_every_hop_and_returns_final_url():
    p = policy(hosts=("example.com", "trusted.test"))
    result = p.validate_redirect_chain(
        "https://example.com/start",
        ["https://sub.example.com/next", "https://trusted.test/final"],
    )
    assert result == "https://trusted.test/final"


def test_redirect_chain_blocks_allowlist_escape_private_ip_and_loop():
    p = policy()
    with pytest.raises(NavigationPolicyError, match="allowlist"):
        p.validate_redirect_chain("https://example.com", ["https://evil.test"])
    with pytest.raises(NavigationPolicyError, match="Private"):
        p.validate_redirect_chain("https://example.com", ["http://10.1.2.3"])
    with pytest.raises(NavigationPolicyError, match="loop"):
        p.validate_redirect_chain("https://example.com", ["https://example.com"])


def test_redirect_limit_is_bounded():
    p = policy(max_redirects=1)
    with pytest.raises(NavigationPolicyError, match="limit"):
        p.validate_redirect_chain(
            "https://example.com/a",
            ["https://example.com/b", "https://example.com/c"],
        )


def test_policy_rejects_empty_allowlist_and_invalid_configuration():
    with pytest.raises(ValueError):
        NavigationPolicy(allowed_hosts=frozenset())
    with pytest.raises(ValueError):
        NavigationPolicy(allowed_hosts=frozenset({"example.com"}), max_redirects=11)
