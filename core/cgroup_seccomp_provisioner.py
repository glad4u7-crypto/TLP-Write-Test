"""Cgroup v2 limits and strict seccomp-profile preflight for APAA workers."""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re


class IsolationEnforcementError(RuntimeError):
    pass


_NAME = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")
_ALLOWED_DEFAULT_ACTIONS = {"SCMP_ACT_ERRNO", "SCMP_ACT_KILL", "SCMP_ACT_KILL_PROCESS"}


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
    """Writes only within an explicitly delegated cgroup-v2 subtree."""

    def __init__(self, delegated_root: str = "/sys/fs/cgroup/apaa"):
        root = Path(delegated_root)
        if not root.is_absolute() or ".." in root.parts or root == Path("/sys/fs/cgroup"):
            raise ValueError("a dedicated delegated cgroup-v2 subtree is required")
        self.root = root

    def create(self, worker_id: str, limits: CgroupLimits = CgroupLimits()) -> Path:
        if not _NAME.fullmatch(worker_id):
            raise ValueError("invalid worker_id")
        if not (self.root / "cgroup.controllers").exists() and not self.root.exists():
            raise IsolationEnforcementError("delegated cgroup-v2 subtree is unavailable")
        if not Path("/sys/fs/cgroup/cgroup.controllers").exists():
            raise IsolationEnforcementError("unified cgroup v2 is required")
        target = self.root / worker_id
        try:
            target.mkdir(mode=0o700, parents=False, exist_ok=False)
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
        path = Path(cgroup_path)
        if path.parent != self.root or not _NAME.fullmatch(path.name):
            raise ValueError("cgroup path is outside the delegated worker subtree")
        if type(pid) is not int or pid <= 1:
            raise ValueError("worker PID is invalid")
        try:
            (path / "cgroup.procs").write_text(str(pid), encoding="ascii")
        except OSError as exc:
            raise IsolationEnforcementError("worker could not be attached to its cgroup") from exc

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


def validate_seccomp_profile(profile_path: str | Path) -> dict:
    """Reject permissive or malformed seccomp profiles before OCI create."""
    path = Path(profile_path)
    if not path.is_absolute() or ".." in path.parts or not path.is_file():
        raise IsolationEnforcementError("seccomp profile must be an existing absolute file")
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
