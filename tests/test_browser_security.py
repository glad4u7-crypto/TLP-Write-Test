import ipaddress

import pytest

from core.browser_security import (
    BrowserPolicyError,
    canonicalize_https_url,
    validate_browser_job,
    validate_destination,
    validate_dns_answers,
    validate_redirect,
)


def test_canonicalizes_https_host_port_path_and_fragment():
    result = canonicalize_https_url("HTTPS://ExAmPlE.com:443/docs?q=1#section")
    assert result.url == "https://example.com/docs?q=1"
    assert result.origin == "https://example.com"
    assert result.hostname == "example.com"
    assert result.port == 443


def test_canonicalizes_idn_to_ascii():
    result = canonicalize_https_url("https://bücher.example/guide")
    assert result.hostname == "xn--bcher-kva.example"
    assert result.origin == "https://xn--bcher-kva.example"


@pytest.mark.parametrize("url", [
    "http://example.com", "file:///etc/passwd", "javascript:alert(1)",
    "data:text/plain,hello", "//example.com/path", "https://user@example.com",
    "https://user:pass@example.com", "https://example.com\\@evil.example",
    "https://localhost", "https://127.0.0.1", "https://10.0.0.1",
    "https://169.254.169.254/latest/meta-data", "https://192.168.1.1",
    "https://[::1]", "https://[fc00::1]", "https://[fe80::1]",
    "https://127.1", "https://0177.0.0.1", "https://0x7f000001", "https://0x7f.0.0.1",
    "https://example.com:99999", "https://example.com:bad", "https://example.com:0", "https://example.com:",
    "https://singlelabel", "https://exa mple.com", " https://example.com",
    "https://example.com ", "https://example.com\\path",
])
def test_rejects_unsafe_or_malformed_urls(url):
    with pytest.raises(BrowserPolicyError):
        canonicalize_https_url(url)


@pytest.mark.parametrize("url", [
    "https://example.com", "https://example.com:443/path",
    "https://sub.example.com", "https://example.com.evil.test",
    "https://evil-example.com",
])
def test_exact_origin_allowlist_never_uses_suffix_matching(url):
    allowed = ["https://example.com"]
    if url in ("https://example.com", "https://example.com:443/path"):
        validate_destination(url, allowed)
    else:
        with pytest.raises(BrowserPolicyError):
            validate_destination(url, allowed)


def test_non_default_port_is_part_of_exact_origin():
    with pytest.raises(BrowserPolicyError):
        validate_destination("https://example.com:8443/", ["https://example.com"])


def test_allowlist_rejects_path_query_and_fragment_entries():
    for origin in ("https://example.com/path", "https://example.com/?q=1", "https://example.com/#fragment"):
        with pytest.raises(BrowserPolicyError):
            validate_destination("https://example.com/", [origin])


def test_mixed_dns_answers_fail_closed():
    with pytest.raises(BrowserPolicyError):
        validate_destination(
            "https://example.com",
            ["https://example.com"],
            resolver=lambda host: ["93.184.216.34", "10.0.0.2"],
        )


def test_dns_answers_are_normalized_and_deduplicated():
    assert validate_dns_answers(
        "example.com", ["93.184.216.34", "93.184.216.34"]
    ) == ("93.184.216.34",)


@pytest.mark.parametrize("answer", [
    "127.0.0.1", "10.1.2.3", "172.16.0.1", "192.168.1.1",
    "169.254.169.254", "::1", "fc00::1", "fe80::1", "224.0.0.1",
    "0.0.0.0", "255.255.255.255", "not-an-ip",
])
def test_dns_answers_reject_private_reserved_and_invalid_values(answer):
    with pytest.raises(BrowserPolicyError):
        validate_dns_answers("example.com", [answer])


def test_empty_dns_answers_fail_closed():
    with pytest.raises(BrowserPolicyError):
        validate_dns_answers("example.com", [])


def test_dns_resolver_failure_is_fail_closed():
    def broken(_host):
        raise OSError("fixture failure")

    with pytest.raises(BrowserPolicyError):
        validate_destination("https://example.com", ["https://example.com"], resolver=broken)


