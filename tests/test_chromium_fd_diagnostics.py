from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from core.chromium_fd_diagnostics import (
    _proc_stat_identity,
    _process_role,
    _target_class,
    snapshot_cgroup,
    snapshot_json_safe,
)


def _stat(comm: str, state: str = "S", ppid: int = 1) -> str:
    # Linux /proc/PID/stat fields 3..; field 22 (starttime) is set to 12345.
    tail = [state, str(ppid)] + ["0"] * 17 + ["12345"] + ["0"] * 5
    return f"4242 ({comm}) " + " ".join(tail)


def _proc_fixture(tmp_path: Path, *, comm: str = "chrome (network)") -> tuple[Path, Path]:
    proc = tmp_path / "proc"
    cgroup = tmp_path / "cg"
    pdir = proc / "4242"
    (pdir / "fd").mkdir(parents=True)
    (pdir / "fdinfo").mkdir()
    cgroup.mkdir()
    (cgroup / "cgroup.procs").write_text("4242\n", encoding="ascii")
    (pdir / "stat").write_text(_stat(comm), encoding="ascii")
    (pdir / "status").write_text(
        "Name:\tchrome\nUid:\t65532\t65532\t65532\t65532\n"
        "Gid:\t65532\t65532\t65532\t65532\nNSpid:\t4242\nSeccomp:\t2\nFDSize:\t64\n",
        encoding="ascii",
    )
    (pdir / "fd" / "0").symlink_to("/dev/null")
    (pdir / "fdinfo" / "0").write_text("pos:\t0\nflags:\t02000000\nmnt_id:\t1\nino:\t5\n")
    (pdir / "fd" / "1").symlink_to("pipe:[12345]")
    (pdir / "fdinfo" / "1").write_text("pos:\t0\nflags:\t01\n")
    return proc, cgroup


def test_proc_stat_parser_handles_spaces_and_parentheses_in_comm():
    assert _proc_stat_identity(_stat("chrome (network)")) == ("chrome (network)", ord("S"), 1)


@pytest.mark.parametrize(
    ("target", "expected"),
    [
        ("pipe:[123]", "pipe"),
        ("socket:[456]", "socket"),
        ("anon_inode:[eventfd]", "eventfd"),
        ("anon_inode:[eventpoll]", "eventpoll"),
        ("anon_inode:[timerfd]", "timerfd"),
        ("anon_inode:[other]", "anon_inode"),
        ("/memfd:chromium", "memfd"),
        ("memfd:chromium", "memfd"),
        ("/tmp/profile", "filesystem"),
        ("unknown-target", "other"),
    ],
)
def test_target_class_is_sanitized(target, expected):
    assert _target_class(target) == expected


def test_snapshot_captures_process_and_sanitized_fd_metadata(tmp_path, monkeypatch):
    proc, cgroup = _proc_fixture(tmp_path)
    real_stat = os.stat\n    def fake_stat(path, *args, **kwargs):\n        if str(path).endswith("/fd/1"):\n            return real_stat("/dev/null")\n        return real_stat(path, *args, **kwargs)\n    monkeypatch.setattr("core.chromium_fd_diagnostics.os.stat", fake_stat)\n    result = snapshot_cgroup(cgroup, proc_root=proc)\n    assert result["process_count_observed"] == 1
    process = result["processes"][0]
    assert process["comm"] == "chrome (network)"
    assert process["ppid"] == 1
    assert process["status"]["uid"].startswith("65532")
    assert process["status"]["seccomp"] == "2"
    assert [fd["target_class"] for fd in process["fds"]] == ["filesystem", "pipe"]
    assert process["fds"][1]["inode"] > 0
    assert process["fds"][1]["close_on_exec"] == "not_observable_via_fdinfo"
    encoded = json.dumps(result)
    assert "pipe:[12345]" not in encoded
    assert "/dev/null" not in encoded


def test_missing_process_during_snapshot_is_tolerated(tmp_path):
    proc, cgroup = _proc_fixture(tmp_path)
    (cgroup / "cgroup.procs").write_text("4242\n9999\n", encoding="ascii")
    result = snapshot_cgroup(cgroup, proc_root=proc)
    assert result["process_count_observed"] == 1


def test_nested_cgroup_processes_are_included(tmp_path):
    proc, cgroup = _proc_fixture(tmp_path)
    nested = cgroup / "child"
    nested.mkdir()
    (nested / "cgroup.procs").write_text("5252\n", encoding="ascii")
    pdir = proc / "5252"
    (pdir / "fd").mkdir(parents=True)
    (pdir / "fdinfo").mkdir()
    (pdir / "stat").write_text(_stat("renderer", ppid=4242), encoding="ascii")
    (pdir / "status").write_text("Uid:\t65532\nGid:\t65532\n", encoding="ascii")
    assert [p["pid"] for p in snapshot_cgroup(cgroup, proc_root=proc)["processes"]] == [4242, 5252]


@pytest.mark.parametrize("kwargs", [
    {"max_processes": 0},
    {"max_processes": 513},
    {"max_fds_per_process": 0},
    {"max_fds_per_process": 2049},
])
def test_snapshot_bounds_are_enforced(tmp_path, kwargs):
    proc, cgroup = _proc_fixture(tmp_path)
    with pytest.raises(ValueError):
        snapshot_cgroup(cgroup, proc_root=proc, **kwargs)


def test_snapshot_rejects_relative_or_parent_traversal_cgroup(tmp_path):
    with pytest.raises(ValueError):
        snapshot_cgroup("relative/path")
    with pytest.raises(ValueError):
        snapshot_cgroup(tmp_path / "..")


def test_evidence_size_limit_is_enforced():
    with pytest.raises(ValueError):
        snapshot_json_safe({"x": "y" * 5000}, max_bytes=1024)


def test_fd_disappearing_between_listing_and_readlink_is_ignored(tmp_path):
    proc, cgroup = _proc_fixture(tmp_path)
    (proc / "4242" / "fd" / "1").unlink()
    result = snapshot_cgroup(cgroup, proc_root=proc)
    assert result["process_count_observed"] == 1
    assert len(result["processes"][0]["fds"]) == 1



@pytest.mark.parametrize(
    ("cmdline", "expected"),
    [
        (b"/usr/bin/chromium\\0--type=zygote\\0", "zygote"),
        (b"/usr/bin/chromium\\0--type=renderer\\0", "renderer"),
        (b"/usr/bin/chromium\\0--type=gpu-process\\0", "gpu"),
        (b"/usr/bin/chromium\\0--type=utility\\0--utility-sub-type=network.mojom.NetworkService\\0", "network-service"),
        (b"/usr/bin/chromium\\0--type=utility\\0", "utility"),
        (b"/usr/bin/chromium\\0", "browser-or-launcher"),
        (b"", "other"),
    ],
)
def test_chromium_role_classification_does_not_retain_argv(cmdline, expected):
    assert _process_role(cmdline) == expected


def test_production_snapshot_rejects_cgroup_outside_mount(tmp_path, monkeypatch):
    proc, cgroup = _proc_fixture(tmp_path)
    monkeypatch.setattr("core.chromium_fd_diagnostics.Path.resolve", lambda self: Path("/sys/fs/cgroup") if str(self) == "/sys/fs/cgroup" else Path("/tmp/outside"))
    with pytest.raises(ValueError, match="beneath /sys/fs/cgroup"):
        snapshot_cgroup(cgroup, proc_root="/proc")
