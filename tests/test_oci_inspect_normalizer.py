import json
import pytest

from core.browser_runtime import build_worker_launch_spec
from core.browser_isolation import validate_worker_profile
from core.oci_errors import OCIExecutionError
from core.oci_inspect_normalizer import normalize_oci_inspect
from core.oci_worker_plan import build_oci_worker_plan


IMAGE = "registry.example.invalid/apaa/worker@sha256:" + "a" * 64
# Podman expands --cap-drop=ALL into an explicit Linux capability list.
PODMAN_ALL_CAPS = [
    "AUDIT_CONTROL", "AUDIT_READ", "AUDIT_WRITE", "BLOCK_SUSPEND", "BPF",
    "CHECKPOINT_RESTORE", "CHOWN", "DAC_OVERRIDE", "DAC_READ_SEARCH",
    "FOWNER", "FSETID", "IPC_LOCK", "IPC_OWNER", "KILL", "LEASE",
    "LINUX_IMMUTABLE", "MAC_ADMIN", "MAC_OVERRIDE", "MKNOD", "NET_ADMIN",
    "NET_BIND_SERVICE", "NET_BROADCAST", "NET_RAW", "PERFMON", "SETFCAP", "SETGID",
    "SETPCAP", "SETUID", "SYS_ADMIN", "SYS_BOOT", "SYS_CHROOT", "SYS_MODULE",
    "SYS_NICE", "SYS_PACCT", "SYS_PTRACE", "SYS_RAWIO", "SYS_RESOURCE",
    "SYS_TIME", "SYS_TTY_CONFIG", "SYSLOG", "WAKE_ALARM",
]
PROFILE = {
    "schema_version": 1, "uid": 10001, "gid": 10001,
    "privileged": False, "read_only_root": True, "no_new_privileges": True,
    "capabilities_drop": ["ALL"], "host_network": False, "host_pid": False,
    "host_ipc": False, "host_mounts": [], "secret_mounts": [],
    "writable_mounts": ["/tmp/job"], "browser_profile_persistence": False,
    "cdp_exposed": False, "direct_egress": False, "proxy_only_egress": True,
    "dns_via_proxy_only": True, "egress_proxy": "http://proxy.apaa.internal:3128",
    "memory_limit_bytes": 536870912, "cpu_limit_millis": 1000,
    "pids_limit": 64, "job_timeout_seconds": 30,
}


def plan(runtime):
    spec = build_worker_launch_spec(validate_worker_profile(PROFILE))
    return build_oci_worker_plan(
        spec, runtime=runtime, image=IMAGE, network_name="apaa-egress-prod",
        job_id="job-123", seccomp_profile="/etc/apaa/seccomp.json", rootless=True,
    )


def inspect_fixture(*, podman=False, **host_overrides):
    host = {
        "NetworkMode": "apaa-egress-prod", "ReadonlyRootfs": True,
        "Privileged": False, "PidMode": "private", "IpcMode": "private",
        "CapDrop": PODMAN_ALL_CAPS if podman else ["ALL"],
        "CapAdd": [],
        "SecurityOpt": ["no-new-privileges:true", "seccomp=/etc/apaa/seccomp.json"],
    }
    host.update(host_overrides)
    item = {"Id": "a" * 64, "State": {"Status": "created"}, "HostConfig": host}
    item["ImageName"] = IMAGE if podman else None
    item["Config"] = {} if podman else {"Image": IMAGE}
    return json.dumps([item])


@pytest.mark.parametrize("runtime", ["docker", "podman"])
def test_known_runtime_inspect_shapes_normalize(runtime):
    normalized = normalize_oci_inspect(inspect_fixture(podman=runtime == "podman"), plan(runtime))
    assert normalized.container_id == "a" * 64
    assert normalized.image == IMAGE
    assert normalized.readonly_rootfs is True


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"ReadonlyRootfs": False}, "read-only"),
        ({"NetworkMode": "bridge"}, "network"),
        ({"CapDrop": []}, "capabilities"),
        ({"SecurityOpt": ["no-new-privileges:true"]}, "seccomp"),
        ({"Privileged": True}, "privileged"),
        ({"CapAdd": ["NET_ADMIN"]}, "adds Linux capabilities"),
        ({"CapDrop": PODMAN_ALL_CAPS[:-1]}, "capabilities"),
        ({"CapDrop": PODMAN_ALL_CAPS + ["FUTURE_UNKNOWN_CAP"]}, "capabilities"),
    ],
)
def test_inspect_policy_drift_fails_closed(overrides, message):
    with pytest.raises(OCIExecutionError, match=message):
        normalize_oci_inspect(inspect_fixture(**overrides), plan("docker"))


def test_podman_wrong_image_name_fails_closed():
    item = json.loads(inspect_fixture(podman=True))
    item[0]["ImageName"] = "untrusted:latest"
    with pytest.raises(OCIExecutionError, match="digest-pinned"):
        normalize_oci_inspect(json.dumps(item), plan("podman"))
