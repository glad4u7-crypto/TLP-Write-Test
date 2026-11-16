import json

from core.oci_worker_executor import CommandResult
from scripts.qualify_oci_runtime_preflight import main


def runner_for(runtime, version, info):
    def run(argv, timeout):
        if argv[1] == "version":
            return CommandResult(0, version, "")
        if argv[1] == "info":
            return CommandResult(0, info, "")
        if argv[1] == "create":
            return CommandResult(0, "--read-only --cap-drop --security-opt", "")
        if argv[1] == "inspect":
            return CommandResult(0, "--format", "")
        if argv[1] == "start":
            return CommandResult(0, "start", "")
        raise AssertionError(argv)
    return run


def test_host_preflight_reports_compatible_runtime(capsys):
    runner = runner_for(
        "podman", "5.4.2",
        '{"host":{"cgroupVersion":"v2","security":{"rootless":true,"seccompEnabled":true}}}',
    )
    assert main(["--runtime", "podman", "--pinned-version", "5.4.2"], runner=runner) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["qualified"] is True
    assert result["observed_version"] == "5.4.2"


def test_host_preflight_fails_closed_on_version_drift(capsys):
    runner = runner_for(
        "podman", "5.4.2",
        '{"host":{"cgroupVersion":"v2","security":{"rootless":true,"seccompEnabled":true}}}',
    )
    assert main(["--runtime", "podman", "--pinned-version", "5.4.1"], runner=runner) == 2
    result = json.loads(capsys.readouterr().out)
    assert result["qualified"] is False
    assert "runtime_version_not_pinned" in result["reasons"]


def test_host_preflight_reports_probe_failure_without_leaking_command_output(capsys):
    def fail(argv, timeout):
        return CommandResult(1, "", "private daemon detail")
    assert main(["--runtime", "docker", "--pinned-version", "27.5.1"], runner=fail) == 2
    output = capsys.readouterr().out
    assert "read_only_runtime_probe_failed_closed" in output
    assert "private daemon detail" not in output
