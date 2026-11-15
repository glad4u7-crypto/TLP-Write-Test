"""Offline worker launch-contract and pre-start attestation validation.

This module does not create containers, namespaces, firewall rules, proxies,
processes or browser sessions. It builds an inert launch specification and
validates evidence supplied by a separately trusted runtime/host inspector.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import ipaddress
import json
import re
import time
from urllib.parse import urlsplit

from core.browser_isolation import WorkerIsolationProfile


class RuntimeAttestationError(ValueError):
    """Raised when launch evidence is incomplete, stale or unsafe."""


_NAMESPACES = ("user", "pid", "network", "ipc", "uts", "mount")
_ATTESTATION_FIELDS = frozenset({
    "schema_version", "launch_spec_digest", "runtime_id", "worker_id",
    "image_digest", "attestor_id", "evidence_digest", "observed_at", "state",
    "process_started", "runtime_config_verified", "host_firewall_verified",
    "uid", "gid", "privileged", "read_only_root", "no_new_privileges",
    "capabilities_effective", "namespaces", "host_mounts", "secret_mounts",
    "writable_mounts", "browser_profile_persistence", "cdp_exposed",
    "direct_egress", "proxy_only_egress", "dns_via_proxy_only", "egress_proxy",
    "memory_limit_bytes", "cpu_limit_millis", "pids_limit", "job_timeout_seconds",
    "seccomp_enforced", "network_namespace_isolated", "firewall_default_deny",
    "egress_allowed", "direct_dns_egress_blocked", "proxy_side_dns_only",
})
_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
_HEX_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{2,127}$")


@dataclass(frozen=True)
class WorkerLaunchSpec:
    """Immutable, inert description of the required worker runtime settings."""

    uid: int
    gid: int
    read_only_root: bool
    no_new_privileges: bool
    capabilities_drop: tuple[str, ...]
    namespaces: tuple[str, ...]
    host_mounts: tuple[str, ...]
    secret_mounts: tuple[str, ...]
    writable_mounts: tuple[str, ...]
    browser_profile_persistence: bool
    cdp_exposed: bool
    direct_egress: bool
    proxy_only_egress: bool
    dns_via_proxy_only: bool
    egress_proxy: str
    memory_limit_bytes: int
    cpu_limit_millis: int
    pids_limit: int
    job_timeout_seconds: int
    seccomp_required: bool
    launch_state_required: str

    @property
    def digest(self) -> str:
        """Stable digest binding an attestation to this exact launch contract."""
        payload = {
            "uid": self.uid, "gid": self.gid,
            "read_only_root": self.read_only_root,
            "no_new_privileges": self.no_new_privileges,
            "capabilities_drop": self.capabilities_drop,
            "namespaces": self.namespaces,
            "host_mounts": self.host_mounts,
            "secret_mounts": self.secret_mounts,
            "writable_mounts": self.writable_mounts,
            "browser_profile_persistence": self.browser_profile_persistence,
            "cdp_exposed": self.cdp_exposed,
            "direct_egress": self.direct_egress,
            "proxy_only_egress": self.proxy_only_egress,
            "dns_via_proxy_only": self.dns_via_proxy_only,
            "egress_proxy": self.egress_proxy,
            "memory_limit_bytes": self.memory_limit_bytes,
            "cpu_limit_millis": self.cpu_limit_millis,
            "pids_limit": self.pids_limit,
            "job_timeout_seconds": self.job_timeout_seconds,
            "seccomp_required": self.seccomp_required,
            "launch_state_required": self.launch_state_required,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class RuntimeSecurityAttestation:
    """Validated pre-start facts; not a cryptographic proof of kernel state."""

    runtime_id: str
    worker_id: str
    image_digest: str
    attestor_id: str
    evidence_digest: str
    observed_at: int
    launch_spec_digest: str
    proxy_endpoint: str
    worker_state: str


def build_worker_launch_spec(profile: object) -> WorkerLaunchSpec:
    """Translate a validated P04 profile into an inert launch contract only."""
    if type(profile) is not WorkerIsolationProfile:
        raise RuntimeAttestationError("A validated WorkerIsolationProfile is required.")
    return WorkerLaunchSpec(
        uid=profile.uid,
        gid=profile.gid,
        read_only_root=True,
        no_new_privileges=True,
        capabilities_drop=("ALL",),
        namespaces=_NAMESPACES,
        host_mounts=(),
        secret_mounts=(),
        writable_mounts=profile.writable_mounts,
        browser_profile_persistence=False,
        cdp_exposed=False,
        direct_egress=False,
        proxy_only_egress=True,
        dns_via_proxy_only=True,
        egress_proxy=profile.egress_proxy,
        memory_limit_bytes=profile.memory_limit_bytes,
        cpu_limit_millis=profile.cpu_limit_millis,
        pids_limit=profile.pids_limit,
        job_timeout_seconds=profile.job_timeout_seconds,
        seccomp_required=True,
        launch_state_required="created",
    )


def _require_bool(raw: dict, key: str, expected: bool) -> None:
    if type(raw.get(key)) is not bool or raw[key] is not expected:
        raise RuntimeAttestationError(f"Runtime attestation mismatch: {key}.")


def _require_int(raw: dict, key: str, expected: int) -> None:
    if type(raw.get(key)) is not int or raw[key] != expected:
        raise RuntimeAttestationError(f"Runtime attestation mismatch: {key}.")


def _proxy_destination(endpoint: str) -> str:
    parsed = urlsplit(endpoint)
    try:
        port = parsed.port
    except ValueError as exc:
        raise RuntimeAttestationError("Configured proxy endpoint is malformed.") from exc
    if not parsed.hostname or port is None:
        raise RuntimeAttestationError("Configured proxy endpoint is incomplete.")
    try:
        ipaddress.ip_address(parsed.hostname)
    except ValueError:
        pass
    else:
        raise RuntimeAttestationError("Proxy endpoint must use its named internal host.")
    return f"{parsed.hostname}:{port}"


def verify_prestart_attestation(
    spec: WorkerLaunchSpec,
    raw: object,
    *,
    now: int | None = None,
    max_age_seconds: int = 60,
) -> RuntimeSecurityAttestation:
    """Fail closed unless trusted inspector evidence matches every required fact.

    The raw mapping must come from a separately trusted runtime + host-firewall
    inspector. A caller-created mapping is not proof. This function performs no
    runtime, network, DNS, filesystem or process inspection itself.
    """
    if type(spec) is not WorkerLaunchSpec:
        raise RuntimeAttestationError("A WorkerLaunchSpec is required.")
    if not isinstance(raw, dict) or any(type(key) is not str for key in raw):
        raise RuntimeAttestationError("Attestation must be a string-keyed mapping.")
    if set(raw) != _ATTESTATION_FIELDS:
        raise RuntimeAttestationError("Attestation fields are missing or unknown.")
    if type(raw["schema_version"]) is not int or raw["schema_version"] != 1:
        raise RuntimeAttestationError("Unsupported attestation schema.")
    if raw["launch_spec_digest"] != spec.digest:
        raise RuntimeAttestationError("Attestation is not bound to this launch specification.")

    for key in ("runtime_id", "worker_id", "attestor_id"):
        if type(raw[key]) is not str or not _IDENTIFIER.fullmatch(raw[key]):
            raise RuntimeAttestationError(f"Invalid {key}.")
    if type(raw["image_digest"]) is not str or not _SHA256.fullmatch(raw["image_digest"]):
        raise RuntimeAttestationError("Worker image must be pinned by a sha256 digest.")
    if type(raw["evidence_digest"]) is not str or not _HEX_DIGEST.fullmatch(raw["evidence_digest"]):
        raise RuntimeAttestationError("Evidence digest is malformed.")

    observed_at = raw["observed_at"]
    if type(observed_at) is not int:
        raise RuntimeAttestationError("Attestation timestamp must be an integer.")
    current = int(time.time()) if now is None else now
    if type(current) is not int or type(max_age_seconds) is not int or max_age_seconds < 1:
        raise RuntimeAttestationError("Attestation freshness parameters are invalid.")
    if observed_at > current + 5 or current - observed_at > max_age_seconds:
        raise RuntimeAttestationError("Runtime attestation is stale or from the future.")

    if raw["state"] != "created":
        raise RuntimeAttestationError("Worker must remain in the created, not-running state.")
    _require_bool(raw, "process_started", False)
    _require_bool(raw, "runtime_config_verified", True)
    _require_bool(raw, "host_firewall_verified", True)
    _require_int(raw, "uid", spec.uid)
    _require_int(raw, "gid", spec.gid)

    expected_bools = {
        "privileged": False, "read_only_root": True,
        "no_new_privileges": True, "browser_profile_persistence": False,
        "cdp_exposed": False, "direct_egress": False,
        "proxy_only_egress": True, "dns_via_proxy_only": True,
        "seccomp_enforced": True, "network_namespace_isolated": True,
        "firewall_default_deny": True, "direct_dns_egress_blocked": True,
        "proxy_side_dns_only": True,
    }
    for key, expected in expected_bools.items():
        _require_bool(raw, key, expected)

    if raw["capabilities_effective"] != []:
        raise RuntimeAttestationError("Effective Linux capabilities must be empty.")
    if raw["namespaces"] != list(spec.namespaces):
        raise RuntimeAttestationError("Runtime namespace set does not match the launch contract.")
    if raw["host_mounts"] != [] or raw["secret_mounts"] != []:
        raise RuntimeAttestationError("Host and secret mounts must be absent.")
    if raw["writable_mounts"] != list(spec.writable_mounts):
        raise RuntimeAttestationError("Writable mounts do not match the ephemeral launch contract.")
    if raw["egress_proxy"] != spec.egress_proxy:
        raise RuntimeAttestationError("Runtime proxy endpoint differs from the approved profile.")
    if raw["egress_allowed"] != [_proxy_destination(spec.egress_proxy)]:
        raise RuntimeAttestationError("Worker egress must allow only the fixed proxy endpoint.")

    for key, expected in (
        ("memory_limit_bytes", spec.memory_limit_bytes),
        ("cpu_limit_millis", spec.cpu_limit_millis),
        ("pids_limit", spec.pids_limit),
        ("job_timeout_seconds", spec.job_timeout_seconds),
    ):
        _require_int(raw, key, expected)

    return RuntimeSecurityAttestation(
        runtime_id=raw["runtime_id"],
        worker_id=raw["worker_id"],
        image_digest=raw["image_digest"],
        attestor_id=raw["attestor_id"],
        evidence_digest=raw["evidence_digest"],
        observed_at=observed_at,
        launch_spec_digest=spec.digest,
        proxy_endpoint=spec.egress_proxy,
        worker_state="created",
    )
