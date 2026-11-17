import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from core.attested_browser_runtime import AttestedBrowserRuntime
from core.browser_nftables import collect_signed_inspector_evidence, _expected_dual_stack_rules
from core.browser_isolation import validate_worker_profile
from core.browser_runtime import build_worker_launch_spec
from core.browser_launcher import (
    BrowserLaunchError,
    BrowserSession,
    create_playwright_worker_start,
    launch_chromium,
)

NOW = 1000
CHALLENGE = "d" * 64
PROXY_IP = "172.20.0.2"
PROXY_IPV6 = "fd00::2"
PROXY_IPS = [PROXY_IP, PROXY_IPV6]
PROXY = "http://egress-proxy.internal:3128"


def make_spec():
    profile = validate_worker_profile({
        "schema_version": 1, "uid": 10001, "gid": 10001,
        "privileged": False, "read_only_root": True, "no_new_privileges": True,
        "capabilities_drop": ["ALL"], "host_network": False, "host_pid": False,
        "host_ipc": False, "host_mounts": [], "secret_mounts": [],
        "writable_mounts": ["/tmp/job"], "browser_profile_persistence": False,
        "cdp_exposed": False, "direct_egress": False, "proxy_only_egress": True,
        "dns_via_proxy_only": True, "egress_proxy": PROXY,
        "memory_limit_bytes": 512 * 1024 * 1024, "cpu_limit_millis": 1000,
        "pids_limit": 64, "job_timeout_seconds": 30,
    })
    return build_worker_launch_spec(profile)




class FakeHost:
    def __init__(self, spec):
        self.runtime = {
            "schema_version": 1, "launch_spec_digest": spec.digest,
            "runtime_id": "runtime:test-001", "worker_id": "worker:test-001",
            "image_digest": "sha256:" + "a" * 64,
            "attestor_id": "inspector:test-001", "evidence_digest": "b" * 64,
            "observed_at": NOW, "state": "created", "process_started": False,
            "runtime_config_verified": True, "host_firewall_verified": True,
            "uid": spec.uid, "gid": spec.gid, "privileged": False,
            "read_only_root": True, "no_new_privileges": True,
            "capabilities_effective": [], "namespaces": list(spec.namespaces),
            "host_mounts": [], "secret_mounts": [],
            "writable_mounts": list(spec.writable_mounts),
            "browser_profile_persistence": False, "cdp_exposed": False,
            "direct_egress": False, "proxy_only_egress": True,
            "dns_via_proxy_only": True, "egress_proxy": spec.egress_proxy,
            "memory_limit_bytes": spec.memory_limit_bytes,
            "cpu_limit_millis": spec.cpu_limit_millis,
            "pids_limit": spec.pids_limit, "job_timeout_seconds": spec.job_timeout_seconds,
            "seccomp_enforced": True, "network_namespace_isolated": True,
            "firewall_default_deny": True,
            "egress_allowed": ["egress-proxy.internal:3128"],
            "direct_dns_egress_blocked": True, "proxy_side_dns_only": True,
        }
        self.namespace = {
            "runtime_id": "runtime:test-001", "worker_id": "worker:test-001",
            "inode": 4026533001, "interface": "eth0",
        }
        expected_rules = _expected_dual_stack_rules(tuple(sorted(PROXY_IPS)), 3128)
        self.rules = {"nftables": [
            {"metainfo": {"version": "1.0.9", "release_name": "test"}},
            {"table": {"family": "inet", "name": "apaa"}},
            {"chain": {"family": "inet", "table": "apaa", "name": "input",
                       "type": "filter", "hook": "input", "prio": 0, "policy": "drop"}},
            {"chain": {"family": "inet", "table": "apaa", "name": "output",
                       "type": "filter", "hook": "output", "prio": 0, "policy": "drop"}},
        ]}
        for chain_name, expressions in expected_rules.items():
            for expression in expressions:
                self.rules["nftables"].append({"rule": {
                    "family": "inet", "table": "apaa", "chain": chain_name,
                    "expr": expression,
                }})

    def read_runtime_attestation(self): return self.runtime
    def read_network_namespace_identity(self): return self.namespace
    def read_nftables_json(self): return self.rules


def make_signed_evidence(spec, key):
    return collect_signed_inspector_evidence(
        FakeHost(spec), spec, challenge=CHALLENGE, key_id="host-inspector-prod",
        signing_key=key, expected_proxy_addresses=PROXY_IPS, now=NOW,
    )


class FakeContext:
    def __init__(self): self.close_calls = 0
    def close(self): self.close_calls += 1


