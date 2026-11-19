import pytest

from core.browser_isolation import validate_worker_profile
from core.browser_runtime import build_worker_launch_spec
from core.oci_worker_plan import OCIWorkerPlanError, build_oci_worker_plan


IMAGE = "registry.example.invalid/apaa/worker@sha256:" + "a" * 64
SECCOMP = "/etc/apaa/seccomp/browser-worker.json"


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


def plan(**overrides):
    args = {
        "runtime": "podman",
        "image": IMAGE,
        "network_name": "apaa-egress-prod",
        "job_id": "job-123",
        "seccomp_profile": SECCOMP,
        "rootless": True,
    }
    args.update(overrides)
    return build_oci_worker_plan(make_spec(), **args)


def test_plan_is_inert_argv_and_has_two_phase_create_then_start():
    result = plan()
    assert isinstance(result.create_argv, tuple)
    assert result.create_argv[:2] == ("podman", "create")
    assert result.inspect_argv == ("podman", "inspect", "apaa-worker-job-123")
    assert result.start_argv == ("podman", "start", "apaa-worker-job-123")
    assert result.stop_argv[:3] == ("podman", "stop", "--time")
    assert result.remove_argv == ("podman", "rm", "--force", "apaa-worker-job-123")
    assert result.launch_spec_digest == make_spec().digest
    assert all(isinstance(arg, str) for arg in result.create_argv)
    assert not any(";" in arg or "&&" in arg or "|" in arg for arg in result.create_argv)


def test_plan_enforces_read_only_root_capability_drop_and_no_new_privileges():
    args = plan().create_argv
    assert "--read-only" in args
    assert "--cap-drop=ALL" in args
    assert "--security-opt=no-new-privileges:true" in args
    assert f"--security-opt=seccomp={SECCOMP}" in args
    assert "--user" in args and "10001:10001" in args
    assert "--pids-limit" in args and "64" in args
    assert "--memory" in args and str(512 * 1024 * 1024) in args
    assert "--cpus" in args and "1" in args


def test_plan_uses_only_explicit_named_egress_network_and_digest_pinned_image():
    args = plan().create_argv
    network_index = args.index("--network")
    assert args[network_index + 1] == "apaa-egress-prod"
    assert args[-1] == IMAGE
    assert "--pull=never" in args


def test_plan_has_ephemeral_private_runtime_surfaces():
    args = plan().create_argv
    for expected in (
        "--ipc=private", "--pid=private", "--uts=private",
        "/tmp/job:rw,noexec,nosuid,nodev,size=16m",
        "/run:rw,noexec,nosuid,nodev,size=16m",
    ):
        assert expected in args
    assert "/tmp:rw,noexec,nosuid,nodev,size=64m" not in args
    assert "--privileged" not in args
    assert "--network=host" not in args
    assert "--pid=host" not in args
    assert "-v" not in args and "--volume" not in args


@pytest.mark.parametrize("overrides", [
    {"runtime": "bash"},
    {"image": "registry.example.invalid/apaa/worker:latest"},
    {"network_name": "bridge"},
    {"job_id": "../../host"},
    {"seccomp_profile": "relative/profile.json"},
    {"seccomp_profile": "/etc/apaa/../host/profile.json"},
    {"rootless": False},
])
def test_plan_rejects_untrusted_runtime_inputs(overrides):
    with pytest.raises(OCIWorkerPlanError):
        plan(**overrides)


def test_plan_rejects_invalid_spec_type():
    with pytest.raises(OCIWorkerPlanError):
        build_oci_worker_plan(
            object(), runtime="podman", image=IMAGE,
            network_name="apaa-egress-prod", job_id="job-123",
            seccomp_profile=SECCOMP, rootless=True,
        )


def test_plan_maps_only_approved_proxy_environment_and_worker_entrypoint():
    args = plan().create_argv
    assert "APAA_EGRESS_PROXY=http://egress-proxy.internal:3128" in args
    assert "HTTP_PROXY=http://egress-proxy.internal:3128" in args
    assert "HTTPS_PROXY=http://egress-proxy.internal:3128" in args
    assert "NO_PROXY=" in args
    assert "no_proxy=" in args
    assert "/usr/local/bin/apaa-worker" in args
    assert "TMPDIR=/tmp/job" in args


def test_plan_does_not_invoke_runtime_or_change_host_state():
    # The API returns argv only. No subprocess, socket, filesystem or runtime
    # adapter is accepted or called by this module.
    result = plan(runtime="docker")
    assert result.create_argv[0] == "docker"
    assert result.start_argv == ("docker", "start", result.container_name)
