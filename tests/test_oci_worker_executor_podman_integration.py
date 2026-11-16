"""Disposable real-Podman exercise of APAA's OCI executor plumbing.

The ephemeral CI signer exists only to exercise the executor/control-plane
cryptographic and durable-challenge path against a real container runtime.
It is NOT a trusted host collector and does NOT qualify host firewall,
proxy-only egress, or production key provisioning.
"""
from __future__ import annotations

import base64
import json
import os
import time
import uuid

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from core.browser_runtime import build_worker_launch_spec
from core.inspector_control_plane import InspectorEvidenceControlPlane
from core.inspector_key_registry import InspectorPublicKeyRecord, InspectorPublicKeyRegistry
from core.oci_worker_executor import (
    CommandResult,
    OCIWorkerExecutor,
    subprocess_command_runner,
)
from core.oci_worker_plan import build_oci_worker_plan
from core.sqlite_security_store import SQLiteSecurityStore
from core.storage import TenantKey
from test_browser_inspector import (
    firewall_evidence,
    profile,
    resign,
    runtime_attestation,
    signed_envelope,
)


pytestmark = pytest.mark.skipif(
    os.environ.get("APAA_PODMAN_INTEGRATION") != "1",
    reason="requires the disposable rootless Podman qualification workflow",
)


def _runner(argv, timeout):
    return subprocess_command_runner(argv, timeout)


def _executor(tmp_path, *, plan, spec, corrupt_signature=False):
    now = int(time.time())
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    key_id = "ci-ephemeral-inspector"
    registry = InspectorPublicKeyRegistry([
        InspectorPublicKeyRecord(
            key_id=key_id,
            public_key=public,
            not_before=now - 5,
            not_after=now + 120,
        )
    ])
    control = InspectorEvidenceControlPlane(
        security_store=SQLiteSecurityStore(tmp_path / "security.sqlite3"),
        key_registry=registry,
    )
    proxy_ip = "172.20.0.2"

    def evidence_supplier(challenge, snapshot):
        envelope, _ = signed_envelope(spec, private)
        envelope["key_id"] = key_id
        payload = envelope["payload"]
        payload["challenge"] = challenge
        attestation = runtime_attestation(spec)
        attestation.update({
            "runtime_id": snapshot["container_id"],
            "worker_id": snapshot["container_name"],
            "image_digest": plan.image.rsplit("@", 1)[1],
            "attestor_id": key_id,
            "observed_at": now,
        })
        firewall = firewall_evidence()
        firewall.update({
            "runtime_id": snapshot["container_id"],
            "worker_id": snapshot["container_name"],
            "observed_at": now,
        })
        payload["runtime_attestation"] = attestation
        payload["firewall"] = firewall
        resign(envelope, private)
        if corrupt_signature:
            envelope["signature"] = base64.b64encode(b"x" * 64).decode("ascii")
        return envelope

    executor = OCIWorkerExecutor(
        runner=_runner,
        evidence_supplier=evidence_supplier,
        trusted_public_keys={key_id: public},
        expected_proxy_addresses=[proxy_ip],
        inspector_control_plane=control,
        tenant=TenantKey("https://ci.invalid", "ephemeral-owner"),
        clock=lambda: now,
        command_timeout_seconds=20,
    )
    return executor


def _build_plan():
    image = os.environ["APAA_PODMAN_IMAGE"]
    network = "apaa-egress-ci"
    seccomp = "/usr/share/containers/seccomp.json"
    if not os.path.isfile(seccomp):
        pytest.fail(f"required Podman seccomp profile is missing: {seccomp}")
    spec = build_worker_launch_spec(profile())
    plan = build_oci_worker_plan(
        spec,
        runtime="podman",
        image=image,
        network_name=network,
        job_id="ci-" + uuid.uuid4().hex[:16],
        seccomp_profile=seccomp,
        rootless=True,
    )
    return spec, plan


def test_executor_attests_then_starts_and_removes_real_rootless_podman_container(tmp_path):
    spec, plan = _build_plan()
    executor = _executor(tmp_path, plan=plan, spec=spec)
    report = executor.launch(plan, spec)

    assert report.started is True, report.events
    assert report.cleaned is False
    assert report.handle is not None
    assert report.handle.container_id
    assert [event.stage for event in report.events][:4] == [
        "CREATE", "INSPECT", "ATTEST", "START"
    ]

    cid = report.handle.container_id
    running = _runner(("podman", "inspect", "--format", "{{.State.Status}}", cid), 10)
    assert running.returncode == 0
    assert running.stdout.strip() == "running"

    try:
        process = _runner(
            ("podman", "exec", cid, "/busybox", "cat", "/proc/self/status"), 10
        )
        assert process.returncode == 0, process.stderr
        masks = {}
        for line in process.stdout.splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                if key in {"CapInh", "CapPrm", "CapEff", "CapBnd"}:
                    masks[key] = int(value.strip(), 16)
        assert set(masks) == {"CapInh", "CapPrm", "CapEff", "CapBnd"}
        assert not any(masks.values()), masks
    finally:
        stopped = executor.stop(report.handle, plan)
        assert stopped.cleaned is True

    absent = _runner(("podman", "inspect", cid), 10)
    assert absent.returncode != 0


def test_executor_rejects_bad_signature_and_cleans_real_created_container(tmp_path):
    spec, plan = _build_plan()
    executor = _executor(
        tmp_path, plan=plan, spec=spec, corrupt_signature=True
    )
    report = executor.launch(plan, spec)

    assert report.started is False
    assert report.handle is None
    assert report.cleaned is True
    stages = [event.stage for event in report.events]
    assert "ATTEST" not in stages
    assert "START" not in stages
    assert stages[-1] == "CLEANUP"

    absent = _runner(("podman", "ps", "--all", "--filter", f"name={plan.container_name}", "--format", "{{.ID}}"), 10)
    assert absent.returncode == 0
    assert not absent.stdout.strip()
