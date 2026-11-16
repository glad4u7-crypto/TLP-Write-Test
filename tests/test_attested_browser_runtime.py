import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from core.attested_browser_runtime import AttestedBrowserRuntime, BrowserRuntimeGateError
from core.browser_isolation import validate_worker_profile
from core.browser_runtime import build_worker_launch_spec
from core.browser_nftables import collect_signed_inspector_evidence


NOW = 1000
CHALLENGE = "d" * 64
PROXY_IP = "172.20.0.2"


def make_spec():
    profile = validate_worker_profile({
        "schema_version": 1, "uid": 10001, "gid": 10001,
        "privileged": False, "read_only_root": True,
        "no_new_privileges": True, "capabilities_drop": ["ALL"],
        "host_network": False, "host_pid": False, "host_ipc": False,
        "host_mounts": [], "secret_mounts": [],
        "writable_mounts": ["/tmp/job"],
        "browser_profile_persistence": False, "cdp_exposed": False,
        "direct_egress": False, "proxy_only_egress": True,
        "dns_via_proxy_only": True,
        "egress_proxy": "http://egress-proxy.internal:3128",
        "memory_limit_bytes": 512 * 1024 * 1024,
        "cpu_limit_millis": 1000, "pids_limit": 64,
        "job_timeout_seconds": 30,
    })
    return build_worker_launch_spec(profile)


def match(left, right):
    return {"match": {"op": "==", "left": left, "right": right}}


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
        self.rules = {"nftables": [
            {"metainfo": {"version": "1.0.9", "release_name": "test"}},
            {"table": {"family": "inet", "name": "filter"}},
            {"chain": {"family": "inet", "table": "filter", "name": "egress",
                       "type": "filter", "hook": "output", "prio": 0, "policy": "drop"}},
            {"rule": {"family": "inet", "table": "filter", "chain": "egress", "expr": [
                match({"meta": {"key": "l4proto"}}, "tcp"),
                match({"payload": {"protocol": "ip", "field": "daddr"}}, PROXY_IP),
                match({"payload": {"protocol": "tcp", "field": "dport"}}, 3128),
                {"accept": None},
            ]}},
        ]}

    def read_runtime_attestation(self):
        return self.runtime

    def read_network_namespace_identity(self):
        return self.namespace

    def read_nftables_json(self):
        return self.rules


def signed_evidence(spec, key):
    return collect_signed_inspector_evidence(
        FakeHost(spec), spec, challenge=CHALLENGE, key_id="host-inspector-prod",
        signing_key=key, expected_proxy_addresses=[PROXY_IP], now=NOW,
    )


def test_gate_verifies_signed_evidence_before_calling_worker_adapter():
    spec = make_spec()
    key = Ed25519PrivateKey.generate()
    calls = []
    gate = AttestedBrowserRuntime(
        spec,
        trusted_public_keys={"host-inspector-prod": key.public_key().public_bytes_raw()},
        expected_proxy_addresses=[PROXY_IP],
        worker_start=lambda passed_spec, evidence: (
            calls.append((passed_spec, evidence)) or "worker-handle"
        ),
    )

    result = gate.launch(signed_evidence(spec, key), challenge=CHALLENGE, now=NOW)

    assert result == "worker-handle"
    assert len(calls) == 1
    assert calls[0][0] == spec
    assert calls[0][1].firewall.default_egress_policy == "drop"
    assert calls[0][1].firewall.allowed_proxy_addresses == (PROXY_IP,)


def test_gate_blocks_launch_without_trusted_worker_adapter():
    spec = make_spec()
    key = Ed25519PrivateKey.generate()
    gate = AttestedBrowserRuntime(
        spec, trusted_public_keys={"host-inspector-prod": key.public_key().public_bytes_raw()},
        expected_proxy_addresses=[PROXY_IP],
    )
    with pytest.raises(BrowserRuntimeGateError, match="No trusted"):
        gate.launch(signed_evidence(spec, key), challenge=CHALLENGE, now=NOW)


@pytest.mark.parametrize("bad_challenge", ["x" * 64, ""])
def test_gate_blocks_challenge_mismatch_before_worker_adapter(bad_challenge):
    spec = make_spec()
    key = Ed25519PrivateKey.generate()
    calls = []
    gate = AttestedBrowserRuntime(
        spec, trusted_public_keys={"host-inspector-prod": key.public_key().public_bytes_raw()},
        expected_proxy_addresses=[PROXY_IP],
        worker_start=lambda *_: calls.append(True),
    )
    with pytest.raises(BrowserRuntimeGateError, match="evidence was rejected"):
        gate.launch(signed_evidence(spec, key), challenge=bad_challenge, now=NOW)
    assert calls == []


def test_gate_blocks_tampered_firewall_evidence_before_worker_adapter():
    spec = make_spec()
    key = Ed25519PrivateKey.generate()
    calls = []
    envelope = signed_evidence(spec, key)
    envelope["payload"]["firewall"]["default_egress_policy"] = "accept"
    gate = AttestedBrowserRuntime(
        spec, trusted_public_keys={"host-inspector-prod": key.public_key().public_bytes_raw()},
        expected_proxy_addresses=[PROXY_IP],
        worker_start=lambda *_: calls.append(True),
    )
    with pytest.raises(BrowserRuntimeGateError):
        gate.launch(envelope, challenge=CHALLENGE, now=NOW)
    assert calls == []


def test_gate_blocks_stale_evidence_before_worker_adapter():
    spec = make_spec()
    key = Ed25519PrivateKey.generate()
    calls = []
    gate = AttestedBrowserRuntime(
        spec, trusted_public_keys={"host-inspector-prod": key.public_key().public_bytes_raw()},
        expected_proxy_addresses=[PROXY_IP],
        worker_start=lambda *_: calls.append(True),
    )
    with pytest.raises(BrowserRuntimeGateError):
        gate.launch(signed_evidence(spec, key), challenge=CHALLENGE, now=NOW + 100)
    assert calls == []


def test_gate_fails_closed_when_worker_adapter_raises_without_fallback():
    spec = make_spec()
    key = Ed25519PrivateKey.generate()
    calls = []

    def broken_adapter(*_):
        calls.append("attempt")
        raise RuntimeError("adapter unavailable")

    gate = AttestedBrowserRuntime(
        spec, trusted_public_keys={"host-inspector-prod": key.public_key().public_bytes_raw()},
        expected_proxy_addresses=[PROXY_IP], worker_start=broken_adapter,
    )
    with pytest.raises(BrowserRuntimeGateError, match="no alternate or direct launch"):
        gate.launch(signed_evidence(spec, key), challenge=CHALLENGE, now=NOW)
    assert calls == ["attempt"]
