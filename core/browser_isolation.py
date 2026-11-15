"""Offline validator for a future unprivileged browser-worker launch profile.

This module validates a declarative security profile only. It does not create
containers, namespaces, firewall rules, proxies, users, mounts or processes.
A trusted deployment adapter must enforce and independently attest every
validated setting before any browser process can be started.
"""
from __future__ import annotations

from dataclasses import dataclass
import ipaddress
import re
from collections.abc import Mapping
from urllib.parse import urlsplit


class IsolationPolicyError(ValueError):
    """Raised when a worker launch profile is incomplete or unsafe."""


_REQUIRED_FIELDS = frozenset({
    "schema_version", "uid", "gid", "privileged", "read_only_root",
    "no_new_privileges", "capabilities_drop", "host_network", "host_pid",
    "host_ipc", "host_mounts", "secret_mounts", "writable_mounts",
    "browser_profile_persistence", "cdp_exposed", "direct_egress",
    "proxy_only_egress", "dns_via_proxy_only", "egress_proxy",
    "memory_limit_bytes", "cpu_limit_millis", "pids_limit",
    "job_timeout_seconds",
})
_PROXY_HOST = re.compile(r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\\.)+[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")


@dataclass(frozen=True)
class WorkerIsolationProfile:
    uid: int
    gid: int
    egress_proxy: str
    memory_limit_bytes: int
    cpu_limit_millis: int
    pids_limit: int
    job_timeout_seconds: int
    writable_mounts: tuple[str, ...]


def _require_true(profile: Mapping, key: str) -> None:
    if profile.get(key) is not True:
        raise IsolationPolicyError(f"{key} must be true.")


def _require_false(profile: Mapping, key: str) -> None:
    if profile.get(key) is not False:
        raise IsolationPolicyError(f"{key} must be false.")


def _bounded_int(profile: Mapping, key: str, minimum: int, maximum: int) -> int:
    value = profile.get(key)
    if type(value) is not int or not minimum <= value <= maximum:
        raise IsolationPolicyError(f"{key} is outside the permitted range.")
    return value


def validate_worker_profile(raw: object) -> WorkerIsolationProfile:
    """Validate a closed, deny-by-default worker isolation manifest."""
    if not isinstance(raw, Mapping) or any(type(k) is not str for k in raw):
        raise IsolationPolicyError("Worker profile must be a string-keyed mapping.")
    if set(raw) != _REQUIRED_FIELDS:
        raise IsolationPolicyError("Worker profile fields are missing or unknown.")
    if type(raw["schema_version"]) is not int or raw["schema_version"] != 1:
        raise IsolationPolicyError("Unsupported worker profile schema.")
    uid = _bounded_int(raw, "uid", 1, 65535)
    gid = _bounded_int(raw, "gid", 1, 65535)

    for key in ("privileged", "host_network", "host_pid", "host_ipc",
                "browser_profile_persistence", "cdp_exposed", "direct_egress"):
        _require_false(raw, key)
    for key in ("read_only_root", "no_new_privileges",
                "proxy_only_egress", "dns_via_proxy_only"):
        _require_true(raw, key)

    if raw["capabilities_drop"] != ["ALL"]:
        raise IsolationPolicyError("All Linux capabilities must be dropped.")
    for key in ("host_mounts", "secret_mounts"):
        if raw[key] != []:
            raise IsolationPolicyError(f"{key} must be empty.")
    writable = raw["writable_mounts"]
    if not isinstance(writable, list) or any(type(x) is not str for x in writable):
        raise IsolationPolicyError("Writable mounts must be a list of paths.")
    if any(
        not p.startswith("/tmp/")
        or len(p.split("/")) < 4
        or any(part in (".", "..") for part in p.split("/"))
        for p in writable
    ) or len(set(writable)) != len(writable):
        raise IsolationPolicyError("Only unique, job-ephemeral child paths below /tmp are permitted.")

    proxy = raw["egress_proxy"]
    if type(proxy) is not str:
        raise IsolationPolicyError("An explicit egress proxy endpoint is required.")
    try:
        parsed = urlsplit(proxy)
        port = parsed.port
    except ValueError as exc:
        raise IsolationPolicyError("Egress proxy endpoint is malformed.") from exc
    try:
        proxy_is_ip = ipaddress.ip_address(parsed.hostname or "") is not None
    except ValueError:
        proxy_is_ip = False
    if (parsed.scheme != "http" or not parsed.hostname or proxy_is_ip
            or not parsed.hostname.endswith(".internal")
            or not _PROXY_HOST.fullmatch(parsed.hostname)
            or parsed.username is not None or parsed.password is not None
            or parsed.path not in ("", "/") or parsed.query or parsed.fragment
            or port is None or not 1 <= port <= 65535):
        raise IsolationPolicyError("Egress proxy must be an explicit internal HTTP proxy endpoint.")

    return WorkerIsolationProfile(
        uid=uid,
        gid=gid,
        egress_proxy=proxy,
        memory_limit_bytes=_bounded_int(raw, "memory_limit_bytes", 128 * 1024 * 1024, 2 * 1024 * 1024 * 1024),
        cpu_limit_millis=_bounded_int(raw, "cpu_limit_millis", 100, 4000),
        pids_limit=_bounded_int(raw, "pids_limit", 16, 256),
        job_timeout_seconds=_bounded_int(raw, "job_timeout_seconds", 1, 60),
        writable_mounts=tuple(writable),
    )
