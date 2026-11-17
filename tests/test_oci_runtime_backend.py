from __future__ import annotations

import json
from pathlib import Path
import subprocess

import pytest

from core.oci_runtime_backend import (
    OCIWorkerSpec,
    OCIRuntimeError,
    PodmanOCIRuntime,
    WorkerLimits,
)


IMAGE = "registry.invalid/apaa/chromium@sha256:" + "a" * 64
NS = "/run/netns/apaa-test"
SECCOMP = "/etc/apaa/seccomp-chromium.json"


class FakeRunner:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.calls = []

    def __call__(self, command, **kwargs):
        self.calls.append((command, kwargs))
        if len(command) > 1 and command[1] == "ps":
            return subprocess.CompletedProcess(command, 0, "", "")
        rc, stdout = self.outputs.pop(0)
        if "--cidfile" in command:
            Path(command[command.index("--cidfile") + 1]).write_text(stdout.strip(), encoding="ascii")
        return subprocess.CompletedProcess(command, rc, stdout, "")


def spec(**changes):
    values = dict(
        image=IMAGE,
        network_namespace=NS,
        seccomp_profile=SECCOMP,
        worker_id="worker-0001",
        limits=WorkerLimits(memory_bytes=512 * 1024 * 1024, cpu_count=1, pids_limit=64),
    )
    values.update(changes)
    return OCIWorkerSpec(**values)


def test_create_uses_digest_pinned_image_and_hardening_flags():
    runner = FakeRunner([(0, "b" * 64 + "\n")])
    runtime = PodmanOCIRuntime(runner=runner)
    container_id = runtime.create(spec())
    command, kwargs = runner.calls[0]
    assert container_id == "b" * 64
    assert command[1] == "--cgroup-manager=cgroupfs"
    assert command[2] == "create"
    assert "--pull=never" in command
    assert "--read-only" in command
    assert "--tmpfs" in command
    assert "--shm-size" in command
    assert "--cap-drop=ALL" in command
    assert "--security-opt=no-new-privileges" in command
    assert "--entrypoint" in command and "sleep" in command and "infinity" in command
    assert f"ns:{NS}" in command
    assert IMAGE in command
    assert kwargs["shell"] is False
    assert kwargs["timeout"] == 20


def test_create_uses_dedicated_cgroup_parent_when_supplied():
    runner = FakeRunner([(0, "b" * 64 + "\\n")])
    runtime = PodmanOCIRuntime(runner=runner)
    runtime.create(spec(cgroup_parent="/sys/fs/cgroup/apaa/worker-0001"))
    command = runner.calls[0][0]
    assert "--cgroup-parent" in command
    assert command[command.index("--cgroup-parent") + 1] == "/sys/fs/cgroup/apaa/worker-0001"


def test_spec_rejects_cgroup_parent_outside_delegated_subtree():
    with pytest.raises(ValueError):
        spec(cgroup_parent="/sys/fs/cgroup/system.slice")


def test_local_immutable_image_id_is_accepted():
    spec(image="sha256:" + "b" * 64)


def test_create_rejects_noncanonical_runtime_id():
    runtime = PodmanOCIRuntime(runner=FakeRunner([(0, "not-a-container-id")]))
    with pytest.raises(OCIRuntimeError):
        runtime.create(spec())


@pytest.mark.parametrize("image", [
    "registry.invalid/apaa/chromium:latest",
    "registry.invalid/apaa/chromium@sha256:abcd",
    "registry.invalid/apaa/chromium@sha256:" + "g" * 64,
])
def test_spec_rejects_mutable_or_invalid_image_reference(image):
    with pytest.raises(ValueError):
        spec(image=image)


@pytest.mark.parametrize("namespace", [
    "/tmp/netns",
    "/run/netns/../host",
    "run/netns/worker",
])
def test_spec_rejects_untrusted_namespace_path(namespace):
    with pytest.raises(ValueError):
        spec(network_namespace=namespace)


def test_lifecycle_only_accepts_full_immutable_container_id():
    runner = FakeRunner([
        (0, json.dumps([{"Id": "b" * 64, "State": {"Status": "created"}}])),
        (0, ""),
        (0, ""),
        (0, ""),
    ])
    runtime = PodmanOCIRuntime(runner=runner)
    runtime.inspect("b" * 64)
    runtime.start("b" * 64)
    runtime.stop("b" * 64)
    runtime.remove("b" * 64)
    assert [call[0][1] for call in runner.calls] == ["inspect", "start", "stop", "rm"]


@pytest.mark.parametrize("method", ["inspect", "start", "stop", "remove"])
def test_lifecycle_rejects_name_or_short_id(method):
    runtime = PodmanOCIRuntime(runner=FakeRunner([]))
    with pytest.raises(ValueError):
        getattr(runtime, method)("apaa-worker")


def test_inspect_rejects_invalid_json():
    runtime = PodmanOCIRuntime(runner=FakeRunner([(0, "not-json")]))
    with pytest.raises(OCIRuntimeError):
        runtime.inspect("b" * 64)


def test_runtime_failure_is_sanitized():
    runtime = PodmanOCIRuntime(runner=FakeRunner([(125, "")]))
    with pytest.raises(OCIRuntimeError, match="command failed"):
        runtime.start("b" * 64)


def test_limits_are_bounded():
    with pytest.raises(ValueError):
        WorkerLimits(memory_bytes=1)
    with pytest.raises(ValueError):
        WorkerLimits(cpu_count=0)
    with pytest.raises(ValueError):
        WorkerLimits(pids_limit=1)
