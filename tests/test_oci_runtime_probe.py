from core.oci_worker_executor import CommandResult
from core.oci_runtime_probe import probe_oci_runtime


def fake_runner(runtime, *, version, info):
    def run(argv, timeout):
        assert timeout == 15
        if argv[1] == "version":
            return CommandResult(0, version, "")
        if argv[1] == "info":
            return CommandResult(0, info, "")
        if argv[1] == "create":
            return CommandResult(0, "Usage: create --read-only --cap-drop --security-opt", "")
        if argv[1] == "inspect":
            return CommandResult(0, "Usage: inspect --format", "")
        if argv[1] == "start":
            return CommandResult(0, "Usage: start", "")
        raise AssertionError(argv)
    return run


def test_podman_probe_reads_rootless_cgroup_and_seccomp():
    runner = fake_runner(
        "podman", version="5.4.2",
        info='{"host":{"cgroupVersion":"v2","security":{"rootless":true,"seccompEnabled":true}}}',
    )
    result = probe_oci_runtime("podman", runner=runner, pinned_version="5.4.2")
    assert result.compatible
    assert result.observed_version == "5.4.2"


def test_docker_probe_reads_security_options_and_cgroup():
    runner = fake_runner(
        "docker", version="27.5.1",
        info='{"CgroupVersion":"2","SecurityOptions":["name=seccomp","name=rootless"]}',
    )
    result = probe_oci_runtime("docker", runner=runner, pinned_version="27.5.1")
    assert result.compatible


def test_wrong_version_pin_fails_closed():
    runner = fake_runner(
        "podman", version="5.4.2",
        info='{"host":{"cgroupVersion":"v2","security":{"rootless":true,"seccompEnabled":true}}}',
    )
    result = probe_oci_runtime("podman", runner=runner, pinned_version="5.4.1")
    assert not result.compatible
    assert "runtime_version_not_pinned" in result.reasons


def test_unknown_runtime_is_rejected_without_commands():
    def forbidden_runner(argv, timeout):
        raise AssertionError("no command should run")
    import pytest
    with pytest.raises(ValueError):
        probe_oci_runtime("containerd", runner=forbidden_runner, pinned_version="1.7.0")
