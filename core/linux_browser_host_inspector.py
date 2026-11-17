"""Read-only Linux host snapshot source for attested browser workers.

This adapter observes an already-created OCI worker. It does not create or
modify namespaces, containers, firewall rules, users, mounts or processes.
Runtime identity must come from a separately trusted OCI/runtime inspector.
nftables is queried inside the worker network namespace using fixed argv and
shell=False; missing tools, stale PID identity or ambiguous interfaces fail closed.
"""
from __future__ import annotations

from collections.abc import Mapping
import json
import os
from pathlib import Path
import subprocess
from typing import Any, Protocol, runtime_checkable

from core.browser_nftables import HostCollectionError, HostSnapshotSource


@runtime_checkable
class LinuxRuntimeObservationProvider(Protocol):
    """Trusted runtime API adapter; never implement this from worker-supplied data."""

    def read_runtime_attestation(self) -> Mapping[str, object]: ...
    def read_worker_process_identity(self) -> Mapping[str, object]:
        """Return exactly pid, runtime_id, worker_id and process_start_ticks."""


class LinuxHostSnapshotSource(HostSnapshotSource):
    """Observe one OCI worker's runtime, network namespace and effective nft rules."""

    def __init__(
        self,
        provider: LinuxRuntimeObservationProvider,
        *,
        proc_root: str | os.PathLike[str] = "/proc",
        nsenter_path: str = "/usr/bin/nsenter",
        nft_path: str = "/usr/sbin/nft",
        command_runner: Any = subprocess.run,
        command_timeout_seconds: float = 5.0,
        max_nft_output_bytes: int = 2_000_000,
    ) -> None:
        if not isinstance(provider, LinuxRuntimeObservationProvider):
            raise TypeError("A trusted LinuxRuntimeObservationProvider is required.")
        for name, path in (("nsenter_path", nsenter_path), ("nft_path", nft_path)):
            if type(path) is not str or not os.path.isabs(path):
                raise ValueError(f"{name} must be an absolute executable path.")
        if not callable(command_runner):
            raise TypeError("command_runner must be callable.")
        if isinstance(command_timeout_seconds, bool) or not isinstance(command_timeout_seconds, (int, float)) or not 0 < command_timeout_seconds <= 30:
            raise ValueError("command_timeout_seconds must be between 0 and 30.")
        if type(max_nft_output_bytes) is not int or not 1024 <= max_nft_output_bytes <= 8_000_000:
            raise ValueError("max_nft_output_bytes is outside the permitted range.")
        self._provider = provider
        self._proc_root = Path(proc_root)
        self._nsenter = nsenter_path
        self._nft = nft_path
        self._run = command_runner
        self._timeout = float(command_timeout_seconds)
        self._max_output = max_nft_output_bytes

    def read_runtime_attestation(self) -> Mapping[str, object]:
        raw = self._provider.read_runtime_attestation()
        if not isinstance(raw, Mapping) or any(type(key) is not str for key in raw):
            raise HostCollectionError("Runtime inspector returned a malformed attestation.")
        # Force JSON-only data before it crosses into the signed evidence layer.
        try:
            normalized = json.loads(json.dumps(dict(raw), allow_nan=False))
        except (TypeError, ValueError) as exc:
            raise HostCollectionError("Runtime attestation is not canonical JSON data.") from exc
        return normalized

    def _identity(self) -> tuple[int, str, str, int]:
        raw = self._provider.read_worker_process_identity()
        fields = {"pid", "runtime_id", "worker_id", "process_start_ticks"}
        if not isinstance(raw, Mapping) or set(raw) != fields:
            raise HostCollectionError("Runtime process identity has missing or unknown fields.")
        pid, runtime_id, worker_id, start_ticks = (
            raw["pid"], raw["runtime_id"], raw["worker_id"], raw["process_start_ticks"]
        )
        if type(pid) is not int or pid <= 1:
            raise HostCollectionError("Worker PID is invalid.")
        if type(runtime_id) is not str or type(worker_id) is not str:
            raise HostCollectionError("Worker runtime identity is malformed.")
        if type(start_ticks) is not int or start_ticks <= 0:
            raise HostCollectionError("Worker process start-time identity is invalid.")
        attestation = self.read_runtime_attestation()
        if attestation.get("runtime_id") != runtime_id or attestation.get("worker_id") != worker_id:
            raise HostCollectionError("Process identity does not match the runtime attestation.")
        if attestation.get("state") != "created" or attestation.get("process_started") is not False:
            raise HostCollectionError("Browser worker must remain in the created pre-start state.")
        return pid, runtime_id, worker_id, start_ticks

    def _proc_paths(self, pid: int) -> tuple[Path, Path, Path]:
        root = self._proc_root / str(pid)
        return root / "stat", root / "ns" / "net", root / "net" / "dev"

    def _observed_start_ticks(self, stat_path: Path) -> int:
        try:
            raw = stat_path.read_text(encoding="ascii")
            closing = raw.rfind(")")
            if closing < 0:
                raise ValueError("missing process command terminator")
            fields = raw[closing + 1 :].strip().split()
            # Remaining fields start at proc stat field 3 (state); starttime is field 22.
            value = int(fields[19])
            if value <= 0:
                raise ValueError("invalid start ticks")
            return value
        except (OSError, UnicodeError, ValueError, IndexError) as exc:
            raise HostCollectionError("Worker process identity could not be read from procfs.") from exc

    def _network_namespace(self, pid: int, expected_start_ticks: int) -> tuple[int, str]:
        stat_path, namespace_path, dev_path = self._proc_paths(pid)
        if self._observed_start_ticks(stat_path) != expected_start_ticks:
            raise HostCollectionError("Worker PID was reused or no longer identifies the attested process.")
        try:
            inode = namespace_path.stat().st_ino
            dev = dev_path.read_text(encoding="ascii")
        except OSError as exc:
            raise HostCollectionError("Worker network namespace could not be inspected.") from exc
        if type(inode) is not int or inode <= 0:
            raise HostCollectionError("Worker network namespace inode is invalid.")
        interfaces: list[str] = []
        for line in dev.splitlines()[2:]:
            if ":" not in line:
                continue
            name = line.split(":", 1)[0].strip()
            if name and name != "lo":
                interfaces.append(name)
        if len(interfaces) != 1:
            raise HostCollectionError("Worker must have exactly one non-loopback network interface.")
        return inode, interfaces[0]

    def read_network_namespace_identity(self) -> Mapping[str, object]:
        pid, runtime_id, worker_id, start_ticks = self._identity()
        inode, interface = self._network_namespace(pid, start_ticks)
        return {
            "runtime_id": runtime_id,
            "worker_id": worker_id,
            "inode": inode,
            "interface": interface,
        }

    def read_nftables_json(self) -> Mapping[str, object]:
        pid, _runtime_id, _worker_id, start_ticks = self._identity()
        inode_before, _interface_before = self._network_namespace(pid, start_ticks)
        argv = [
            self._nsenter, "--target", str(pid), "--net",
            self._nft, "-j", "list", "ruleset",
        ]
        try:
            completed = self._run(
                argv,
                shell=False,
                check=False,
                capture_output=True,
                text=True,
                stdin=subprocess.DEVNULL,
                timeout=self._timeout,
                env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C", "LC_ALL": "C"},
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise HostCollectionError("Read-only nftables inspection failed.") from exc
        if getattr(completed, "returncode", 1) != 0:
            raise HostCollectionError("nftables inspection returned a non-zero exit status.")
        output = getattr(completed, "stdout", None)
        if type(output) is not str or len(output.encode("utf-8")) > self._max_output:
            raise HostCollectionError("nftables output is missing or exceeds the size limit.")
        # Confirm PID and namespace identity did not change during inspection.
        pid_after, _runtime_after, _worker_after, ticks_after = self._identity()
        inode_after, _interface_after = self._network_namespace(pid_after, ticks_after)
        if pid_after != pid or ticks_after != start_ticks or inode_after != inode_before:
            raise HostCollectionError("Worker identity changed during nftables inspection.")
        try:
            parsed = json.loads(output)
        except json.JSONDecodeError as exc:
            raise HostCollectionError("nftables returned malformed JSON.") from exc
        if not isinstance(parsed, dict):
            raise HostCollectionError("nftables output must be a JSON object.")
        return parsed
