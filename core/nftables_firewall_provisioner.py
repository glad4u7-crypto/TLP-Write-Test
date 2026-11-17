"""Per-worker nftables policy: default DROP, one pinned TCP proxy endpoint.

The table is installed inside the worker network namespace. Direct DNS, QUIC,
other TCP/UDP ports, and arbitrary destinations are not permitted. The proxy
must listen on the host-side veth address and enforce destination pinning.
"""
from __future__ import annotations

import ipaddress
import os
import re
import subprocess
from typing import Callable, Sequence


class FirewallProvisionError(RuntimeError):
    pass


_NAME = re.compile(r"^[a-z][a-z0-9_-]{0,9}$")
Runner = Callable[..., subprocess.CompletedProcess[str]]


def _proxy_address(value: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address:
    address = ipaddress.ip_address(value)
    if address.is_unspecified or address.is_multicast or address.is_loopback or address.is_link_local:
        raise ValueError("proxy address must be a usable unicast address")
    return address


class NftablesFirewallProvisioner:
    def __init__(self, *, runner: Runner = subprocess.run, require_root: bool = True, timeout_seconds: int = 10):
        self._runner = runner
        self._require_root = require_root
        self._timeout = timeout_seconds

    @staticmethod
    def render_ruleset(proxy_ips: Sequence[str], proxy_port: int) -> str:
        if type(proxy_port) is not int or not 1 <= proxy_port <= 65535:
            raise ValueError("proxy_port is invalid")
        if not isinstance(proxy_ips, (list, tuple)) or not proxy_ips or len(proxy_ips) > 8:
            raise ValueError("one to eight explicit proxy IPs are required")
        parsed = tuple(dict.fromkeys(_proxy_address(value) for value in proxy_ips))
        lines = [
            "add table inet apaa",
            "add chain inet apaa input { type filter hook input priority 0; policy drop; }",
            "add chain inet apaa output { type filter hook output priority 0; policy drop; }",
            'add rule inet apaa input iifname "lo" accept',
            'add rule inet apaa output oifname "lo" accept',
            "add rule inet apaa input ct state established,related accept",
            "add rule inet apaa output ct state established,related accept",
            # IPv6 neighbour discovery is link-local control traffic, not Internet egress.
            "add rule inet apaa input ip6 saddr fe80::/10 icmpv6 type { nd-neighbor-solicit, nd-neighbor-advert } accept",
            "add rule inet apaa output ip6 daddr ff02::/16 icmpv6 type nd-neighbor-solicit accept",
        ]
        for address in parsed:
            family = "ip" if address.version == 4 else "ip6"
            lines.append(
                f"add rule inet apaa output {family} daddr {address.compressed} "
                f"tcp dport {proxy_port} ct state new accept"
            )
        return "\n".join(lines) + "\n"

    def install(self, namespace: str, proxy_ips: Sequence[str], proxy_port: int) -> None:
        if not _NAME.fullmatch(namespace):
            raise ValueError("invalid network namespace name")
        if self._require_root and os.geteuid() != 0:
            raise FirewallProvisionError("CAP_NET_ADMIN/root is required; firewall bypass is forbidden")
        ruleset = self.render_ruleset(proxy_ips, proxy_port)
        try:
            result = self._runner(
                ["ip", "netns", "exec", namespace, "nft", "-f", "-"],
                input=ruleset, check=False, capture_output=True, text=True,
                timeout=self._timeout, shell=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise FirewallProvisionError("nftables installation failed") from exc
        if result.returncode:
            raise FirewallProvisionError("nftables rejected the worker policy")

    def verify_ruleset(self, namespace: str) -> str:
        if not _NAME.fullmatch(namespace):
            raise ValueError("invalid network namespace name")
        if self._require_root and os.geteuid() != 0:
            raise FirewallProvisionError("CAP_NET_ADMIN/root is required for firewall inspection")
        try:
            result = self._runner(
                ["ip", "netns", "exec", namespace, "nft", "list", "table", "inet", "apaa"],
                check=False, capture_output=True, text=True,
                timeout=self._timeout, shell=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise FirewallProvisionError("nftables inspection failed") from exc
        if result.returncode or "policy drop" not in result.stdout:
            raise FirewallProvisionError("worker firewall is absent or not default DROP")
        return result.stdout
