"""End-to-end fake-runner tests for the P18 OCI attestation gate."""

import json

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from core.browser_runtime import build_worker_launch_spec
from core.oci_worker_plan import build_oci_worker_plan
from core.oci_worker_executor import CommandResult, OCIWorkerExecutor
from core.inspector_control_plane import InspectorEvidenceControlPlane
from core.inspector_key_registry import (
    InspectorPublicKeyRecord,
    InspectorPublicKeyRegistry,
)
from core.sqlite_security_store import SQLiteSecurityStore
from core.storage import TenantKey
from test_browser_inspector import profile, signed_envelope, resign


IMAGE = "registry.example.invalid/apaa/worker@sha256:" + "a" * 64
TENANT = TenantKey("https://issuer.example", "owner-1")
NOW = 1000
PROXY_IP = "172.20.0.2"


def setup(tmp_path, *, corrupt_signature=False, revoked_key=False, wrong_worker=False, replay_challenge=False, supplier_error=False):
    spec = build_worker_launch_spec(profile())
    plan = build_oci_worker_plan(
        spec, runtime="podman", image=IMAGE, network_name="apaa-egress-prod",
        job_id="job-123", seccomp_profile="/etc/apaa/seccomp.json", rootless=True,
    )
    private = Ed25519PrivateKey.generate()
    _, keys = signed_envelope(spec, private)
    public = keys["host-inspector-prod"]
    control = InspectorEvidenceControlPlane(
        security_store=SQLiteSecurityStore(tmp_path / "security.sqlite3"),
        key_registry=InspectorPublicKeyRegistry([
            InspectorPublicKeyRecord(
                key_id="host-inspector-prod", public_key=public,
                not_before=900, not_after=1100, revoked=revoked_key,
            )
        ]),
    )
    calls = []

    def runner(argv, timeout):
        calls.append(tuple(argv))
        if argv[1] == "create":
            return CommandResult(0, "a" * 64, "")
        if argv[1] == "inspect":
            return CommandResult(0, json.dumps([{
                "Id": "a" * 64,
                "State": {"Status": "created"},
                "Config": {"Image": IMAGE},
                "HostConfig": {
                    "NetworkMode": "apaa-egress-prod", "ReadonlyRootfs": True,
                    "Privileged": False, "PidMode": "private", "IpcMode": "private",
                    "CapDrop": ["ALL"],
                    "SecurityOpt": ["no-new-privileges:true", "seccomp=/etc/apaa/seccomp.json"],
                },
            }]), "")
        return CommandResult(0, "", "")

    first_challenge = None

    def evidence_supplier(challenge, snapshot):
        nonlocal first_challenge
        if supplier_error:
            raise RuntimeError('host inspector interrupted')
        if replay_challenge:
            if first_challenge is None:
                first_challenge = challenge
            challenge = first_challenge
        envelope, _ = signed_envelope(spec, private)
        envelope["payload"]["challenge"] = challenge
        envelope["payload"]["runtime_attestation"]["runtime_id"] = snapshot["container_id"]
        envelope["payload"]["runtime_attestation"]["worker_id"] = snapshot["container_name"]
        envelope["payload"]["firewall"]["runtime_id"] = snapshot["container_id"]
        envelope["payload"]["firewall"]["worker_id"] = (
            "apaa-worker-other-job" if wrong_worker else snapshot["container_name"]
        )
        resign(envelope, private)
        if corrupt_signature:
            envelope["signature"] = "A" * 88
        return envelope

    executor = OCIWorkerExecutor(
        runner=runner,
        evidence_supplier=evidence_supplier,
        trusted_public_keys=keys,
        expected_proxy_addresses=[PROXY_IP],
        inspector_control_plane=control,
        tenant=TENANT,
        clock=lambda: NOW,
    )
    return spec, plan, calls, executor


def test_p18_valid_durable_identity_bound_evidence_is_required_before_start(tmp_path):
    spec, plan, calls, executor = setup(tmp_path)
    report = executor.launch(plan, spec)

    commands = [call[1] for call in calls]
    assert commands == ["create", "inspect", "start"]
    assert report.started is True
    assert report.cleaned is False
    assert report.handle.container_id == "a" * 64
    assert report.handle.container_name == plan.container_name
    stages = [event.stage for event in report.events]
    assert stages.index("ATTEST") < stages.index("START")


def test_p18_invalid_signature_blocks_start_and_removes_created_worker(tmp_path):
    spec, plan, calls, executor = setup(tmp_path, corrupt_signature=True)
    report = executor.launch(plan, spec)

    assert [call[1] for call in calls] == ["create", "inspect", "rm"]
    assert report.started is False
    assert report.handle is None
    assert report.cleaned is True
    assert "START" not in [event.stage for event in report.events]



def test_p22_revoked_host_inspector_key_blocks_start_and_cleans_worker(tmp_path):
    spec, plan, calls, executor = setup(tmp_path, revoked_key=True)
    report = executor.launch(plan, spec)

    assert [call[1] for call in calls] == ["create", "inspect", "rm"]
    assert report.started is False
    assert report.handle is None
    assert report.cleaned is True
    assert "START" not in [event.stage for event in report.events]


def test_p22_signed_evidence_for_different_worker_blocks_start(tmp_path):
    spec, plan, calls, executor = setup(tmp_path, wrong_worker=True)
    report = executor.launch(plan, spec)

    assert [call[1] for call in calls] == ["create", "inspect", "rm"]
    assert report.started is False
    assert report.handle is None
    assert report.cleaned is True
    assert "START" not in [event.stage for event in report.events]



def test_p22_replayed_challenge_from_previous_launch_blocks_second_start(tmp_path):
    spec, plan, calls, executor = setup(tmp_path, replay_challenge=True)
    first = executor.launch(plan, spec)
    second = executor.launch(plan, spec)

    assert first.started is True
    assert second.started is False
    assert second.cleaned is True
    commands = [call[1] for call in calls]
    assert commands == ["create", "inspect", "start", "create", "inspect", "rm"]
    assert commands.count("start") == 1


def test_p22_host_inspector_interruption_cleans_created_worker(tmp_path):
    spec, plan, calls, executor = setup(tmp_path, supplier_error=True)
    report = executor.launch(plan, spec)

    assert [call[1] for call in calls] == ["create", "inspect", "rm"]
    assert report.started is False
    assert report.cleaned is True
    assert "START" not in [event.stage for event in report.events]
