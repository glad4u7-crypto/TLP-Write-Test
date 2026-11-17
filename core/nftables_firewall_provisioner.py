"""Per-worker nftables policy: default DROP, exact proxy-only TCP egress."""
from __future__ import annotations

from collections import Counter
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
    if type(value) is not str:
        raise ValueError("proxy address must be text")
    address = ipaddress.ip_address(value)
    if (address.is_unspecified or address.is_multicast or address.is_loopback
            or address.is_link_local or address.is_reserved):
        raise ValueError("proxy address must be a usable unicast address")
    return address


def _chain_blocks(ruleset: str) -> dict[str, str]:
    blocks: dict[str, str] = {}
    current_name = None
    current_lines: list[str] = []
    depth = 0
    for raw in ruleset.splitlines():
        line = raw.strip()
        if current_name is None:
            match = re.match(r"^chain\s+([A-Za-z0-9_-]+)\s*\{", line)
            if not match:
                continue
            current_name = match.group(1)
            current_lines = [line]
            depth = line.count("{") - line.count("}")
        else:
            current_lines.append(line)
            depth += line.count("{") - line.count("}")
        if current_name is not None and depth == 0:
            if current_name in blocks:
                raise FirewallProvisionError("firewall contains a duplicate chain")
            blocks[current_name] = "\n".join(current_lines)
            current_name = None
            current_lines = []
    if current_name is not None:
        raise FirewallProvisionError("firewall contains an unterminated chain")
    return blocks


def _accept_rules(ruleset: str) -> Counter[str]:
    found: Counter[str] = Counter()
    for raw in ruleset.splitlines():
        line = raw.strip()
        if not line or line.startswith(("table ", "chain ", "type ", "hook ", "policy ")):
            continue
        if " accept" in line:
            if not line.endswith(" accept"):
                raise FirewallProvisionError("firewall ACCEPT rule has unsupported trailing expressions")
            found[line] += 1
        if re.search(r"\b(jump|goto|vmap)\b", line):
            raise FirewallProvisionError("firewall contains an indirect rule path")
    return found


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
            "add rule inet apaa input ip6 saddr fe80::/10 icmpv6 type nd-neighbor-solicit accept",
            "add rule inet apaa input ip6 saddr fe80::/10 icmpv6 type nd-neighbor-advert accept",
            "add rule inet apaa output ip6 saddr fe80::/10 ip6 daddr ff02::/16 icmpv6 type nd-neighbor-solicit accept",
            "add rule inet apaa output ip6 saddr fe80::/10 ip6 daddr fe80::/10 icmpv6 type nd-neighbor-advert accept",
            "add rule inet apaa output ip6 saddr fe80::/10 ip6 daddr ff02::/16 icmpv6 type nd-neighbor-advert accept",
        ]
        for address in parsed:
            family = "ip" if address.version == 4 else "ip6"
            lines.extend([
                f"add rule inet apaa input {family} saddr {address.compressed} "
                f"tcp sport {proxy_port} ct state established,related accept",
                f"add rule inet apaa output {family} daddr {address.compressed} "
                f"tcp dport {proxy_port} ct state established,related accept",
                f"add rule inet apaa output {family} daddr {address.compressed} "
                f"tcp dport {proxy_port} ct state new accept",
            ])
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

    def verify_ruleset(
        self, namespace: str, *, proxy_ips: Sequence[str] | None = None, proxy_port: int | None = None
    ) -> str:
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
        output = result.stdout if result.returncode == 0 else ""
        chain_names = re.findall(r"^\s*chain\s+([A-Za-z0-9_-]+)\s*\{", output, re.MULTILINE)
        if result.returncode or Counter(chain_names) != Counter({"input": 1, "output": 1}):
            raise FirewallProvisionError("worker firewall must contain exactly the input and output chains")
        if output.count("policy drop") != 2:
            raise FirewallProvisionError("worker firewall is absent or not default DROP")
        if proxy_ips is not None or proxy_port is not None:
            if proxy_ips is None or proxy_port is None:
                raise ValueError("both proxy_ips and proxy_port are required for strict verification")
            expected_script = self.render_ruleset(proxy_ips, proxy_port)
            # render_ruleset lines begin with 'add rule'; retain the exact rule body.
            expected_accepts = Counter(
                line.removeprefix("add rule inet apaa input ").removeprefix("add rule inet apaa output ")
                for line in expected_script.splitlines() if line.startswith("add rule ")
            )
            actual_accepts = _accept_rules(output)
            if actual_accepts != expected_accepts:
                raise FirewallProvisionError("firewall ACCEPT rules differ from the exact approved policy")
            # Parse full multiline chain declarations; rules can themselves contain braces.
            blocks = _chain_blocks(output)
            if set(blocks) != {"input", "output"}:
                raise FirewallProvisionError("firewall chain inventory is unexpected")
            for name, hook in (("input", "input"), ("output", "output")):
                if not re.search(
                    rf"type filter hook {hook} priority [^;]+;\s*policy drop;",
                    blocks[name],
                ):
                    raise FirewallProvisionError("firewall chain hook or policy is unexpected")
        return output