def test_ip_literal_does_not_need_dns_resolver():
    result = validate_destination("https://93.184.216.34", ["https://93.184.216.34"])
    assert result.hostname == "93.184.216.34"


def test_redirect_relative_location_is_revalidated():
    result = validate_redirect(
        "https://example.com/docs/start",
        "../help",
        ["https://example.com"],
    )
    assert result.url == "https://example.com/help"


@pytest.mark.parametrize("location", [
    "https://evil.example/steal", "//evil.example/steal",
    "http://example.com/insecure", "file:///etc/passwd",
    "https://127.0.0.1/admin",
])
def test_redirect_to_unapproved_or_unsafe_destination_is_blocked(location):
    with pytest.raises(BrowserPolicyError):
        validate_redirect(
            "https://example.com/start", location, ["https://example.com"]
        )


def valid_job(**overrides):
    job = {
        "job_id": "job_12345678",
        "url": "https://example.com/docs",
        "allowed_origins": ["https://example.com"],
        "action": "read_visible_text",
        "expires_at": 1300,
        "max_response_bytes": 100_000,
        "max_runtime_seconds": 30,
    }
    job.update(overrides)
    return job


def test_valid_read_only_job_is_parsed_into_immutable_contract():
    job = validate_browser_job(valid_job(), now=1000)
    assert job.job_id == "job_12345678"
    assert job.url == "https://example.com/docs"
    assert job.allowed_origins == ("https://example.com",)
    assert job.action == "read_visible_text"
    with pytest.raises((AttributeError, TypeError)):
        job.action = "click"


def test_job_rejects_unknown_or_missing_fields():
    unknown = valid_job(debug=True)
    with pytest.raises(BrowserPolicyError):
        validate_browser_job(unknown, now=1000)
    missing = valid_job()
    del missing["expires_at"]
    with pytest.raises(BrowserPolicyError):
        validate_browser_job(missing, now=1000)


@pytest.mark.parametrize("action", [
    "click", "fill", "type", "submit", "evaluate_javascript", "download",
    "upload", "clipboard_write", "run_shell", "payment", "place_order",
])
def test_job_rejects_mutating_or_unknown_action_types(action):
    with pytest.raises(BrowserPolicyError):
        validate_browser_job(valid_job(action=action), now=1000)


@pytest.mark.parametrize("expiry", [999, 1000, 1301, True, "1300"])
def test_job_expiry_must_be_integer_and_within_five_minutes(expiry):
    with pytest.raises(BrowserPolicyError):
        validate_browser_job(valid_job(expires_at=expiry), now=1000)


@pytest.mark.parametrize("value", [0, -1, True, 2_000_001, "1000"])
def test_job_response_limit_is_strictly_bounded(value):
    with pytest.raises(BrowserPolicyError):
        validate_browser_job(valid_job(max_response_bytes=value), now=1000)


@pytest.mark.parametrize("value", [0, -1, True, 61, "30"])
def test_job_runtime_limit_is_strictly_bounded(value):
    with pytest.raises(BrowserPolicyError):
        validate_browser_job(valid_job(max_runtime_seconds=value), now=1000)


def test_job_rejects_duplicate_origins_and_cross_origin_url():
    with pytest.raises(BrowserPolicyError):
        validate_browser_job(
            valid_job(allowed_origins=["https://example.com", "https://example.com"]),
            now=1000,
        )
    with pytest.raises(BrowserPolicyError):
        validate_browser_job(
            valid_job(url="https://evil.example/page"),
            now=1000,
        )


def test_job_rejects_non_mapping_and_invalid_job_id():
    with pytest.raises(BrowserPolicyError):
        validate_browser_job(["not", "a", "mapping"], now=1000)
    with pytest.raises(BrowserPolicyError):
        validate_browser_job(valid_job(job_id="short"), now=1000)


def test_no_network_or_dns_lookup_occurs_without_injected_resolver(monkeypatch):
    import socket

    def forbidden(*_args, **_kwargs):
        raise AssertionError("network/DNS must never be called by policy validation")

    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    assert validate_browser_job(valid_job(), now=1000).url == "https://example.com/docs"
