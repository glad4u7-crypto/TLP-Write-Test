import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from core.attested_browser_runtime import AttestedBrowserRuntime
from core.browser_nftables import collect_signed_inspector_evidence, _expected_dual_stack_rules
from core.browser_isolation import validate_worker_profile
from core.browser_runtime import build_worker_launch_spec
from core.browser_launcher import (
    BrowserLaunchError,
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

    def read_runtime_attestation(self):
        return self.runtime

    def read_network_namespace_identity(self):
        return self.namespace

    def read_nftables_json(self):
        return self.rules


def make_signed_evidence(spec, key):
    return collect_signed_inspector_evidence(
        FakeHost(spec), spec, challenge=CHALLENGE, key_id="host-inspector-prod",
        signing_key=key, expected_proxy_addresses=PROXY_IPS, now=NOW,
    )


class FakeBrowserType:
    def __init__(self):
        self.calls = 0

    def launch(self, **kwargs):
        self.calls += 1
        raise AssertionError("Host-local browser process must never be started.")


def make_gate(browser_type, spec, key):
    return AttestedBrowserRuntime(
        spec,
        trusted_public_keys={"host-inspector-prod": key.public_key().public_bytes_raw()},
        expected_proxy_addresses=PROXY_IPS,
        worker_start=create_playwright_worker_start(browser_type),
    )


def test_valid_signed_worker_evidence_does_not_authorize_host_local_chromium():
    spec = make_spec()
    key = Ed25519PrivateKey.generate()
    browser_type = FakeBrowserType()
    gate = make_gate(browser_type, spec, key)

    with pytest.raises(BrowserLaunchError, match="Host-local Playwright launch is forbidden"):
        launch_chromium(gate, make_signed_evidence(spec, key), challenge=CHALLENGE, now=NOW)

    assert browser_type.calls == 0


def test_unsigned_or_tampered_evidence_never_reaches_local_launcher():
    spec = make_spec()
    key = Ed25519PrivateKey.generate()
    browser_type = FakeBrowserType()
    gate = make_gate(browser_type, spec, key)
    envelope = make_signed_evidence(spec, key)
    envelope["signature"] = "A" * len(envelope["signature"])

    with pytest.raises(BrowserLaunchError, match="Signed runtime/firewall"):
        launch_chromium(gate, envelope, challenge=CHALLENGE, now=NOW)

    assert browser_type.calls == 0


def test_wrong_challenge_never_reaches_local_launcher():
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


def test_legacy_worker_start_callback_is_always_fail_closed():
    spec = make_spec()
    browser_type = FakeBrowserType()
    callback = create_playwright_worker_start(browser_type)

    with pytest.raises(BrowserLaunchError, match="Host-local Playwright launch is forbidden"):
        callback(spec, object())

    assert browser_type.calls == 0
