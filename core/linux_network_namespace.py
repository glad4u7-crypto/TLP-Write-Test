"""Linux network-namespace and veth provisioner with fail-closed rollback."""
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
        names = (self.name, self.host_veth, self.worker_veth)
        if any(type(value) is not str or not _NAME.fullmatch(value) for value in names):
            raise ValueError("namespace and interface names must be short safe identifiers")
        if len(set(names)) != 3:
            raise ValueError("namespace, host veth and worker veth names must be distinct")
        for host, worker, version, prefix in (
            (self.host_ipv4, self.worker_ipv4, 4, 30),
            (self.host_ipv6, self.worker_ipv6, 6, 64),
        ):
            h, w = ipaddress.ip_interface(host), ipaddress.ip_interface(worker)
            if h.version != version or w.version != version or h.network != w.network:
                raise ValueError("host and worker addresses must share the expected IP subnet")
            if h.network.prefixlen != prefix:
                raise ValueError("veth subnet must use the required point-to-point prefix")
            if (h.ip == w.ip or h.ip not in h.network or w.ip not in w.network
                    or h.ip.is_unspecified or w.ip.is_unspecified
                    or h.ip.is_loopback or w.ip.is_loopback
                    or h.ip.is_multicast or w.ip.is_multicast):
                raise ValueError("invalid point-to-point addresses")


class LinuxNetworkNamespaceProvisioner:
    def __init__(self, *, runner: Runner = subprocess.run, require_root: bool = True, timeout_seconds: int = 10):
        if type(timeout_seconds) is not int or not 1 <= timeout_seconds <= 60:
            raise ValueError("timeout_seconds is invalid")
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

    def remove(self, plan: NamespacePlan) -> None:
        if not isinstance(plan, NamespacePlan):
            raise TypeError("cleanup requires the original immutable NamespacePlan")
        if self._require_root and os.geteuid() != 0:
            raise NamespaceProvisionError("CAP_NET_ADMIN/root is required for namespace cleanup")
        errors = []
        try:
            self._run(["ip", "link", "del", plan.host_veth])
        except Exception as exc:
            errors.append(exc)
        try:
            self._run(["ip", "netns", "del", plan.name])
        except Exception as exc:
            errors.append(exc)
        if errors:
            raise NamespaceProvisionError("namespace or host veth cleanup was incomplete") from errors[0]