class FakeBrowser:
    def __init__(self, fail_context=False):
        self.context = FakeContext()
        self.fail_context = fail_context
        self.close_calls = 0
        self.context_options = None
    def new_context(self, **kwargs):
        self.context_options = kwargs
        if self.fail_context: raise RuntimeError("context creation failed")
        return self.context
    def close(self): self.close_calls += 1


class FakeBrowserType:
    def __init__(self, browser=None, fail_launch=False):
        self.browser = browser or FakeBrowser()
        self.fail_launch = fail_launch
        self.launch_options = None
        self.calls = 0
    def launch(self, **kwargs):
        self.calls += 1
        self.launch_options = kwargs
        if self.fail_launch: raise RuntimeError("launch failed")
        return self.browser


def make_gate(browser_type, spec, key):
    return AttestedBrowserRuntime(
        spec,
        trusted_public_keys={"host-inspector-prod": key.public_key().public_bytes_raw()},
        expected_proxy_addresses=PROXY_IPS,
        worker_start=create_playwright_worker_start(browser_type),
    )


def test_launch_uses_signed_firewall_ip_pin_and_enforces_tls_verification():
    spec = make_spec()
    key = Ed25519PrivateKey.generate()
    browser_type = FakeBrowserType()
    gate = make_gate(browser_type, spec, key)
    session = launch_chromium(gate, make_signed_evidence(spec, key), challenge=CHALLENGE, now=NOW)

    assert isinstance(session, BrowserSession)
    assert browser_type.calls == 1
    assert browser_type.launch_options["proxy"] == {"server": "http://172.20.0.2:3128"}
    assert browser_type.launch_options["headless"] is True
    assert browser_type.launch_options["chromium_sandbox"] is True
    assert "--proxy-bypass-list=<-loopback>" in browser_type.launch_options["args"]
    assert "--disable-http2" in browser_type.launch_options["args"]
    assert "--disable-quic" in browser_type.launch_options["args"]
    assert browser_type.browser.context_options["ignore_https_errors"] is False
    assert browser_type.browser.context_options["accept_downloads"] is False
    assert browser_type.browser.context_options["service_workers"] == "block"
    session.close()
    session.close()
    assert browser_type.browser.context.close_calls == 1
    assert browser_type.browser.close_calls == 1


def test_unsigned_or_tampered_evidence_never_starts_browser():
    spec = make_spec()
    key = Ed25519PrivateKey.generate()
    browser_type = FakeBrowserType()
    gate = make_gate(browser_type, spec, key)
    envelope = make_signed_evidence(spec, key)
    envelope["signature"] = "A" * len(envelope["signature"])
    with pytest.raises(BrowserLaunchError, match="Signed runtime/firewall"):
        launch_chromium(gate, envelope, challenge=CHALLENGE, now=NOW)
    assert browser_type.calls == 0


def test_wrong_challenge_never_starts_browser():
    spec = make_spec()
    key = Ed25519PrivateKey.generate()
    browser_type = FakeBrowserType()
    gate = make_gate(browser_type, spec, key)
    with pytest.raises(BrowserLaunchError):
        launch_chromium(gate, make_signed_evidence(spec, key), challenge="e" * 64, now=NOW)
    assert browser_type.calls == 0


def test_untrusted_gate_type_is_rejected():
    with pytest.raises(TypeError, match="concrete AttestedBrowserRuntime"):
        launch_chromium(object(), {}, challenge=CHALLENGE, now=NOW)


def test_context_creation_failure_closes_browser_and_does_not_fallback():
    spec = make_spec()
    key = Ed25519PrivateKey.generate()
    browser = FakeBrowser(fail_context=True)
    browser_type = FakeBrowserType(browser=browser)
    gate = make_gate(browser_type, spec, key)
    with pytest.raises(BrowserLaunchError, match="no alternate or direct"):
        launch_chromium(gate, make_signed_evidence(spec, key), challenge=CHALLENGE, now=NOW)
    assert browser.close_calls == 1
    assert browser_type.calls == 1


def test_browser_launch_failure_does_not_attempt_direct_fallback():
    spec = make_spec()
    key = Ed25519PrivateKey.generate()
    browser_type = FakeBrowserType(fail_launch=True)
    gate = make_gate(browser_type, spec, key)
    with pytest.raises(BrowserLaunchError, match="no alternate or direct"):
        launch_chromium(gate, make_signed_evidence(spec, key), challenge=CHALLENGE, now=NOW)
    assert browser_type.calls == 1
