import json
import pytest

from core.browser_runtime import build_worker_launch_spec
from core.browser_isolation import validate_worker_profile
from core.oci_worker_plan import build_oci_worker_plan
from core.oci_worker_executor import CommandResult, OCIWorkerExecutor


IMAGE = "registry.example.invalid/apaa/worker@sha256:" + "a" * 64
PROFILE = {
    "schema_version": 1, "uid": 10001, "gid": 10001,
    "privileged": False, "read_only_root": True, "no_new_privileges": True,
    "capabilities_drop": ["ALL"], "host_network": False, "host_pid": False,
    "host_ipc": False, "host_mounts": [], "secret_mounts": [],
    "writable_mounts": ["/tmp/job"], "browser_profile_persistence": False,
    "cdp_exposed": False, "direct_egress": False, "proxy_only_egress": True,
    "dns_via_proxy_only": True, "egress_proxy": "http://proxy.apaa.internal:3128",
    "memory_limit_bytes": 536870912, "cpu_limit_millis": 1000,
    "pids_limit": 64, "job_timeout_seconds": 30,
}


def setup_runner(inspect=None, fail_at=None):
    calls = []
    def runner(argv, timeout):
        calls.append(tuple(argv))
        if fail_at == argv[1]:
            return CommandResult(1, "", "failure")
        if argv[1] == "inspect":
            return CommandResult(0, json.dumps([inspect or {
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
    return calls, runner


def make_executor(runner, evidence=None):
    return OCIWorkerExecutor(
        runner=runner,
        evidence_supplier=lambda challenge, snapshot: evidence,
        trusted_public_keys={"test-key": b"x" * 32},
        expected_proxy_addresses=["10.20.0.2"],
        clock=lambda: 1000,
        challenge_factory=lambda: "a" * 64,
    )


def make_plan():
    spec = build_worker_launch_spec(validate_worker_profile(PROFILE))
    plan = build_oci_worker_plan(
        spec, runtime="podman", image=IMAGE, network_name="apaa-egress-prod",
        job_id="job-123", seccomp_profile="/etc/apaa/seccomp.json", rootless=True,
    )
    return spec, plan


def test_create_inspect_then_attestation_failure_never_starts_and_cleans():
    spec, plan = make_plan()
    calls, runner = setup_runner()
    report = make_executor(runner).launch(plan, spec)
    assert [call[1] for call in calls] == ["create", "inspect", "rm"]
    assert not report.started
    assert report.cleaned
    assert [event.stage for event in report.events] == ["CREATE", "INSPECT", "BLOCK", "CLEANUP"]


def test_create_failure_never_inspects_or_starts():
    spec, plan = make_plan()
    calls, runner = setup_runner(fail_at="create")
    report = make_executor(runner).launch(plan, spec)
    assert [call[1] for call in calls] == ["create"]
    assert not report.started


def test_bad_stopped_state_never_starts():
    spec, plan = make_plan()
    calls, runner = setup_runner(inspect={
        "Id": "a" * 64, "State": {"Status": "running"},
        "Config": {"Image": IMAGE},
        "HostConfig": {"NetworkMode": "apaa-egress-prod", "ReadonlyRootfs": True,
                       "CapDrop": ["ALL"], "SecurityOpt": ["no-new-privileges:true", "seccomp=x"]},
    })
    report = make_executor(runner).launch(plan, spec)
    assert "start" not in [call[1] for call in calls]
    assert report.cleaned


def test_plan_spec_digest_mismatch_is_rejected_before_command():
    spec, plan = make_plan()
    calls, runner = setup_runner()
    other = build_worker_launch_spec(validate_worker_profile({**PROFILE, "job_timeout_seconds": 29}))
    with pytest.raises(Exception, match="digest do not match"):
        make_executor(runner).launch(plan, other)
    assert calls == []
