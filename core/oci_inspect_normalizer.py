"""Strict, read-only normalization for Docker and Podman inspect JSON."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from core.oci_worker_plan import OCIWorkerPlan
from core.oci_errors import OCIExecutionError


# Linux capability names known to the supported runtime contract. Podman may
# expand --cap-drop=ALL into this explicit list in inspect JSON; Docker commonly
# preserves the literal ALL token. Unknown/missing entries fail closed.
_LINUX_CAPABILITIES = frozenset({
    "AUDIT_CONTROL", "AUDIT_READ", "AUDIT_WRITE", "BLOCK_SUSPEND", "BPF",
    "CHECKPOINT_RESTORE", "CHOWN", "DAC_OVERRIDE", "DAC_READ_SEARCH",
    "FOWNER", "FSETID", "IPC_LOCK", "IPC_OWNER", "KILL", "LEASE",
    "LINUX_IMMUTABLE", "MAC_ADMIN", "MAC_OVERRIDE", "MKNOD", "NET_ADMIN",
    "NET_BIND_SERVICE", "NET_BROADCAST", "NET_RAW", "PERFMON",
    "SETGID", "SETFCAP", "SETPCAP", "SETUID", "SYS_ADMIN", "SYS_BOOT",
    "SYS_CHROOT", "SYS_MODULE", "SYS_NICE", "SYS_PACCT", "SYS_PTRACE",
    "SYS_RAWIO", "SYS_RESOURCE", "SYS_TIME", "SYS_TTY_CONFIG", "SYSLOG",
    "WAKE_ALARM",
})


@dataclass(frozen=True)
class OCIInspectSnapshot:
    container_id: str
    container_name: str
    image: str
    state: str
    network: str
    readonly_rootfs: bool
    cap_drop: tuple[str, ...]
    security_options: tuple[str, ...]
    launch_spec_digest: str


def _all_capabilities_dropped(value: Any) -> bool:
    if not isinstance(value, list) or not value or not all(type(x) is str for x in value):
        return False
    normalized = {x.upper().removeprefix("CAP_") for x in value}
    return normalized == {"ALL"} or normalized == _LINUX_CAPABILITIES


def normalize_oci_inspect(raw: str, plan: OCIWorkerPlan) -> OCIInspectSnapshot:
    """Accept only the known Docker/Podman inspect shapes and fail closed."""
    try:
        decoded: Any = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise OCIExecutionError("inspect: runtime returned invalid JSON.") from exc
    if not isinstance(decoded, list) or len(decoded) != 1 or not isinstance(decoded[0], dict):
        raise OCIExecutionError("inspect: expected exactly one container object.")
    item = decoded[0]
    state = item.get("State")
    config = item.get("Config")
    host = item.get("HostConfig")
    if not isinstance(state, dict) or state.get("Status") != "created":
        raise OCIExecutionError("inspect: worker is not confirmed stopped in created state.")
    container_id = item.get("Id")
    if type(container_id) is not str or len(container_id) < 12:
        raise OCIExecutionError("inspect: runtime did not return a valid immutable container ID.")

    config_image = config.get("Image") if isinstance(config, dict) else None
    podman_image = item.get("ImageName") if plan.runtime == "podman" else None
    effective_image = config_image or podman_image
    if effective_image != plan.image:
        raise OCIExecutionError("inspect: effective image differs from the digest-pinned plan.")
    if not isinstance(host, dict):
        raise OCIExecutionError("inspect: effective host configuration is missing.")
    network = host.get("NetworkMode")
    if network != plan.network_name:
        # Podman 4.9 reports the generic HostConfig.NetworkMode ("bridge")
        # for a user-defined bridge, while NetworkSettings.Networks records
        # the actual attached network name. Accept only the exact, sole
        # requested attachment; extra or missing networks remain fail-closed.
        network_settings = item.get("NetworkSettings")
        attached = (
            network_settings.get("Networks")
            if isinstance(network_settings, dict) else None
        )
        if (
            plan.runtime != "podman"
            or network not in {"bridge", "private"}
            or not isinstance(attached, dict)
            or set(attached) != {plan.network_name}
        ):
            attached_names = sorted(attached) if isinstance(attached, dict) else []
            raise OCIExecutionError(
                "inspect: effective network mismatch "
                f"(runtime={plan.runtime}, mode={network!r}, "
                f"expected={plan.network_name!r}, attached={attached_names!r})."
            )
        network = plan.network_name
    if host.get("ReadonlyRootfs") is not True:
        raise OCIExecutionError("inspect: read-only root filesystem is not enforced.")
    if host.get("Privileged") is True or host.get("PidMode") == "host" or host.get("IpcMode") == "host":
        raise OCIExecutionError("inspect: privileged or host namespace mode detected.")
    caps = host.get("CapDrop")
    if not _all_capabilities_dropped(caps):
        raise OCIExecutionError("inspect: Linux capabilities are not fully dropped.")
    cap_add = host.get("CapAdd")
    if cap_add not in (None, []):
        raise OCIExecutionError("inspect: runtime adds Linux capabilities.")
    security = host.get("SecurityOpt")
    if not isinstance(security, list) or not any(
        isinstance(x, str) and x.startswith("no-new-privileges") for x in security
    ) or not any(isinstance(x, str) and x.startswith("seccomp=") for x in security):
        raise OCIExecutionError("inspect: no-new-privileges/seccomp are not both enforced.")
    return OCIInspectSnapshot(
        container_id=container_id,
        container_name=plan.container_name,
        image=effective_image,
        state="created",
        network=network,
        readonly_rootfs=True,
        cap_drop=tuple(caps),
        security_options=tuple(security),
        launch_spec_digest=plan.launch_spec_digest,
    )
