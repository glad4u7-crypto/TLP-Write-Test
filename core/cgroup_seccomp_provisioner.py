"""Cgroup v2 limits and deny-by-default seccomp preflight for APAA workers."""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re


class IsolationEnforcementError(RuntimeError):
    pass


_NAME = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")
_ALLOWED_DEFAULT_ACTIONS = {"SCMP_ACT_ERRNO", "SCMP_ACT_KILL", "SCMP_ACT_KILL_PROCESS"}
_CGROUP_ROOT = Path("/sys/fs/cgroup")


@dataclass(frozen=True)
class CgroupLimits:
    memory_max: int = 1_073_741_824
    cpu_quota: int = 100_000
    cpu_period: int = 100_000
    pids_max: int = 128

    def __post_init__(self):
        if type(self.memory_max) is not int or not 64 * 1024 * 1024 <= self.memory_max <= 8 * 1024**3:
            raise ValueError("memory_max is outside supported bounds")
        if type(self.cpu_quota) is not int or not 10_000 <= self.cpu_quota <= 800_000:
            raise ValueError("cpu_quota is outside supported bounds")
        if type(self.cpu_period) is not int or not 10_000 <= self.cpu_period <= 1_000_000:
            raise ValueError("cpu_period is outside supported bounds")
        if type(self.pids_max) is not int or not 16 <= self.pids_max <= 512:
            raise ValueError("pids_max is outside supported bounds")


class CgroupV2Provisioner:
    """Creates a bounded parent cgroup for Podman below an explicitly delegated subtree."""

    def __init__(self, delegated_root: str = "/sys/fs/cgroup/apaa"):
        root = Path(delegated_root)
        if not root.is_absolute() or ".." in root.parts or root == _CGROUP_ROOT:
            raise ValueError("a dedicated delegated cgroup-v2 subtree is required")
        self.root = root

    def _verified_root(self) -> Path:
        try:
            resolved_root = self.root.resolve(strict=True)
            resolved_cgroup_root = _CGROUP_ROOT.resolve(strict=True)
        except OSError as exc:
            raise IsolationEnforcementError("delegated cgroup subtree is unavailable") from exc
        if (self.root != resolved_root or not resolved_root.is_relative_to(resolved_cgroup_root)
                or resolved_root == resolved_cgroup_root):
            raise IsolationEnforcementError("delegated cgroup subtree escapes the cgroup v2 mount")
        if not (_CGROUP_ROOT / "cgroup.controllers").is_file():
            raise IsolationEnforcementError("unified cgroup v2 is required")
        return resolved_root

    def create(self, worker_id: str, limits: CgroupLimits = CgroupLimits()) -> Path:
        if type(worker_id) is not str or not _NAME.fullmatch(worker_id):
            raise ValueError("invalid worker_id")
        root = self._verified_root()
        try:
            available = set((root / "cgroup.controllers").read_text(encoding="ascii").split())
            enabled = set((root / "cgroup.subtree_control").read_text(encoding="ascii").split())
        except OSError as exc:
            raise IsolationEnforcementError("delegated cgroup controllers cannot be inspected") from exc
        required = {"cpu", "memory", "pids"}
        if not required.issubset(available) or not required.issubset(enabled):
            raise IsolationEnforcementError("cpu, memory and pids controllers must be delegated and enabled")
        target = root / worker_id
        try:
            target.mkdir(mode=0o700, parents=False, exist_ok=False)
            target_available = set((target / "cgroup.controllers").read_text(encoding="ascii").split())
            if not required.issubset(target_available):
                raise IsolationEnforcementError("worker parent does not expose cpu, memory and pids controllers")
            # Delegate controllers to the OCI child cgroup. Without this,
            # Podman can report a libpod child membership while no matching
            # leaf cgroup exists and no effective per-container limits apply.
            (target / "cgroup.subtree_control").write_text("+cpu +memory +pids", encoding="ascii")
            target_enabled = set((target / "cgroup.subtree_control").read_text(encoding="ascii").split())
            if not required.issubset(target_enabled):
                raise IsolationEnforcementError("worker parent did not enable controllers for its OCI child")
            (target / "memory.max").write_text(str(limits.memory_max), encoding="ascii")
            (target / "cpu.max").write_text(f"{limits.cpu_quota} {limits.cpu_period}", encoding="ascii")
            (target / "pids.max").write_text(str(limits.pids_max), encoding="ascii")
            self._verify(target, limits)
        except Exception as exc:
            try:
                target.rmdir()
            except OSError:
                pass
            if isinstance(exc, (ValueError, IsolationEnforcementError)):
                raise
            raise IsolationEnforcementError("cgroup limit provisioning failed") from exc
        return target

    def attach(self, cgroup_path: str | Path, pid: int) -> None:
        root = self._verified_root()
        path = Path(cgroup_path)
        if (not path.is_absolute() or path.is_symlink() or path.resolve(strict=True) != path
                or path.parent.resolve(strict=True) != root or not _NAME.fullmatch(path.name)):
            raise ValueError("cgroup path is outside the delegated worker subtree")
        if type(pid) is not int or pid <= 1:
            raise ValueError("worker PID is invalid")
        try:
            (path / "cgroup.procs").write_text(str(pid), encoding="ascii")
        except OSError as exc:
            raise IsolationEnforcementError("worker could not be attached to its cgroup") from exc

    def remove(self, cgroup_path: str | Path) -> None:
        root = self._verified_root()
        path = Path(cgroup_path)
        if (not path.is_absolute() or path.is_symlink() or path.resolve(strict=True) != path
                or path.parent.resolve(strict=True) != root or not _NAME.fullmatch(path.name)):
            raise ValueError("cgroup path is outside the delegated worker subtree")
        try:
            if (path / "cgroup.procs").read_text(encoding="ascii").strip():
                raise IsolationEnforcementError("worker cgroup still contains processes")
            path.rmdir()
        except OSError as exc:
            raise IsolationEnforcementError("worker cgroup cleanup failed or still has children") from exc

    @staticmethod
    def _verify(path: Path, limits: CgroupLimits) -> None:
        expected = {
            "memory.max": str(limits.memory_max),
            "cpu.max": f"{limits.cpu_quota} {limits.cpu_period}",
            "pids.max": str(limits.pids_max),
        }
        for filename, value in expected.items():
            if (path / filename).read_text(encoding="ascii").strip() != value:
                raise IsolationEnforcementError("kernel did not retain the requested cgroup limit")
        enabled = set((path / "cgroup.subtree_control").read_text(encoding="ascii").split())
        if not {"cpu", "memory", "pids"}.issubset(enabled):
            raise IsolationEnforcementError("worker parent has not delegated controllers to its OCI child")


