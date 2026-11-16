"""Read-only live Linux qualification for the P07 host inspector.

Runs only in a disposable CI runner. It inspects a child process in the
runner's existing network namespace and never changes host/network policy.
This is not owner-host or production qualification.
"""
from __future__ import annotations

import json
import subprocess
import sys

from core.linux_host_inspector import LinuxHostInspectorAdapter


def main() -> int:
    worker = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
    )
    try:
        adapter = LinuxHostInspectorAdapter(
            runtime_attestation_reader=lambda: {
                "schema_version": 1,
                "qualification": "disposable-ci-live-procfs",
            },
            runtime_id="runtime:ci-live-inspector",
            worker_id="worker:ci-live-inspector",
            worker_pid=worker.pid,
        )
        attestation = adapter.read_runtime_attestation()
        if attestation.get("qualification") != "disposable-ci-live-procfs":
            raise SystemExit("FAIL: runtime attestation reader contract mismatch")

        identity = adapter.read_network_namespace_identity()
        if identity.get("runtime_id") != "runtime:ci-live-inspector":
            raise SystemExit("FAIL: runtime identity mismatch")
        if identity.get("worker_id") != "worker:ci-live-inspector":
            raise SystemExit("FAIL: worker identity mismatch")
        if type(identity.get("inode")) is not int or identity["inode"] <= 0:
            raise SystemExit("FAIL: live network namespace inode missing")
        if not isinstance(identity.get("interface"), str) or not identity["interface"]:
            raise SystemExit("FAIL: live worker interface missing")

        raw = adapter.read_nftables_json()
        snapshot = json.loads(raw)
        if not isinstance(snapshot, dict) or not isinstance(snapshot.get("nftables"), list):
            raise SystemExit("FAIL: live nftables JSON has an unexpected shape")
        print("PASS: live /proc PID, network namespace inode, interface and read-only nftables snapshot verified")
        print("BOUNDARY: disposable CI runner only; no owner-host qualification is implied")
        return 0
    finally:
        worker.terminate()
        try:
            worker.wait(timeout=3)
        except subprocess.TimeoutExpired:
            worker.kill()
            worker.wait(timeout=3)


if __name__ == "__main__":
    raise SystemExit(main())
