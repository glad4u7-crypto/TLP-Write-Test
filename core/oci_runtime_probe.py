"""Read-only Docker/Podman capability probe; never creates or starts containers."""
from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from core.oci_runtime_compat import OCIRuntimePolicy, OCIRuntimeSnapshot, OCIRuntimeAssessment, assess_oci_runtime
from core.oci_worker_executor import CommandResult, OCIExecutionError, CommandRunner


def _json_object(raw: str, stage: str) -> dict[str, object]:
    try:
        value = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise OCIExecutionError(f"{stage}: invalid JSON from OCI runtime.") from exc
    if not isinstance(value, dict):
        raise OCIExecutionError(f"{stage}: expected a JSON object.")
    return value


def _run(runner: CommandRunner, argv: Sequence[str], stage: str) -> str:
    result = runner(tuple(argv), 15)
    if not isinstance(result, CommandResult) or type(result.returncode) is not int:
        raise OCIExecutionError(f"{stage}: invalid command result.")
    if result.returncode != 0:
        raise OCIExecutionError(f"{stage}: runtime probe failed closed.")
    return result.stdout.strip()


def probe_oci_runtime(
    runtime: str,
    *,
    runner: CommandRunner,
    pinned_version: str,
) -> OCIRuntimeAssessment:
    """Probe exact version, rootless/cgroup/security and CLI contracts, read-only."""
    if runtime not in ("docker", "podman"):
        raise ValueError("Only Docker and Podman probes are supported.")
    if type(pinned_version) is not str or not pinned_version or any(c.isspace() for c in pinned_version):
        raise ValueError("An exact runtime version pin is required.")

    if runtime == "docker":
        version = _run(runner, ("docker", "version", "--format", "{{.Server.Version}}"), "version")
        info = _json_object(_run(runner, ("docker", "info", "--format", "{{json .}}"), "info"), "info")
        security = info.get("SecurityOptions", [])
        rootless = isinstance(security, list) and any("rootless" in str(x).lower() for x in security)
        cgroup = info.get("CgroupVersion")
    else:
        version = _run(runner, ("podman", "version", "--format", "{{.Client.Version}}"), "version")
        info = _json_object(_run(runner, ("podman", "info", "--format", "json"), "info"), "info")
        host = info.get("host")
        host = host if isinstance(host, dict) else {}
        security_info = host.get("security")
        security_info = security_info if isinstance(security_info, dict) else {}
        rootless = security_info.get("rootless") is True
        cgroup = host.get("cgroupVersion")
        security = ["seccomp"] if security_info.get("seccompEnabled") is True else []

    help_text = _run(runner, (runtime, "create", "--help"), "create-help")
    inspect_help = _run(runner, (runtime, "inspect", "--help"), "inspect-help")
    start_help = _run(runner, (runtime, "start", "--help"), "start-help")
    supports_create = all(flag in help_text for flag in ("--read-only", "--cap-drop", "--security-opt"))
    supports_inspect = "inspect" in inspect_help.lower() or "format" in inspect_help.lower()
    supports_start = "start" in start_help.lower() or "attach" in start_help.lower()

    snapshot = OCIRuntimeSnapshot(
        runtime=runtime,
        version=version,
        rootless=rootless,
        cgroup_version=str(cgroup or "").lower().removeprefix("v"),
        security_options=tuple(str(x) for x in security) if isinstance(security, list) else (),
        supports_create_inspect_start=supports_create and supports_inspect and supports_start,
        supports_readonly_rootfs="--read-only" in help_text,
        supports_cap_drop_all="--cap-drop" in help_text,
        supports_seccomp_profile="--security-opt" in help_text,
    )
    return assess_oci_runtime(snapshot, OCIRuntimePolicy(runtime=runtime, pinned_version=pinned_version))
