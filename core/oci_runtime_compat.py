"""Fail-closed compatibility gate for pinned rootless OCI runtimes.

This module is deliberately pure: it does not invoke Docker/Podman, install
packages, create networks, or start containers. A trusted probe must supply
the observed runtime snapshot; this gate compares it with an explicit policy.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


RuntimeName = Literal["docker", "podman"]


@dataclass(frozen=True)
class OCIRuntimeSnapshot:
    runtime: str
    version: str
    rootless: bool
    cgroup_version: str
    security_options: tuple[str, ...]
    supports_create_inspect_start: bool
    supports_readonly_rootfs: bool
    supports_cap_drop_all: bool
    supports_seccomp_profile: bool


@dataclass(frozen=True)
class OCIRuntimePolicy:
    runtime: RuntimeName
    pinned_version: str
    require_rootless: bool = True
    required_cgroup_version: str = "2"


@dataclass(frozen=True)
class OCIRuntimeAssessment:
    compatible: bool
    runtime: str
    observed_version: str
    reasons: tuple[str, ...]


def assess_oci_runtime(
    snapshot: OCIRuntimeSnapshot,
    policy: OCIRuntimePolicy,
) -> OCIRuntimeAssessment:
    """Compare observed capabilities with an exact, operator-pinned policy."""
    if not isinstance(snapshot, OCIRuntimeSnapshot):
        raise TypeError("A normalized OCI runtime snapshot is required.")
    if not isinstance(policy, OCIRuntimePolicy):
        raise TypeError("An explicit OCI runtime policy is required.")
    if policy.runtime not in ("docker", "podman"):
        raise ValueError("Only Docker and Podman are supported.")
    if not policy.pinned_version or any(ch.isspace() for ch in policy.pinned_version):
        raise ValueError("An exact pinned runtime version is required.")

    failures: list[str] = []
    if snapshot.runtime != policy.runtime:
        failures.append("runtime_name_mismatch")
    if snapshot.version != policy.pinned_version:
        failures.append("runtime_version_not_pinned")
    if policy.require_rootless and snapshot.rootless is not True:
        failures.append("rootless_mode_not_proven")
    if snapshot.cgroup_version != policy.required_cgroup_version:
        failures.append("cgroup_version_mismatch")
    if not snapshot.supports_create_inspect_start:
        failures.append("lifecycle_command_contract_missing")
    if not snapshot.supports_readonly_rootfs:
        failures.append("readonly_rootfs_unsupported")
    if not snapshot.supports_cap_drop_all:
        failures.append("cap_drop_all_unsupported")
    if not snapshot.supports_seccomp_profile:
        failures.append("seccomp_profile_unsupported")
    if not any(item.startswith("seccomp") for item in snapshot.security_options):
        failures.append("seccomp_runtime_option_not_reported")

    return OCIRuntimeAssessment(
        compatible=not failures,
        runtime=snapshot.runtime,
        observed_version=snapshot.version,
        reasons=tuple(failures) if failures else ("pinned_rootless_runtime_contract_passed",),
    )
