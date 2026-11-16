import base64
import copy
import json

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from core.browser_isolation import validate_worker_profile
from core.browser_runtime import build_worker_launch_spec
from core.browser_inspector import (
    InspectorEvidenceError,
    verify_signed_inspector_evidence,
)


def profile():
    return validate_worker_profile({
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


def runtime_attestation(spec):
    return {
        "schema_version": 1, "launch_spec_digest": spec.digest,
        "runtime_id": "runtime:test-001", "worker_id": "worker:test-001",
        "image_digest": "sha256:" + "a" * 64,
        "attestor_id": "inspector:test-001", "evidence_digest": "b" * 64,
        "observed_at": 1000, "state": "created", "process_started": False,
        "runtime_config_verified": True, "host_firewall_verified": True,
        "uid": spec.uid, "gid": spec.gid,
        "privileged": False, "read_only_root": True,
        "no_new_privileges": True, "capabilities_effective": [],
        "namespaces": list(spec.namespaces), "host_mounts": [],
        "secret_mounts": [], "writable_mounts": list(spec.writable_mounts),
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


def firewall_evidence():
    return {
        "schema_version": 1,
        "runtime_id": "runtime:test-001",
        "worker_id": "worker:test-001",
        "network_namespace_inode": 4026533001,
        "interface": "eth0",
        "backend": "nftables",
        "observed_at": 1000,
        "default_egress_policy": "drop",
        "allowed_egress": [{
            "protocol": "tcp",
            "destination_ip": "172.20.0.2",
            "destination_port": 3128,
        }],
        "direct_dns_blocked": True,
        "proxy_side_dns_only": True,
        "ruleset_digest": "c" * 64,
    }


def signed_envelope(spec, private_key=None, **changes):
    private_key = private_key or Ed25519PrivateKey.generate()
    payload = {
        "challenge": "d" * 64,
        "runtime_attestation": runtime_attestation(spec),
        "firewall": firewall_evidence(),
    }
    payload.update(changes)
    signed = {"schema_version": 1, "key_id": "host-inspector-prod", "payload": payload}
    canonical = json.dumps(
        signed, sort_keys=True, separators=(",", ":"),
        ensure_ascii=True, allow_nan=False,
    ).encode("utf-8")
    signature = private_key.sign(canonical)
    envelope = {**signed, "signature": base64.b64encode(signature).decode("ascii")}
    public_key = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return envelope, {"host-inspector-prod": public_key}


def verify(envelope, keys, **kwargs):
    return verify_signed_inspector_evidence(
        build_worker_launch_spec(profile()), envelope,
        trusted_public_keys=keys, expected_challenge="d" * 64,
        expected_proxy_addresses=["172.20.0.2"], now=1000, **kwargs,
    )


def resign(envelope, private_key):
    signed = {key: envelope[key] for key in ("schema_version", "key_id", "payload")}
    canonical = json.dumps(
        signed, sort_keys=True, separators=(",", ":"),
        ensure_ascii=True, allow_nan=False,
    ).encode("utf-8")
    envelope["signature"] = base64.b64encode(private_key.sign(canonical)).decode("ascii")
    return envelope


def test_accepts_valid_signed_runtime_and_exact_proxy_firewall_evidence():
    spec = build_worker_launch_spec(profile())
    envelope, keys = signed_envelope(spec)
    result = verify(envelope, keys)
    assert result.key_id == "host-inspector-prod"
    assert result.runtime.worker_state == "created"
    assert result.firewall.backend == "nftables"
    assert result.firewall.network_namespace_inode == 4026533001
    assert result.firewall.allowed_proxy_addresses == ("172.20.0.2",)
    assert result.firewall.proxy_port == 3128


def test_rejects_untrusted_key_and_malformed_public_key():
    spec = build_worker_launch_spec(profile())
    envelope, keys = signed_envelope(spec)
    with pytest.raises(InspectorEvidenceError):
        verify(envelope, {})
    with pytest.raises(InspectorEvidenceError):
        verify(envelope, {"host-inspector-prod": b"short"})


def test_rejects_tampered_payload_and_signature():
    spec = build_worker_launch_spec(profile())
    envelope, keys = signed_envelope(spec)
    tampered = copy.deepcopy(envelope)
    tampered["payload"]["firewall"]["default_egress_policy"] = "accept"
    with pytest.raises(InspectorEvidenceError):
        verify(tampered, keys)
    broken = copy.deepcopy(envelope)
    broken["signature"] = base64.b64encode(b"x" * 64).decode("ascii")
    with pytest.raises(InspectorEvidenceError):
        verify(broken, keys)


def test_rejects_bad_signature_encoding_and_envelope_schema():
    spec = build_worker_launch_spec(profile())
    envelope, keys = signed_envelope(spec)
    bad_signature = copy.deepcopy(envelope)
    bad_signature["signature"] = "not base64!"
    with pytest.raises(InspectorEvidenceError):
        verify(bad_signature, keys)
    extra = copy.deepcopy(envelope)
    extra["unsigned_claim"] = True
    with pytest.raises(InspectorEvidenceError):
        verify(extra, keys)


def test_rejects_wrong_or_replayed_challenge():
    spec = build_worker_launch_spec(profile())
    envelope, keys = signed_envelope(spec)
    with pytest.raises(InspectorEvidenceError):
        verify_signed_inspector_evidence(
            spec, envelope, trusted_public_keys=keys,
            expected_challenge="e" * 64,
            expected_proxy_addresses=["172.20.0.2"], now=1000,
        )


@pytest.mark.parametrize("field,value", [
    ("default_egress_policy", "accept"),
    ("direct_dns_blocked", False),
    ("proxy_side_dns_only", False),
    ("backend", "iptables"),
    ("network_namespace_inode", 0),
    ("interface", "eth0; flush ruleset"),
    ("ruleset_digest", "not-a-digest"),
    ("observed_at", 900),
    ("observed_at", 1006),
])
def test_rejects_unsafe_or_stale_firewall_evidence(field, value):
    spec = build_worker_launch_spec(profile())
    private = Ed25519PrivateKey.generate()
    envelope, keys = signed_envelope(spec, private)
    envelope["payload"]["firewall"][field] = value
    resign(envelope, private)
    with pytest.raises(InspectorEvidenceError):
        verify(envelope, keys)


@pytest.mark.parametrize("rules", [
    [{"protocol": "tcp", "destination_ip": "172.20.0.2", "destination_port": 3128},
     {"protocol": "tcp", "destination_ip": "1.1.1.1", "destination_port": 443}],
    [{"protocol": "udp", "destination_ip": "172.20.0.2", "destination_port": 3128}],
    [{"protocol": "tcp", "destination_ip": "172.20.0.2", "destination_port": 53}],
    [{"protocol": "tcp", "destination_ip": "0.0.0.0", "destination_port": 3128}],
    [{"protocol": "tcp", "destination_ip": "172.20.0.2/32", "destination_port": 3128}],
    [{"protocol": "tcp", "destination_ip": "172.20.0.3", "destination_port": 3128}],
])
def test_rejects_firewall_allowlist_wider_or_different_than_proxy(rules):
    spec = build_worker_launch_spec(profile())
    private = Ed25519PrivateKey.generate()
    envelope, keys = signed_envelope(spec, private)
    envelope["payload"]["firewall"]["allowed_egress"] = rules
    resign(envelope, private)
    with pytest.raises(InspectorEvidenceError):
        verify(envelope, keys)


def test_rejects_firewall_worker_or_runtime_identity_mismatch():
    spec = build_worker_launch_spec(profile())
    private = Ed25519PrivateKey.generate()
    envelope, keys = signed_envelope(spec, private)
    envelope["payload"]["firewall"]["worker_id"] = "worker:other-001"
    resign(envelope, private)
    with pytest.raises(InspectorEvidenceError):
        verify(envelope, keys)


def test_rejects_duplicate_or_unsafe_expected_proxy_addresses():
    spec = build_worker_launch_spec(profile())
    envelope, keys = signed_envelope(spec)
    with pytest.raises(InspectorEvidenceError):
        verify_signed_inspector_evidence(
            spec, envelope, trusted_public_keys=keys,
            expected_challenge="d" * 64,
            expected_proxy_addresses=["172.20.0.2", "172.20.0.2"], now=1000,
        )
    with pytest.raises(InspectorEvidenceError):
        verify_signed_inspector_evidence(
            spec, envelope, trusted_public_keys=keys,
            expected_challenge="d" * 64,
            expected_proxy_addresses=["127.0.0.1"], now=1000,
        )


def test_rejects_unknown_or_missing_nested_fields_even_when_signed():
    spec = build_worker_launch_spec(profile())
    private = Ed25519PrivateKey.generate()
    envelope, keys = signed_envelope(spec, private)
    envelope["payload"]["firewall"]["comment"] = "trust me"
    resign(envelope, private)
    with pytest.raises(InspectorEvidenceError):
        verify(envelope, keys)


def test_verification_is_offline_and_has_no_process_or_socket_side_effects(monkeypatch):
    import socket
    import subprocess

    def forbidden(*_args, **_kwargs):
        raise AssertionError("Inspector evidence verification must remain offline.")

    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    spec = build_worker_launch_spec(profile())
    envelope, keys = signed_envelope(spec)
    result = verify(envelope, keys)
    assert result.firewall.default_egress_policy == "drop"
    assert result.firewall.backend == "nftables"
