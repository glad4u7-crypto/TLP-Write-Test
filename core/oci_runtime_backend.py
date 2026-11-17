"""Fail-closed OCI lifecycle adapter for disposable APAA Chromium workers."""
from __future__ import annotations

from dataclasses import dataclass
import json
import re
import subprocess
from typing import Callable, Sequence


class OCIRuntimeError(RuntimeError):
    """Raised when an OCI operation fails or its result is untrustworthy."""


_CONTAINER_ID = re.compile(r"^[0-9a-f]{64}$")
_IMAGE_DIGEST = re.compile(r"^.+@sha256:[0-9a-f]{64}$")
_WORKER_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
_CGROUP_PARENT = re.compile(r"^/sys/fs/cgroup/apaa/[a-z][a-z0-9_-]{0,31}$")


@dataclass(frozen=True)
class WorkerLimits:
    memory_bytes: int = 1_073_741_824
    cpu_count: float = 1.0
    pids_limit: int = 128

    def __post_init__(self) -> None:
        if type(self.memory_bytes) is not int or not 64 * 1024 * 1024 <= self.memory_bytes <= 8 * 1024**3:
            raise ValueError("memory_bytes is outside the supported worker range")
        if type(self.cpu_count) not in (int, float) or not 0.1 <= self.cpu_count <= 8:
            raise ValueError("cpu_count is outside the supported worker range")
        if type(self.pids_limit) is not int or not 16 <= self.pids_limit <= 512:
            raise ValueError("pids_limit is outside the supported worker range")


@dataclass(frozen=True)
class OCIWorkerSpec:
    image: str
    network_namespace: str
    seccomp_profile: str
    worker_id: str
    limits: WorkerLimits = WorkerLimits()
    cgroup_parent: str | None = None

    def __post_init__(self) -> None:
        if not _IMAGE_DIGEST.fullmatch(self.image):
            raise ValueError("worker image must be pinned by sha256 digest")
        if not self.network_namespace.startswith("/run/netns/") or ".." in self.network_namespace.split("/"):
            raise ValueError("network namespace must be an absolute path under /run/netns")
        if not self.seccomp_profile.startswith("/") or ".." in self.seccomp_profile.split("/"):
            raise ValueError("seccomp profile must be an absolute normalized path")
        if not _WORKER_ID.fullmatch(self.worker_id):
            raise ValueError("worker_id is invalid")
        if self.cgroup_parent is not None and not _CGROUP_PARENT.fullmatch(self.cgroup_parent):
            raise ValueError("cgroup_parent must be inside the dedicated APAA cgroup subtree")


Runner = Callable[..., subprocess.CompletedProcess[str]]


class PodmanOCIRuntime:
    """Minimal Podman lifecycle; immutable IDs, digest references, no shell or pull."""

    def __init__(
        self,
        executable: str = "podman",
        *,
        timeout_seconds: int = 20,
        runner: Runner = subprocess.run,
    ) -> None:
        if not executable or "/" in executable or "\x00" in executable:
            raise ValueError("executable must be a command name")
        if type(timeout_seconds) is not int or not 1 <= timeout_seconds <= 120:
            raise ValueError("timeout_seconds is invalid")
        self._executable = executable
        self._timeout = timeout_seconds
        self._runner = runner

    def _run(self, args: Sequence[str], *, check: bool = True) -> str:
        try:
            result = self._runner(
                [self._executable, *args],
                check=False, capture_output=True, text=True,
                timeout=self._timeout, shell=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise OCIRuntimeError("OCI runtime command could not be completed") from exc
        if check and result.returncode != 0:
            raise OCIRuntimeError("OCI runtime command failed")
        return result.stdout.strip()

    def create(self, spec: OCIWorkerSpec) -> str:
        args = [
            "create", "--pull=never",
            "--name", f"apaa-{spec.worker_id}",
            "--label", f"org.apaa.worker={spec.worker_id}",
            "--network", f"ns:{spec.network_namespace}",
            "--read-only",
            "--tmpfs", "/tmp:rw,nosuid,nodev,size=256m",
            "--shm-size", "128m",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            "--security-opt", f"seccomp={spec.seccomp_profile}",
            "--memory", str(spec.limits.memory_bytes),
            "--cpus", str(spec.limits.cpu_count),
            "--pids-limit", str(spec.limits.pids_limit),
            "--user", "65532:65532",
        ]
        if spec.cgroup_parent:
            args.extend(["--cgroup-parent", spec.cgroup_parent])
        args.extend(["--entrypoint", "sleep", spec.image, "infinity"])
        output = self._run(args)
        container_id = output.splitlines()[-1] if output else ""
        if not _CONTAINER_ID.fullmatch(container_id):
            raise OCIRuntimeError("OCI create did not return a canonical immutable container ID")
        return container_id

    def inspect(self, container_id: str) -> dict:
        self._validate_id(container_id)
        output = self._run(["inspect", container_id])
        try:
            payload = json.loads(output)
        except (TypeError, json.JSONDecodeError) as exc:
            raise OCIRuntimeError("OCI inspect returned invalid JSON") from exc
        if not isinstance(payload, list) or len(payload) != 1 or not isinstance(payload[0], dict):
            raise OCIRuntimeError("OCI inspect returned an unexpected object shape")
        if payload[0].get("Id") != container_id:
            raise OCIRuntimeError("OCI inspect identity differs from the requested immutable container ID")
        return payload[0]

    def start(self, container_id: str) -> None:
        self._validate_id(container_id)
        self._run(["start", container_id])

    def stop(self, container_id: str, *, timeout_seconds: int = 5) -> None:
        self._validate_id(container_id)
        if type(timeout_seconds) is not int or not 1 <= timeout_seconds <= 30:
            raise ValueError("stop timeout is invalid")
        self._run(["stop", "--time", str(timeout_seconds), container_id])

    def remove(self, container_id: str) -> None:
        self._validate_id(container_id)
        self._run(["rm", "--force", container_id])

    @staticmethod
    def _validate_id(container_id: str) -> None:
        if type(container_id) is not str or not _CONTAINER_ID.fullmatch(container_id):
            raise ValueError("only a canonical immutable container ID is accepted")
