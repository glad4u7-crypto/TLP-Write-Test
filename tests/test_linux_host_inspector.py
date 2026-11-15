import subprocess
from types import SimpleNamespace

import pytest

from core.browser_nftables import HostCollectionError
from core.linux_host_inspector import LinuxHostInspectorAdapter


def make_adapter(tmp_path):
    proc = tmp_path / "proc"
    target = proc / "43210"
    (target / "ns").mkdir(parents=True)
    (target / "net").mkdir()
    (target / "ns" / "net").write_text("namespace handle", encoding="ascii")
    (target / "net" / "dev").write_text(
        "Inter-| Receive | Transmit\n"
        " face |bytes packets errs drop fifo frame compressed multicast|bytes packets errs drop fifo colls carrier compressed\n"
        "    lo: 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0\n"
        "  eth0: 1 2 0 0 0 0 0 0 3 4 0 0 0 0 0 0\n",
        encoding="ascii",
    )
    nsenter = tmp_path / "nsenter"
    nft = tmp_path / "nft"
    for binary in (nsenter, nft):
        binary.write_text("#!/bin/sh\nexit 0\n", encoding="ascii")
        binary.chmod(0o755)
    return LinuxHostInspectorAdapter(
        runtime_attestation_reader=lambda: {"schema_version": 1},
        runtime_id="runtime:test-001",
        worker_id="worker:test-001",
        worker_pid=43210,
        proc_root=str(proc),
        nsenter_path=str(nsenter),
        nft_path=str(nft),
    ), nsenter, nft


def test_reads_only_target_namespace_identity_and_single_worker_interface(tmp_path):
    adapter, _, _ = make_adapter(tmp_path)
    result = adapter.read_network_namespace_identity()
    assert result["runtime_id"] == "runtime:test-001"
    assert result["worker_id"] == "worker:test-001"
    assert result["inode"] > 0
    assert result["interface"] == "eth0"


def test_runtime_attestation_is_read_from_trusted_injected_source(tmp_path):
    adapter, _, _ = make_adapter(tmp_path)
    assert adapter.read_runtime_attestation() == {"schema_version": 1}


def test_nftables_command_is_fixed_read_only_no_shell_and_namespace_scoped(tmp_path, monkeypatch):
    adapter, nsenter, nft = make_adapter(tmp_path)
    observed = {}

    def fake_run(command, **kwargs):
        observed["command"] = command
        observed["kwargs"] = kwargs
        return SimpleNamespace(returncode=0, stdout='{"nftables": []}', stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert adapter.read_nftables_json() == '{"nftables": []}'
    assert observed["command"] == [
        str(nsenter.resolve()), "--target", "43210", "--net", "--",
        str(nft.resolve()), "-j", "list", "ruleset",
    ]
    assert observed["kwargs"]["shell"] is False
    assert observed["kwargs"]["stdin"] == subprocess.DEVNULL
    assert observed["kwargs"]["timeout"] == 5
    assert observed["kwargs"]["close_fds"] is True


def test_rejects_multiple_non_loopback_interfaces(tmp_path):
    adapter, _, _ = make_adapter(tmp_path)
    dev = tmp_path / "proc" / "43210" / "net" / "dev"
    dev.write_text(
        "header one\nheader two\n eth0: 0\n eth1: 0\n",
        encoding="ascii",
    )
    with pytest.raises(HostCollectionError):
        adapter.read_network_namespace_identity()


def test_rejects_invalid_pid_and_missing_inspection_binary(tmp_path):
    with pytest.raises(HostCollectionError):
        LinuxHostInspectorAdapter(
            runtime_attestation_reader=lambda: {},
            runtime_id="runtime:test-001", worker_id="worker:test-001",
            worker_pid=1, proc_root=str(tmp_path),
            nsenter_path="/missing/nsenter", nft_path="/missing/nft",
        )


@pytest.mark.parametrize("result", [
    SimpleNamespace(returncode=1, stdout="", stderr="sensitive host detail"),
    SimpleNamespace(returncode=0, stdout="", stderr=""),
    SimpleNamespace(returncode=0, stdout="x" * 1_048_577, stderr=""),
])
def test_fails_closed_on_nftables_command_failure_or_oversize(tmp_path, monkeypatch, result):
    adapter, _, _ = make_adapter(tmp_path)
    monkeypatch.setattr(subprocess, "run", lambda *_args, **_kwargs: result)
    with pytest.raises(HostCollectionError):
        adapter.read_nftables_json()


def test_fails_closed_on_command_timeout(tmp_path, monkeypatch):
    adapter, _, _ = make_adapter(tmp_path)

    def timeout(*_args, **_kwargs):
        raise subprocess.TimeoutExpired("nft", 5)

    monkeypatch.setattr(subprocess, "run", timeout)
    with pytest.raises(HostCollectionError):
        adapter.read_nftables_json()
