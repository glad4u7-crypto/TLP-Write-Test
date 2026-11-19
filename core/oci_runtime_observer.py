"""Read-only Podman/procfs/cgroup observer for isolated APAA workers."""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
from typing import Any

from core.oci_runtime_backend import OCIWorkerSpec, PodmanOCIRuntime, WorkerLimits


class WorkerObservationError(RuntimeError):
    """Runtime state cannot be independently confirmed."""


@dataclass(frozen=True)
class WorkerObservation:
    container_id: str
    host_pid: int
    process_start_time_ticks: int
    network_namespace_inode: int
    cgroup_path: str
    memory_max: str
    cpu_max: str
    pids_max: str
    seccomp_mode: int
    image_id: str


class PodmanWorkerObserver:
    """Cross-check independent runtime/kernel observations against an immutable spec."""

    def __init__(
        self,
        runtime: PodmanOCIRuntime,
        *,
        proc_root: str | Path = "/proc",
        cgroup_root: str | Path = "/sys/fs/cgroup",
        namespace_root: str | Path = "/run/netns",
    ) -> None:
        if not callable(getattr(runtime, "inspect", None)):
            raise TypeError("runtime must expose a trusted inspect(container_id) operation")
        self.runtime = runtime
        self.proc_root = Path(proc_root)
        self.cgroup_root = Path(cgroup_root)
        self.namespace_root = Path(namespace_root)

    @staticmethod
    def _start_time(stat_text: str) -> int:
        if type(stat_text) is not str:
            raise WorkerObservationError("proc stat is malformed")
        closing = stat_text.rfind(")")
        if closing < 0:
            raise WorkerObservationError("proc stat has no process-name terminator")
        fields = stat_text[closing + 1:].split()
        # The first token after comm is field 3 (state); starttime is field 22.
        if len(fields) <= 19 or not fields[19].isdigit():
            raise WorkerObservationError("proc start-time field is missing")
        return int(fields[19])

    @staticmethod
    def _unified_cgroup(cgroup_text: str) -> str:
        if type(cgroup_text) is not str:
            raise WorkerObservationError("proc cgroup data is malformed")
        matches = []
        for line in cgroup_text.splitlines():
            parts = line.split(":", 2)
            if len(parts) == 3 and parts[0] == "0" and parts[1] == "":
                matches.append(parts[2])
        if len(matches) != 1:
            raise WorkerObservationError("exactly one unified cgroup-v2 membership is required")
        value = matches[0]
        if not value.startswith("/") or ".." in Path(value).parts:
            raise WorkerObservationError("unified cgroup path is unsafe")
        return value

    @staticmethod
    def _locate_pid_cgroup(parent: Path, pid: int, mount_root: Path) -> tuple[Path, str]:
        """Find the unique cgroup-v2 directory that actually lists this host PID."""
        matches: list[Path] = []
        visited = 0
        parent_real = parent.resolve(strict=True)
        for current, dirs, _files in os.walk(parent_real, topdown=True, followlinks=False):
            current_path = Path(current)
            dirs[:] = [
                name for name in dirs
                if not (current_path / name).is_symlink()
            ]
            visited += 1
            if visited > 4096 or len(current_path.relative_to(parent_real).parts) > 8:
                raise WorkerObservationError("dedicated cgroup subtree exceeds safe inspection bounds")
            procs = current_path / "cgroup.procs"
            try:
                entries = procs.read_text(encoding="ascii").split()
            except OSError as exc:
                raise WorkerObservationError("cgroup.procs cannot be read within the dedicated subtree") from exc
            if str(pid) in entries:
                matches.append(current_path)
                if len(matches) > 1:
                    raise WorkerObservationError("worker PID appears in multiple cgroup-v2 directories")
        if len(matches) != 1:
            raise WorkerObservationError("worker PID is not uniquely present in the dedicated cgroup-v2 subtree")
        actual = matches[0]
        if not actual.is_relative_to(mount_root.resolve(strict=True)):
            raise WorkerObservationError("located worker cgroup escapes the cgroup-v2 mount")
        return actual, "/" + str(actual.relative_to(mount_root.resolve(strict=True))).strip("/")

    def _normalize_cgroup_mount_path(self, value: str) -> str:
        """Normalize procfs paths that include the cgroup-v2 mount prefix."""
        try:
            mount = str(self.cgroup_root.resolve(strict=True)).rstrip("/")
        except OSError as exc:
            raise WorkerObservationError("cgroup-v2 mount root is unavailable") from exc
        if value == mount:
            return "/"
        if value.startswith(mount + "/"):
            return value[len(mount):]
        return value

    @staticmethod
    def _read(path: Path) -> str:
        try:
            return path.read_text(encoding="ascii").strip()
        except OSError as exc:
            raise WorkerObservationError("required kernel observation is unavailable") from exc

    def observe(self, container_id: str, spec: OCIWorkerSpec) -> WorkerObservation:
        if not isinstance(spec, OCIWorkerSpec):
            raise TypeError("spec must be OCIWorkerSpec")
        # Runtime.inspect validates the immutable 64-hex ID and returned identity.
        inspected = self.runtime.inspect(container_id)
        host = inspected.get("HostConfig") or {}
        config = inspected.get("Config") or {}
        state = inspected.get("State") or {}
        security = host.get("SecurityOpt") or []
        cap_drop = host.get("CapDrop")
        cap_add = host.get("CapAdd") or []
        if (not host.get("ReadonlyRootfs")
                or not isinstance(cap_drop, list) or not cap_drop
                or len(cap_drop) != len(set(cap_drop))
                or any(type(item) is not str or not re.fullmatch(r"CAP_[A-Z0-9_]+", item) for item in cap_drop)
                or cap_add
                or not any(x == "no-new-privileges" or x.startswith("no-new-privileges=") for x in security)
                or f"seccomp={spec.seccomp_profile}" not in security):
            raise WorkerObservationError("OCI security options differ from the required worker profile")
        expected_cpu_nanos = int(spec.limits.cpu_count * 1_000_000_000)
        if (host.get("Memory") != spec.limits.memory_bytes
                or host.get("PidsLimit") != spec.limits.pids_limit
                or host.get("NanoCpus") != expected_cpu_nanos):
            raise WorkerObservationError("OCI resource limits differ from the immutable worker spec")
        if config.get("User") != f"{spec.uid}:{spec.gid}":
            raise WorkerObservationError("OCI worker UID/GID differs from the immutable worker spec")
        expected_network = f"ns:{spec.network_namespace}"
        if host.get("NetworkMode") != expected_network:
            raise WorkerObservationError("OCI worker network namespace differs from the requested namespace")
        if state.get("Running") is not True:
            raise WorkerObservationError("OCI worker is not confirmed running")
        pid = state.get("Pid")
        if type(pid) is not int or pid <= 1:
            raise WorkerObservationError("OCI runtime did not report a valid host PID")
        proc = self.proc_root / str(pid)
        try:
            start_before = self._start_time(self._read(proc / "stat"))
            net_inode = (proc / "ns" / "net").stat().st_ino
            namespace_inode = (self.namespace_root / Path(spec.network_namespace).name).stat().st_ino
            cgroup_path = self._normalize_cgroup_mount_path(
                self._unified_cgroup(self._read(proc / "cgroup"))
            )
            status = self._read(proc / "status")
            start_after = self._start_time(self._read(proc / "stat"))
        except OSError as exc:
            raise WorkerObservationError("host process identity could not be inspected") from exc
        if start_before != start_after:
            raise WorkerObservationError("host PID was reused during observation")
        if net_inode != namespace_inode:
            raise WorkerObservationError("worker process is outside the provisioned network namespace")
        parent = spec.cgroup_parent
        if not parent:
            raise WorkerObservationError("an explicit delegated cgroup parent is required")
        if type(parent) is not str or not parent.startswith("/apaa/") or ".." in Path(parent).parts:
            raise WorkerObservationError("cgroup parent must be a hierarchy path inside /apaa")
        # Podman --cgroup-parent takes a cgroup-hierarchy path, not the
        # filesystem mount path (/sys/fs/cgroup). Prove actual membership
        # from host cgroup.procs files rather than trusting procfs namespace paths.
        expected_parent = parent
        parent_dir = self.cgroup_root / expected_parent.lstrip("/")
        try:
            cgroup_dir, cgroup_path = self._locate_pid_cgroup(
                parent_dir, pid, self.cgroup_root
            )
        except OSError as exc:
            raise WorkerObservationError("dedicated worker cgroup subtree is unavailable") from exc
        memory = self._read(cgroup_dir / "memory.max")
        cpu = self._read(cgroup_dir / "cpu.max")
        pids = self._read(cgroup_dir / "pids.max")
        expected_cpu = f"{int(spec.limits.cpu_count * 100000)} 100000"
        if (memory != str(spec.limits.memory_bytes) or cpu != expected_cpu
                or pids != str(spec.limits.pids_limit)):
            raise WorkerObservationError("effective cgroup-v2 limits differ from the worker spec")
        seccomp_lines = [line for line in status.splitlines() if line.startswith("Seccomp:")]
        cap_eff_lines = [line for line in status.splitlines() if line.startswith("CapEff:")]
        if seccomp_lines != ["Seccomp:\t2"]:
            raise WorkerObservationError("kernel does not confirm active seccomp filtering")
        if len(cap_eff_lines) != 1:
            raise WorkerObservationError("kernel effective capability mask is missing or ambiguous")
        cap_eff = cap_eff_lines[0].split(":", 1)[1].strip()
        if not re.fullmatch(r"[0-9a-fA-F]+", cap_eff) or int(cap_eff, 16) != 0:
            raise WorkerObservationError("kernel reports effective Linux capabilities in the worker")
        image_id = inspected.get("Image")
        # Podman versions may expose the immutable local image ID either as
        # sha256:<hex> or as the bare 64-character digest. Normalize only that
        # exact representation; never accept a tag, short ID or mutable name.
        if type(image_id) is str and re.fullmatch(r"[0-9a-f]{64}", image_id):
            image_id = "sha256:" + image_id
        if type(image_id) is not str or not re.fullmatch(r"sha256:[0-9a-f]{64}", image_id):
            raise WorkerObservationError("OCI runtime did not report a canonical immutable image ID")
        if spec.image.startswith("sha256:") and image_id != spec.image:
            raise WorkerObservationError("running container image ID differs from the immutable worker spec")
        if "@sha256:" in spec.image:
            repo_digests = inspected.get("ImageDigest") or inspected.get("RepoDigests") or []
            if isinstance(repo_digests, str):
                repo_digests = [repo_digests]
            if spec.image not in repo_digests:
                raise WorkerObservationError("running container repository digest differs from the immutable worker spec")
        return WorkerObservation(
            container_id=container_id,
            host_pid=pid,
            process_start_time_ticks=start_before,
            network_namespace_inode=net_inode,
            cgroup_path=cgroup_path,
            memory_max=memory,
            cpu_max=cpu,
            pids_max=pids,
            seccomp_mode=2,
            image_id=image_id,
        )
