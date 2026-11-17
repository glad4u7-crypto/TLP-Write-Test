"""Read-only live Linux qualification for the P07 host inspector.

Runs only in a disposable CI runner. It creates a short-lived isolated
network namespace with one disposable dummy worker interface, then inspects
a child process there. It never changes the runner's host network policy.
This is not owner-host or production qualification.
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import time

# Executing a file under scripts/ puts that directory, not the repository
# root, at sys.path[0]. Add the project root so the core package is importable
# both from a checkout and when invoked directly by the CI qualification job.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.linux_host_inspector import LinuxHostInspectorAdapter


def main() -> int:
    # Use a private disposable netns: hosted runners may expose several
    # non-loopback interfaces, while the worker contract intentionally allows
    # exactly one. The dummy interface exists only inside this child netns.
    worker = subprocess.Popen(
        [
            "/usr/bin/unshare", "--net", "--",
            "/bin/sh", "-c",
            "ip link add apaa0 type dummy && ip link set apaa0 up && "
            "exec " + sys.executable + " -c 'import time; time.sleep(30)'",
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
    )
    try:
        # Wait until the namespace setup has completed before inspecting it.
        # Popen returns as soon as unshare starts, not when the dummy interface
        # has been created; inspecting immediately introduces a startup race.
        deadline = time.monotonic() + 5
        proc_net_dev = Path("/proc") / str(worker.pid) / "net" / "dev"
        while time.monotonic() < deadline:
            if worker.poll() is not None:
                raise SystemExit("FAIL: disposable worker exited before namespace setup completed")
            try:
                lines = proc_net_dev.read_text(encoding="ascii").splitlines()[2:]
            except (OSError, UnicodeError):
                lines = []
            interfaces = [line.split(":", 1)[0].strip() for line in lines if ":" in line]
            if "apaa0" in interfaces:
                break
            time.sleep(0.05)
        else:
            raise SystemExit("FAIL: disposable worker namespace did not expose apaa0 before timeout")

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