def validate_seccomp_profile(profile_path: str | Path) -> dict:
    """Reject permissive or malformed seccomp profiles before OCI create."""
    path = Path(profile_path)
    if (not path.is_absolute() or ".." in path.parts or path.is_symlink()
            or not path.is_file() or path.resolve(strict=True) != path):
        raise IsolationEnforcementError("seccomp profile must be an existing regular absolute file without symlinks")
    try:
        profile = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise IsolationEnforcementError("seccomp profile is unreadable or invalid JSON") from exc
    if not isinstance(profile, dict) or profile.get("defaultAction") not in _ALLOWED_DEFAULT_ACTIONS:
        raise IsolationEnforcementError("seccomp default action must deny unknown system calls")
    syscalls = profile.get("syscalls")
    if not isinstance(syscalls, list) or not syscalls:
        raise IsolationEnforcementError("seccomp profile must contain explicit syscall rules")
    for rule in syscalls:
        if not isinstance(rule, dict) or rule.get("action") not in _ALLOWED_DEFAULT_ACTIONS | {"SCMP_ACT_ALLOW"}:
            raise IsolationEnforcementError("seccomp profile contains an invalid syscall action")
        names = rule.get("names")
        if not isinstance(names, list) or not names or any(type(name) is not str or not re.fullmatch(r"[a-z0-9_]{1,64}", name) for name in names):
            raise IsolationEnforcementError("seccomp syscall names are invalid")
    return profile
