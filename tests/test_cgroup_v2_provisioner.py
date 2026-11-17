from pathlib import Path

import pytest

import core.cgroup_seccomp_provisioner as cgroups
from core.cgroup_seccomp_provisioner import (
    CgroupV2Provisioner,
    IsolationEnforcementError,
)


def fake_cgroupfs(tmp_path, monkeypatch, *, root_available="cpu memory pids",
                  root_enabled="cpu memory pids", child_available="cpu memory pids"):
    mount = tmp_path / "sys" / "fs" / "cgroup"
    delegated = mount / "apaa"
    delegated.mkdir(parents=True)
    (mount / "cgroup.controllers").write_text(root_available)
    (delegated / "cgroup.controllers").write_text(root_available)
    (delegated / "cgroup.subtree_control").write_text(root_enabled)
    (delegated / "cgroup.procs").write_text("")
    monkeypatch.setattr(cgroups, "_CGROUP_ROOT", mount)

    original_mkdir = Path.mkdir
    original_write_text = Path.write_text

    def mkdir(path, *args, **kwargs):
        result = original_mkdir(path, *args, **kwargs)
        if path.parent == delegated:
            (path / "cgroup.controllers").write_text(child_available)
            (path / "cgroup.subtree_control").write_text("")
            (path / "cgroup.procs").write_text("")
        return result

    def write_text(path, data, *args, **kwargs):
        if path.name == "cgroup.subtree_control" and str(data).startswith("+"):
            data = str(data).replace("+", "")
        return original_write_text(path, data, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", mkdir)
    monkeypatch.setattr(Path, "write_text", write_text)
    return mount, delegated


def test_create_enables_controllers_for_podman_child_and_applies_limits(tmp_path, monkeypatch):
    _, delegated = fake_cgroupfs(tmp_path, monkeypatch)
    path = CgroupV2Provisioner(str(delegated)).create("worker-one")
    assert path == delegated / "worker-one"
    assert set((path / "cgroup.subtree_control").read_text().split()) == {
        "cpu", "memory", "pids",
    }
    assert (path / "memory.max").read_text() == "1073741824"
    assert (path / "cpu.max").read_text() == "100000 100000"
    assert (path / "pids.max").read_text() == "128"


def test_create_fails_closed_when_root_controllers_are_not_delegated(tmp_path, monkeypatch):
    _, delegated = fake_cgroupfs(
        tmp_path, monkeypatch, root_available="cpu pids", root_enabled="cpu pids",
    )
    with pytest.raises(IsolationEnforcementError, match="must be delegated and enabled"):
        CgroupV2Provisioner(str(delegated)).create("worker-two")


def test_create_fails_closed_when_parent_cannot_delegate_child_controllers(tmp_path, monkeypatch):
    _, delegated = fake_cgroupfs(
        tmp_path, monkeypatch, child_available="cpu pids",
    )
    with pytest.raises(IsolationEnforcementError, match="does not expose"):
        CgroupV2Provisioner(str(delegated)).create("worker-three")


def test_remove_cleans_only_empty_nested_container_cgroups(tmp_path, monkeypatch):
    _, delegated = fake_cgroupfs(tmp_path, monkeypatch)
    provisioner = CgroupV2Provisioner(str(delegated))
    path = provisioner.create("worker-cleanup")
    child = path / "libpod-test"
    child.mkdir()
    (child / "cgroup.procs").write_text("")
    provisioner.remove(path)
    assert not path.exists()


def test_remove_refuses_nested_cgroup_with_live_process(tmp_path, monkeypatch):
    _, delegated = fake_cgroupfs(tmp_path, monkeypatch)
    provisioner = CgroupV2Provisioner(str(delegated))
    path = provisioner.create("worker-live")
    child = path / "libpod-test"
    child.mkdir()
    (child / "cgroup.procs").write_text("4321\n")
    with pytest.raises(IsolationEnforcementError, match="subtree still contains processes"):
        provisioner.remove(path)
    assert path.is_dir()
    assert child.is_dir()
