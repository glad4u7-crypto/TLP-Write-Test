"""Linux network-namespace and veth provisioner.

Provisioning is an explicit privileged host operation. There is no implicit
fallback to the host network namespace. Tests inject a runner; real-host
qualification is separate and must be performed on a disposable Linux host.
"""
from __future__ import annotations

from dataclasses import dataclass
import ipaddress
import os
import re
import subprocess
from typing import Callable, Sequence


class NamespaceProvisionError(RuntimeError):
    pass


_NAME = re.compile(r"^[a-z][a-z0-9_-]{0,9}$")
Runner = Callable[..., subprocess.CompletedProcess[str]]


@dataclass(frozen=True)
class NamespacePlan:
    name: str
    host_veth: str
    worker_veth: str
    host_ipv4: str
    worker_ipv4: str
    host_ipv6: str
    worker_ipv6: str

    def __post_init__(self):
        for value in (self.name, self.host_veth, self.worker_veth):
            if not _NAME.fullmatch(value):
                raise ValueError("namespace and interface names must be short safe identifiers")
        for host, worker, version in (
            (self.host_ipv4, self.worker_ipv4, 4),
            (self.host_ipv6, self.worker_ipv6, 6),
        ):
            h, w = ipaddress.ip_interface(host), ipaddress.ip_interface(worker)
            if h.version != version or w.version != version or h.network != w.network:
                raise ValueError("host and worker addresses must share the expected IP subnet")
            if h.ip == w.ip or h.ip.is_loopback or w.ip.is_loopback or h.ip.is_multicast or w.ip.is_multicast:
                raise ValueError("invalid point-to-point addresses")


class LinuxNetworkNamespaceProvisioner:
    def __init__(self, *, runner: Runner = subprocess.run, require_root: bool = True, timeout_seconds: int = 10):
        self._runner = runner
        self._require_root = require_root
        self._timeout = timeout_seconds

    def _run(self, args: Sequence[str]) -> None:
        try:
            result = self._runner(
                list(args), check=False, capture_output=True, text=True,
                timeout=self._timeout, shell=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise NamespaceProvisionError("network namespace command failed") from exc
        if result.returncode:
            raise NamespaceProvisionError("network namespace command returned failure")

    def provision(self, plan: NamespacePlan) -> None:
        if self._require_root and os.geteuid() != 0:
            raise NamespaceProvisionError("CAP_NET_ADMIN/root is required; host networking is not an allowed fallback")
        created = False
        veth_created = False
        try:
            self._run(["ip", "netns", "add", plan.name])
            created = True
            self._run(["ip", "link", "add", plan.host_veth, "type", "veth", "peer", "name", plan.worker_veth])
            veth_created = True
            self._run(["ip", "link", "set", plan.worker_veth, "netns", plan.name])
            self._run(["ip", "addr", "add", plan.host_ipv4, "dev", plan.host_veth])
            self._run(["ip", "-6", "addr", "add", plan.host_ipv6, "dev", plan.host_veth])
            self._run(["ip", "link", "set", plan.host_veth, "up"])
            self._run(["ip", "netns", "exec", plan.name, "ip", "addr", "add", plan.worker_ipv4, "dev", plan.worker_veth])
            self._run(["ip", "netns", "exec", plan.name, "ip", "-6", "addr", "add", plan.worker_ipv6, "dev", plan.worker_veth])
            self._run(["ip", "netns", "exec", plan.name, "ip", "link", "set", "lo", "up"])
            self._run(["ip", "netns", "exec", plan.name, "ip", "link", "set", plan.worker_veth, "up"])
            gateway4 = str(ipaddress.ip_interface(plan.host_ipv4).ip)
            gateway6 = str(ipaddress.ip_interface(plan.host_ipv6).ip)
            self._run(["ip", "netns", "exec", plan.name, "ip", "route", "replace", "default", "via", gateway4])
            self._run(["ip", "netns", "exec", plan.name, "ip", "-6", "route", "replace", "default", "via", gateway6])
        except Exception:
            if veth_created:
                try:
                    self._run(["ip", "link", "del", plan.host_veth])
                except Exception:
                    pass
            if created:
                try:
                    self._run(["ip", "netns", "del", plan.name])
                except Exception:
                    pass
            raise

    def remove(self, name: str) -> None:
        if not _NAME.fullmatch(name):
            raise ValueError("invalid namespace name")
        if self._require_root and os.geteuid() != 0:
            raise NamespaceProvisionError("CAP_NET_ADMIN/root is required for namespace removal")
        self._run(["ip", "netns", "del", name])
