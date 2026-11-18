import json
import subprocess

import pytest

from core.browser_nftables import HostCollectionError
from core.linux_browser_host_inspector import LinuxHostSnapshotSource

PID = 4242
START_TICKS = 123456


class FakeRuntimeProvider:
    def __init__(self, *, pid=PID, start_ticks=START_TICKS, runtime_id="runtime:host-01", worker_id="worker:host-01", attestation_worker_id=None):
        self.pid, self.start_ticks = pid, start_ticks
        self.runtime_id, self.worker_id = runtime_id, worker_id
        self.attestation_worker_id = attestation_worker_id or worker_id

    def read_runtime_attestation(self):
        return {"runtime_id": self.runtime_id, "worker_id": self.attestation_worker_id,
                "state": "created", "process_started": False}

    def read_worker_process_identity(self):
        return {"pid": self.pid, "runtime_id": self.runtime_id,
                "worker_id": self.worker_id, "process_start_ticks": self.start_ticks}


def make_proc_tree(root, *, start_ticks=START_TICKS, interfaces=("lo", "eth0")):
    proc = root / str(PID)
    (proc / "ns").mkdir(parents=True)
    (proc / "net").mkdir()
    fields = ["S"] + ["0"] * 18 + [str(start_ticks)]
    (proc / "stat").write_text(f"{PID} (apaa-worker) " + " ".join(fields), encoding="ascii")
    (proc / "ns" / "net").write_text("net:[4026533001]", encoding="ascii")
    lines = ["Inter-| Receive | Transmit", " face |bytes packets errs drop fifo frame compressed multicast|bytes packets errs drop fifo colls carrier compressed"]
    lines.extend(f"{name}: 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0" for name in interfaces)
    (proc / "net" / "dev").write_text("\n".join(lines), encoding="ascii")


def nft_json():
    return {"nftables": [
        {"metainfo": {"version": "1.0.9"}},
        {"chain": {"family": "inet", "table": "filter", "name": "egress",
                   "type": "filter", "hook": "output", "prio": 0, "policy": "drop"}},
        {"rule": {"family": "inet", "table": "filter", "chain": "egress", "expr": [
            {"match": {"op": "==", "left": {"meta": {"key": "l4proto"}}, "right": "tcp"}},
            {"match": {"op": "==", "left": {"payload": {"protocol": "ip", "field": "daddr"}}, "right": "172.20.0.2"}},
            {"match": {"op": "==", "left": {"payload": {"protocol": "tcp", "field": "dport"}}, "right": 3128}},
            {"accept": None},
        ]}},
    ]}


def make_source(tmp_path, *, provider=None, runner=None, interfaces=("lo", "eth0")):
    make_proc_tree(tmp_path, interfaces=interfaces)
    calls = []
    def default_runner(argv, **kwargs):
        calls.append((argv, kwargs))
        return subprocess.CompletedProcess(argv, 0, json.dumps(nft_json()), "")
    source = LinuxHostSnapshotSource(
        provider or FakeRuntimeProvider(), proc_root=tmp_path,
        nsenter_path="/usr/bin/nsenter", nft_path="/usr/sbin/nft",
        command_runner=runner or default_runner,
    )
    return source, calls


def test_linux_source_reads_runtime_namespace_and_nftables_inside_worker_netns(tmp_path):
    source, calls = make_source(tmp_path)
    assert source.read_runtime_attestation()["runtime_id"] == "runtime:host-01"
    identity = source.read_network_namespace_identity()
    assert identity["worker_id"] == "worker:host-01"
    assert identity["interface"] == "eth0"
    assert identity["inode"] > 0
    assert source.read_nftables_json() == nft_json()
    argv, kwargs = calls[0]
    assert argv == ["/usr/bin/nsenter", "--target", str(PID), "--net",
                    "/usr/sbin/nft", "-j", "list", "ruleset"]
    assert kwargs["shell"] is False
    assert kwargs["stdin"] is subprocess.DEVNULL
    assert kwargs["timeout"] == 5.0


def test_linux_source_rejects_pid_reuse_before_running_nft(tmp_path):
    source, calls = make_source(tmp_path, provider=FakeRuntimeProvider(start_ticks=START_TICKS + 1))
    with pytest.raises(HostCollectionError, match="reused"):
        source.read_network_namespace_identity()
    assert calls == []


def test_linux_source_requires_exactly_one_non_loopback_interface(tmp_path):
    source, calls = make_source(tmp_path, interfaces=("lo", "eth0", "eth1"))
    with pytest.raises(HostCollectionError, match="exactly one"):
        source.read_network_namespace_identity()
    assert calls == []


def test_linux_source_rejects_runtime_process_identity_mismatch(tmp_path):
    source, calls = make_source(tmp_path, provider=FakeRuntimeProvider(attestation_worker_id="worker:other-01"))
    with pytest.raises(HostCollectionError, match="does not match"):
        source.read_network_namespace_identity()
    assert calls == []


def test_linux_source_fails_closed_when_nftables_command_fails(tmp_path):
    def fail(argv, **kwargs):
        return subprocess.CompletedProcess(argv, 1, "", "permission denied")
    source, _ = make_source(tmp_path, runner=fail)
    with pytest.raises(HostCollectionError, match="non-zero"):
        source.read_nftables_json()


def test_linux_source_rejects_relative_executable_paths(tmp_path):
    with pytest.raises(ValueError, match="absolute"):
        LinuxHostSnapshotSource(FakeRuntimeProvider(), nsenter_path="nsenter")
