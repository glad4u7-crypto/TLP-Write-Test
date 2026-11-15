import pytest

from core.browser_isolation import IsolationPolicyError, validate_worker_profile
from core.browser_egress import EgressPolicyError, validate_proxy_connect


def safe_profile(**overrides):
    value = {
        "schema_version": 1,
        "uid": 10001,
        "gid": 10001,
        "privileged": False,
        "read_only_root": True,
        "no_new_privileges": True,
        "capabilities_drop": ["ALL"],
        "host_network": False,
        "host_pid": False,
        "host_ipc": False,
        "host_mounts": [],
        "secret_mounts": [],
        "writable_mounts": ["/tmp/job"],
        "browser_profile_persistence": False,
        "cdp_exposed": False,
        "direct_egress": False,
        "proxy_only_egress": True,
        "dns_via_proxy_only": True,
        "egress_proxy": "http://egress-proxy.internal:3128",
        "memory_limit_bytes": 512 * 1024 * 1024,
        "cpu_limit_millis": 1000,
        "pids_limit": 64,
        "job_timeout_seconds": 30,
    }
    value.update(overrides)
    return value


def test_accepts_hardened_worker_profile():
    result = validate_worker_profile(safe_profile())
    assert result.uid == 10001
    assert result.gid == 10001
    assert result.egress_proxy == "http://egress-proxy.internal:3128"
    assert result.writable_mounts == ("/tmp/job",)


def test_rejects_unknown_or_missing_profile_fields():
    with pytest.raises(IsolationPolicyError):
        validate_worker_profile(safe_profile(extra=True))
    missing = safe_profile()
    del missing["uid"]
    with pytest.raises(IsolationPolicyError):
        validate_worker_profile(missing)


@pytest.mark.parametrize("field", [
    "privileged", "host_network", "host_pid", "host_ipc",
    "browser_profile_persistence", "cdp_exposed", "direct_egress",
])
def test_rejects_privileged_or_host_access(field):
    with pytest.raises(IsolationPolicyError):
        validate_worker_profile(safe_profile(**{field: True}))


@pytest.mark.parametrize("field", [
    "read_only_root", "no_new_privileges", "proxy_only_egress", "dns_via_proxy_only",
])
def test_rejects_missing_required_hardening(field):
    with pytest.raises(IsolationPolicyError):
        validate_worker_profile(safe_profile(**{field: False}))


@pytest.mark.parametrize("field", ["host_mounts", "secret_mounts"])
def test_rejects_host_or_secret_mounts(field):
    with pytest.raises(IsolationPolicyError):
        validate_worker_profile(safe_profile(**{field: ["/host:/host"]}))


def test_rejects_capability_not_dropped():
    with pytest.raises(IsolationPolicyError):
        validate_worker_profile(safe_profile(capabilities_drop=["NET_ADMIN"]))


@pytest.mark.parametrize("mounts", [
    ["/home/user"], ["/etc"], ["/tmp/job", "/tmp/job"], ["relative/path"],
])
def test_rejects_non_ephemeral_or_duplicate_writable_mounts(mounts):
    with pytest.raises(IsolationPolicyError):
        validate_worker_profile(safe_profile(writable_mounts=mounts))


@pytest.mark.parametrize("proxy", [
    "", "https://egress-proxy:3128", "http://user:pass@egress-proxy:3128",
    "http://egress-proxy", "http://egress-proxy:99999",
    "http://egress-proxy.internal:3128/path", "http://127.0.0.1:3128",
])
def test_rejects_invalid_proxy_endpoint(proxy):
    with pytest.raises(IsolationPolicyError):
        validate_worker_profile(safe_profile(egress_proxy=proxy))


@pytest.mark.parametrize("field,value", [
    ("memory_limit_bytes", 1), ("memory_limit_bytes", 3 * 1024 * 1024 * 1024),
    ("cpu_limit_millis", 0), ("cpu_limit_millis", 5000),
    ("pids_limit", 1), ("pids_limit", 1000),
    ("job_timeout_seconds", 0), ("job_timeout_seconds", 61),
    ("uid", 0), ("gid", 0),
])
def test_rejects_unbounded_resources_or_root_identity(field, value):
    with pytest.raises(IsolationPolicyError):
        validate_worker_profile(safe_profile(**{field: value}))


def test_egress_policy_returns_only_validated_public_addresses_for_exact_origin():
    result = validate_proxy_connect(
        "https://example.com/docs",
        ["https://example.com"],
        ["93.184.216.34", "93.184.216.35"],
    )
    assert result.hostname == "example.com"
    assert result.port == 443
    assert result.origin == "https://example.com"
    assert result.validated_addresses == ("93.184.216.34", "93.184.216.35")
    assert result.tls_server_name == "example.com"


@pytest.mark.parametrize("url,addresses", [
    ("https://evil.example/", ["93.184.216.34"]),
    ("https://example.com:8443/", ["93.184.216.34"]),
    ("http://example.com/", ["93.184.216.34"]),
    ("https://example.com/", ["10.0.0.1"]),
    ("https://example.com/", ["93.184.216.34", "169.254.169.254"]),
    ("https://example.com/", []),
])
def test_egress_policy_rejects_unapproved_or_unsafe_connects(url, addresses):
    with pytest.raises(EgressPolicyError):
        validate_proxy_connect(url, ["https://example.com"], addresses)


def test_egress_policy_does_not_resolve_dns_or_open_sockets(monkeypatch):
    import socket

    def forbidden(*_args, **_kwargs):
        raise AssertionError("policy must not open sockets or perform DNS")

    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    result = validate_proxy_connect(
        "https://example.com/", ["https://example.com"], ["93.184.216.34"]
    )
    assert result.validated_addresses == ("93.184.216.34",)
