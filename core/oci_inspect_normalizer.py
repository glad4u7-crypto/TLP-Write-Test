"""Strict, read-only normalization for Docker and Podman inspect JSON."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from core.oci_worker_plan import OCIWorkerPlan
from core.oci_errors import OCIExecutionError


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

    # Docker reports Config.Image; Podman may additionally report ImageName.
    config_image = config.get("Image") if isinstance(config, dict) else None
    podman_image = item.get("ImageName") if plan.runtime == "podman" else None
    effective_image = config_image or podman_image
    if effective_image != plan.image:
        raise OCIExecutionError("inspect: effective image differs from the digest-pinned plan.")
    if not isinstance(host, dict):
        raise OCIExecutionError("inspect: effective host configuration is missing.")
    network = host.get("NetworkMode")
    if network != plan.network_name:
        raise OCIExecutionError("inspect: effective network differs from the approved APAA network.")
    if host.get("ReadonlyRootfs") is not True:
        raise OCIExecutionError("inspect: read-only root filesystem is not enforced.")
    if host.get("Privileged") is True or host.get("PidMode") == "host" or host.get("IpcMode") == "host":
        raise OCIExecutionError("inspect: privileged or host namespace mode detected.")
    caps = host.get("CapDrop")
    if not isinstance(caps, list) or "ALL" not in caps:
        raise OCIExecutionError("inspect: Linux capabilities are not fully dropped.")
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
