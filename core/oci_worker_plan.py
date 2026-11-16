"""Build-only OCI worker command plans with explicit fail-closed constraints.

This module never invokes Docker/Podman and never provisions a network. The
operator must independently provision and attest a rootless, proxy-only egress
network and a reviewed seccomp profile before executing any returned command.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
import re

from core.browser_runtime import WorkerLaunchSpec


class OCIWorkerPlanError(ValueError):
    """Raised when an OCI worker plan cannot be proven safe to construct."""


_NAME = re.compile(r"^[a-z0-9][a-z0-9-]{2,47}$")
_IMAGE = re.compile(r"^.+@sha256:[0-9a-f]{64}$")
_NETWORK = re.compile(r"^apaa-egress-[a-z0-9][a-z0-9-]{1,40}$")


@dataclass(frozen=True)
class OCIWorkerPlan:
    """Immutable argv vectors; no shell string or implicit execution."""

    runtime: str
    container_name: str
    image: str
    create_argv: tuple[str, ...]
    inspect_argv: tuple[str, ...]
    start_argv: tuple[str, ...]
    stop_argv: tuple[str, ...]
    remove_argv: tuple[str, ...]
    launch_spec_digest: str
    network_name: str
    seccomp_profile: str


def build_oci_worker_plan(
    spec: WorkerLaunchSpec,
    *,
    runtime: str,
    image: str,
    network_name: str,
    job_id: str,
    seccomp_profile: str,
    rootless: bool,
) -> OCIWorkerPlan:
    """Return a hardened, inert create/inspect/start/cleanup command plan.

    The rootless argument is an operator assertion, not runtime proof. A
    separate trusted inspector must attest the actual runtime, namespaces,
    seccomp enforcement and firewall before start_argv can be authorized.
    """
    if type(spec) is not WorkerLaunchSpec:
        raise OCIWorkerPlanError("A validated WorkerLaunchSpec is required.")
    if runtime not in {"podman", "docker"}:
        raise OCIWorkerPlanError("Only explicitly supported podman/docker runtimes are allowed.")
    if type(rootless) is not bool or rootless is not True:
        raise OCIWorkerPlanError("A rootless OCI runtime is mandatory.")
    if type(image) is not str or not _IMAGE.fullmatch(image):
        raise OCIWorkerPlanError("Worker image must be pinned by an immutable sha256 digest.")
    if type(network_name) is not str or not _NETWORK.fullmatch(network_name):
        raise OCIWorkerPlanError("An explicitly provisioned APAA egress network is required.")
    if type(job_id) is not str or not _NAME.fullmatch(job_id):
        raise OCIWorkerPlanError("Job ID is invalid.")
    if type(seccomp_profile) is not str or not seccomp_profile.startswith("/"):
        raise OCIWorkerPlanError("An absolute, reviewed seccomp profile path is required.")
    seccomp_path = PurePosixPath(seccomp_profile)
    if ".." in seccomp_path.parts or "\x00" in seccomp_profile:
        raise OCIWorkerPlanError("Seccomp profile path is not normalized.")
    if not spec.read_only_root or not spec.no_new_privileges:
        raise OCIWorkerPlanError("Read-only root and no-new-privileges are mandatory.")
    if spec.direct_egress or not spec.proxy_only_egress or not spec.dns_via_proxy_only:
        raise OCIWorkerPlanError("Direct egress is forbidden; proxy-only DNS/egress is required.")
    if spec.host_mounts or spec.secret_mounts or spec.browser_profile_persistence or spec.cdp_exposed:
        raise OCIWorkerPlanError("Host mounts, secret mounts, persistent profiles and CDP are forbidden.")
    if not spec.seccomp_required or spec.launch_state_required != "created":
        raise OCIWorkerPlanError("A seccomp-protected, pre-start created state is required.")

    name = f"apaa-worker-{job_id}"
    cpu_count = f"{spec.cpu_limit_millis / 1000:.3f}".rstrip("0").rstrip(".")
    create = (
        runtime, "create",
        "--name", name,
        "--pull=never",
        "--network", network_name,
        "--user", f"{spec.uid}:{spec.gid}",
        "--read-only",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges:true",
        f"--security-opt=seccomp={seccomp_profile}",
        "--pids-limit", str(spec.pids_limit),
        "--memory", str(spec.memory_limit_bytes),
        "--cpus", cpu_count,
        "--ipc=private",
        "--pid=private",
        "--uts=private",
        "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=64m",
        "--tmpfs", "/run:rw,noexec,nosuid,nodev,size=16m",
        "--label", "apaa.managed=true",
        "--label", f"apaa.launch-spec-digest={spec.digest}",
        "--hostname", name,
        "--init",
        image,
    )
    return OCIWorkerPlan(
        runtime=runtime,
        container_name=name,
        image=image,
        create_argv=create,
        inspect_argv=(runtime, "inspect", name),
        start_argv=(runtime, "start", name),
        stop_argv=(runtime, "stop", "--time", "2", name),
        remove_argv=(runtime, "rm", "--force", name),
        launch_spec_digest=spec.digest,
        network_name=network_name,
        seccomp_profile=seccomp_profile,
    )
