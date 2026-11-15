import copy
import pytest

from core.browser_isolation import WorkerIsolationProfile, validate_worker_profile
from core.browser_runtime import (
    RuntimeAttestationError,
    build_worker_launch_spec,
    verify_prestart_attestation,
)


def safe_profile():
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


def launch_spec():
    return build_worker_launch_spec(safe_profile())


def valid_attestation(spec=None, **overrides):
    spec = spec or launch_spec()
    result = {
        "schema_version": 1,
        "launch_spec_digest": spec.digest,
        "runtime_id": "runtime:test-001",
        "worker_id": "worker:test-001",
        "image_digest": "sha256:" + "a" * 64,
        "attestor_id": "inspector:test-001",
        "evidence_digest": "b" * 64,
        "observed_at": 1000,
        "state": "created",
        "process_started": False,
        "runtime_config_verified": True,
        "host_firewall_verified": True,
        "uid": spec.uid, "gid": spec.gid,
        "privileged": False, "read_only_root": True,
        "no_new_privileges": True, "capabilities_effective": [],
        "namespaces": list(spec.namespaces),
        "host_mounts": [], "secret_mounts": [],
        "writable_mounts": list(spec.writable_mounts),
        "browser_profile_persistence": False, "cdp_exposed": False,
        "direct_egress": False, "proxy_only_egress": True,
        "dns_via_proxy_only": True, "egress_proxy": spec.egress_proxy,
        "memory_limit_bytes": spec.memory_limit_bytes,
        "cpu_limit_millis": spec.cpu_limit_millis,
        "pids_limit": spec.pids_limit,
        "job_timeout_seconds": spec.job_timeout_seconds,
        "seccomp_enforced": True, "network_namespace_isolated": True,
        "firewall_default_deny": True,
        "egress_allowed": ["egress-proxy.internal:3128"],
        "direct_dns_egress_blocked": True, "proxy_side_dns_only": True,
    }
    result.update(overrides)
    return result


def test_builds_inert_launch_contract_from_validated_p04_profile():
    spec = launch_spec()
    assert spec.uid == 10001
    assert spec.namespaces == ("user", "pid", "network", "ipc", "uts", "mount")
    assert spec.capabilities_drop == ("ALL",)
    assert spec.direct_egress is False
    assert spec.proxy_only_egress is True
    assert spec.seccomp_required is True
    assert spec.launch_state_required == "created"
    assert len(spec.digest) == 64


def test_launch_contract_rejects_unvalidated_profile():
    with pytest.raises(RuntimeAttestationError):
        build_worker_launch_spec({"uid": 10001})


def test_accepts_fresh_complete_prestart_attestation():
    spec = launch_spec()
    result = verify_prestart_attestation(spec, valid_attestation(spec), now=1000)
    assert result.worker_state == "created"
    assert result.launch_spec_digest == spec.digest
    assert result.image_digest == "sha256:" + "a" * 64
    assert result.proxy_endpoint == spec.egress_proxy


def test_attestation_rejects_missing_or_unknown_fields():
    spec = launch_spec()
    missing = valid_attestation(spec)
    del missing["host_firewall_verified"]
    with pytest.raises(RuntimeAttestationError):
        verify_prestart_attestation(spec, missing, now=1000)
    unknown = valid_attestation(spec, debug=True)
    with pytest.raises(RuntimeAttestationError):
        verify_prestart_attestation(spec, unknown, now=1000)


def test_attestation_is_bound_to_exact_launch_spec():
    spec = launch_spec()
    other = build_worker_launch_spec(validate_worker_profile({
        "schema_version": 1, "uid": 10002, "gid": 10002,
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
    }))
    with pytest.raises(RuntimeAttestationError):
        verify_prestart_attestation(other, valid_attestation(spec), now=1000)


@pytest.mark.parametrize("field,value", [
    ("state", "running"), ("process_started", True),
    ("runtime_config_verified", False), ("host_firewall_verified", False),
    ("privileged", True), ("read_only_root", False),
    ("no_new_privileges", False), ("browser_profile_persistence", True),
    ("cdp_exposed", True), ("direct_egress", True),
    ("proxy_only_egress", False), ("dns_via_proxy_only", False),
    ("seccomp_enforced", False), ("network_namespace_isolated", False),
    ("firewall_default_deny", False), ("direct_dns_egress_blocked", False),
    ("proxy_side_dns_only", False),
])
def test_attestation_rejects_unsafe_runtime_boolean(field, value):
    spec = launch_spec()
    with pytest.raises(RuntimeAttestationError):
        verify_prestart_attestation(spec, valid_attestation(spec, **{field: value}), now=1000)


@pytest.mark.parametrize("field,value", [
    ("capabilities_effective", ["NET_ADMIN"]),
    ("namespaces", ["pid", "network"]),
    ("host_mounts", ["/:/host"]),
    ("secret_mounts", ["/run/secrets"]),
    ("writable_mounts", ["/tmp/job", "/etc"]),
    ("egress_allowed", ["0.0.0.0/0"]),
    ("egress_proxy", "http://other.internal:3128"),
])
def test_attestation_rejects_privilege_mount_namespace_or_egress_drift(field, value):
    spec = launch_spec()
    with pytest.raises(RuntimeAttestationError):
        verify_prestart_attestation(spec, valid_attestation(spec, **{field: value}), now=1000)


@pytest.mark.parametrize("field,value", [
    ("uid", 0), ("gid", 0), ("memory_limit_bytes", 1),
    ("cpu_limit_millis", 9999), ("pids_limit", 999),
    ("job_timeout_seconds", 999),
])
def test_attestation_rejects_identity_or_resource_limit_drift(field, value):
    spec = launch_spec()
    with pytest.raises(RuntimeAttestationError):
        verify_prestart_attestation(spec, valid_attestation(spec, **{field: value}), now=1000)


@pytest.mark.parametrize("image_digest", ["latest", "sha256:abc", "sha256:" + "A" * 64])
def test_attestation_requires_immutable_sha256_image_digest(image_digest):
    spec = launch_spec()
    with pytest.raises(RuntimeAttestationError):
        verify_prestart_attestation(spec, valid_attestation(spec, image_digest=image_digest), now=1000)


@pytest.mark.parametrize("observed_at", [900, 1006, True, "1000"])
def test_attestation_rejects_stale_future_or_non_integer_timestamp(observed_at):
    spec = launch_spec()
    with pytest.raises(RuntimeAttestationError):
        verify_prestart_attestation(spec, valid_attestation(spec, observed_at=observed_at), now=1000)


def test_attestation_rejects_malformed_evidence_digest_and_identity():
    spec = launch_spec()
    for overrides in ({"evidence_digest": "not-a-digest"}, {"runtime_id": "x"}, {"attestor_id": ""}):
        with pytest.raises(RuntimeAttestationError):
            verify_prestart_attestation(spec, valid_attestation(spec, **overrides), now=1000)


def test_attestation_rejects_invalid_spec_and_non_mapping_input():
    with pytest.raises(RuntimeAttestationError):
        verify_prestart_attestation(object(), {}, now=1000)
    with pytest.raises(RuntimeAttestationError):
        verify_prestart_attestation(launch_spec(), [], now=1000)


def test_attestation_validator_performs_no_runtime_or_network_operations(monkeypatch):
    import socket
    import subprocess

    def forbidden(*_args, **_kwargs):
        raise AssertionError("attestation validation must remain offline and side-effect free")

    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    result = verify_prestart_attestation(
        launch_spec(), valid_attestation(), now=1000
    )
    assert result.worker_state == "created"
