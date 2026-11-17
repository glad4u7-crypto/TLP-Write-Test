"""Read-only, bounded Chromium worker FD snapshots from a cgroup-v2 subtree.

The collector never opens or duplicates target descriptors. It reads procfs metadata
only and intentionally records sanitized target classes, not raw symlink targets.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
import time
from typing import Iterable

_MAX_LINE = 4096
_TARGET_CLASSES = (
    ("pipe:[", "pipe"),
    ("socket:[", "socket"),
    ("anon_inode:[eventfd]", "eventfd"),
    ("anon_inode:[eventpoll]", "eventpoll"),
    ("anon_inode:[timerfd]", "timerfd"),
    ("anon_inode:", "anon_inode"),
    ("/memfd:", "memfd"),
    ("memfd:", "memfd"),
)


def _read_text(path: Path, limit: int = _MAX_LINE) -> str | None:
    try:
        with path.open("r", encoding="utf-8", errors="replace") as stream:
            return stream.read(limit)
    except (OSError, ValueError):
        return None


def _proc_stat_identity(raw: str) -> tuple[str, int, int] | None:
    """Return (comm, state, ppid); comm may itself contain spaces/parentheses."""
    left = raw.find("(")
    right = raw.rfind(")")
    if left < 0 or right <= left:
        return None
    comm = raw[left + 1:right][:256]
    fields = raw[right + 1:].strip().split()
    # fields[0] is stat field 3 (state), fields[1] is stat field 4 (ppid).
    if len(fields) < 2 or len(fields[0]) != 1 or not fields[1].isdigit():
        return None
    return comm, ord(fields[0]), int(fields[1])


def _target_class(target: str) -> str:
    for prefix, label in _TARGET_CLASSES:
        if target.startswith(prefix):
            return label
    if target.startswith("/"):
        return "filesystem"
    return "other"


def _fd_metadata(pid_dir: Path, fd_name: str) -> dict | None:
    if not fd_name.isdigit():
        return None
    fd_path = pid_dir / "fd" / fd_name
    try:
        target = os.readlink(fd_path)
        st = os.stat(fd_path)
    except (OSError, ValueError):
        # FD may legitimately disappear between readdir/readlink/stat.
        return None
    info = _read_text(pid_dir / "fdinfo" / fd_name, 2048) or ""
    fields: dict[str, str] = {}
    for line in info.splitlines():
        key, sep, value = line.partition(":")
        if sep and key in {"pos", "flags", "mnt_id", "ino"}:
            fields[key] = value.strip()[:64]
    flags = None
    if "flags" in fields:
        try:
            flags = int(fields["flags"], 8)
        except ValueError:
            flags = None
    return {
        "fd": int(fd_name),
        "target_class": _target_class(target),
        "device": int(st.st_dev),
        "inode": int(st.st_ino),
        "mode": int(st.st_mode),
        "fdinfo": fields,
        "status_flags_octal": format(flags, "o") if flags is not None else None,
        # FD_CLOEXEC belongs to the descriptor table and is not reliably
        # exposed by /proc/<pid>/fdinfo; never infer it from file status flags.
        "close_on_exec": "not_observable_via_fdinfo",
    }


def _executable_mappings(base: Path, executable: str | None) -> list[dict]:
    """Capture sanitized address ranges for the process executable only."""
    raw = _read_text(base / "maps", 262144) or ""
    mappings = []
    for line in raw.splitlines():
        fields = line.split(maxsplit=5)
        if len(fields) < 5:
            continue
        path = fields[5].removesuffix(" (deleted)") if len(fields) == 6 else ""
        if not path.startswith("/") or "x" not in fields[1]:
            continue
        start_end = fields[0].split("-", 1)
        try:
            start, end = int(start_end[0], 16), int(start_end[1], 16)
            file_offset = int(fields[2], 16)
            device = fields[3]
            inode = int(fields[4])
        except (ValueError, IndexError):
            continue
        mappings.append({
            "start": hex(start),
            "end": hex(end),
            "file_offset": hex(file_offset),
            "permissions": fields[1],
            "device": device,
            "inode": inode,
            "module": Path(path).name,
        })
        if len(mappings) >= 48:
            break
    return mappings


def _parse_status(raw: str) -> dict:
    wanted = {"Uid", "Gid", "NSpid", "Seccomp", "FDSize"}
    out: dict[str, str] = {}
    for line in raw.splitlines():
        key, sep, value = line.partition(":")
        if sep and key in wanted:
            out[key.lower()] = " ".join(value.split())[:128]
    return out


def _process_role(cmdline: bytes) -> str:
    """Classify Chromium process role without retaining command-line values."""
    tokens = [part.decode("utf-8", errors="ignore") for part in cmdline.split(b"\\0") if part]
    if "--type=zygote" in tokens:
        return "zygote"
    if "--type=renderer" in tokens:
        return "renderer"
    if "--type=gpu-process" in tokens:
        return "gpu"
    if "--utility-sub-type=network.mojom.NetworkService" in tokens:
        return "network-service"
    if "--type=utility" in tokens:
        return "utility"
    if any(token.endswith("/chromium") or token.endswith("/chrome") for token in tokens[:1]):
        return "browser-or-launcher"
    return "other"


def _read_process(
    pid: int, proc_root: Path, max_fds_per_process: int,
    expected_cgroup_prefix: str | None = None,
) -> dict | None:
    base = proc_root / str(pid)
    stat_raw = _read_text(base / "stat")
    if stat_raw is None:
        return None
    identity = _proc_stat_identity(stat_raw)
    if identity is None:
        return None
    comm, state_code, ppid = identity
    if expected_cgroup_prefix is not None:
        membership = _read_text(base / "cgroup", 4096) or ""
        unified = next((line.partition("::")[2].strip() for line in membership.splitlines()
                        if line.startswith("0::")), None)
        if unified is None or not (
            unified == expected_cgroup_prefix
            or unified.startswith(expected_cgroup_prefix.rstrip("/") + "/")
        ):
            return None
    try:
        executable = Path(os.readlink(base / "exe")).name[:128]
    except OSError:
        executable = None
    cmdline = b""
    try:
        with (base / "cmdline").open("rb") as stream:
            cmdline = stream.read(8192)
    except OSError:
        pass
    role = _process_role(cmdline)
    status = _parse_status(_read_text(base / "status") or "")
    try:
        fd_names = sorted(
            (name for name in os.listdir(base / "fd") if name.isdigit()),
            key=int,
        )[:max_fds_per_process]
    except OSError:
        fd_names = []
    descriptors = []
    for name in fd_names:
        item = _fd_metadata(base, name)
        if item is not None:
            descriptors.append(item)
    try:
        start_time = (_read_text(base / "stat") or "").rsplit(")", 1)[1].split()[19]
    except (IndexError, AttributeError):
        start_time = None
    return {
        "pid": pid,
        "ppid": ppid,
        "comm": comm,
        "executable": executable,
        "role": role,
        "executable_mappings": _executable_mappings(base, executable),
        "state_code": state_code,
        "start_time_ticks": start_time,
        "status": status,
        "fd_count_observed": len(descriptors),
        "fd_limit_reached": len(fd_names) >= max_fds_per_process,
        "fds": descriptors,
    }


def _cgroup_pids(cgroup_dir: Path, max_processes: int) -> list[int]:
    pids: set[int] = set()
    pending = [cgroup_dir]
    visited = 0
    while pending and visited < 256 and len(pids) < max_processes:
        current = pending.pop()
        visited += 1
        raw = _read_text(current / "cgroup.procs", 65536) or ""
        for token in raw.split():
            if token.isdigit() and int(token) > 1:
                pids.add(int(token))
                if len(pids) >= max_processes:
                    break
        try:
            children = [p for p in current.iterdir() if p.is_dir() and not p.is_symlink()]
        except OSError:
            children = []
        pending.extend(children[:64])
    return sorted(pids)[:max_processes]


def snapshot_cgroup(
    cgroup_dir: str | os.PathLike[str],
    *,
    proc_root: str | os.PathLike[str] = "/proc",
    max_processes: int = 128,
    max_fds_per_process: int = 512,
) -> dict:
    """Take one bounded metadata-only snapshot of all processes in cgroup subtree."""
    if type(max_processes) is not int or not 1 <= max_processes <= 512:
        raise ValueError("max_processes must be between 1 and 512")
    if type(max_fds_per_process) is not int or not 1 <= max_fds_per_process <= 2048:
        raise ValueError("max_fds_per_process must be between 1 and 2048")
    root = Path(cgroup_dir)
    if not root.is_absolute() or ".." in root.parts or root.is_symlink() or not root.is_dir():
        raise ValueError("cgroup_dir must be an existing absolute directory")
    proc = Path(proc_root)
    expected_cgroup_prefix = None
    if proc == Path("/proc"):
        mount = Path("/sys/fs/cgroup").resolve()
        try:
            expected_cgroup_prefix = "/" + root.resolve().relative_to(mount).as_posix().strip("/")
        except ValueError:
            raise ValueError("production cgroup must be beneath /sys/fs/cgroup")
    pids = _cgroup_pids(root, max_processes)
    processes = []
    for pid in pids:
        process = _read_process(pid, proc, max_fds_per_process, expected_cgroup_prefix)
        if process is not None:
            processes.append(process)
    by_pid = {process["pid"]: process for process in processes}
    kernel_object_classes = {
        "pipe", "socket", "eventfd", "eventpoll", "timerfd", "anon_inode", "memfd",
    }
    inherited_candidates = []
    for child in processes:
        parent = by_pid.get(child["ppid"])
        if parent is None:
            continue
        parent_fds = {
            (fd["target_class"], fd["device"], fd["inode"]): fd["fd"]
            for fd in parent["fds"] if fd["target_class"] in kernel_object_classes
        }
        for fd in child["fds"]:
            if fd["target_class"] not in kernel_object_classes:
                continue
            key = (fd["target_class"], fd["device"], fd["inode"])
            parent_fd = parent_fds.get(key)
            if parent_fd is not None:
                inherited_candidates.append({
                    "parent_pid": parent["pid"],
                    "parent_role": parent["role"],
                    "parent_fd": parent_fd,
                    "child_pid": child["pid"],
                    "child_role": child["role"],
                    "child_fd": fd["fd"],
                    "target_class": fd["target_class"],
                    "device": fd["device"],
                    "inode": fd["inode"],
                    "same_fd_number": parent_fd == fd["fd"],
                    "interpretation": "shared_kernel_object_candidate_not_proof_of_inheritance",
                })
    return {
        "monotonic_time_ns": time.monotonic_ns(),
        "wall_time_ns": time.time_ns(),
        "process_count_observed": len(processes),
        "process_limit_reached": len(pids) >= max_processes,
        "fd_limit_per_process": max_fds_per_process,
        "parent_child_fd_candidates": inherited_candidates[:2048],
        "processes": processes,
    }


def snapshot_json_safe(snapshot: dict, *, max_bytes: int = 1_000_000) -> dict:
    """Validate bounded JSON-safe collector output; does not add raw procfs paths."""
    import json
    if type(max_bytes) is not int or not 1024 <= max_bytes <= 4_000_000:
        raise ValueError("max_bytes must be between 1024 and 4000000")
    encoded = json.dumps(snapshot, sort_keys=True, separators=(",", ":"))
    if len(encoded.encode("utf-8")) > max_bytes:
        raise ValueError("FD snapshot exceeds the configured evidence size bound")
    return snapshot
