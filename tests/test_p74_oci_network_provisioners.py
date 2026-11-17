from __future__ import annotations

import ipaddress
import json
import socket
import subprocess

import pytest

from core.cgroup_seccomp_provisioner import IsolationEnforcementError, validate_seccomp_profile
from core.linux_network_namespace import (
    LinuxNetworkNamespaceProvisioner,
    NamespacePlan,
    NamespaceProvisionError,
)
from core.nftables_firewall_provisioner import NftablesFirewallProvisioner
from core.pinned_egress import PinnedEgressError, connect_pinned, resolve_and_pin


class Runner:
    def __init__(self, fail_at=None, stdout=""):
        self.calls = []
        self.fail_at = fail_at
        self.stdout = stdout

    def __call__(self, command, **kwargs):
        self.calls.append((command, kwargs))
        rc = 1 if self.fail_at == len(self.calls) else 0
        return subprocess.CompletedProcess(command, rc, self.stdout, "")


def plan():
    return NamespacePlan(
        name="apaa-test",
        host_veth="apahost0",
        worker_veth="apawork0",
        host_ipv4="198.18.0.1/30",
        worker_ipv4="198.18.0.2/30",
        host_ipv6="2001:db8:1::1/64",
        worker_ipv6="2001:db8:1::2/64",
    )


def test_namespace_provisioner_uses_separate_netns_and_dual_stack_routes():
    runner = Runner()
    provisioner = LinuxNetworkNamespaceProvisioner(runner=runner, require_root=False)
    provisioner.provision(plan())
    commands = [call[0] for call in runner.calls]
    assert commands[0] == ["ip", "netns", "add", "apaa-test"]
    assert ["ip", "link", "set", "apawork0", "netns", "apaa-test"] in commands
    assert ["ip", "netns", "exec", "apaa-test", "ip", "route", "replace", "default", "via", "198.18.0.1"] in commands
    assert ["ip", "netns", "exec", "apaa-test", "ip", "-6", "route", "replace", "default", "via", "2001:db8:1::1"] in commands


def test_namespace_provisioner_rolls_back_after_failure():
    runner = Runner(fail_at=3)
    provisioner = LinuxNetworkNamespaceProvisioner(runner=runner, require_root=False)
    with pytest.raises(NamespaceProvisionError):
        provisioner.provision(plan())
    assert runner.calls[-2][0] == ["ip", "link", "del", "apahost0"]
    assert runner.calls[-1][0] == ["ip", "netns", "del", "apaa-test"]


def test_namespace_plan_rejects_cross_subnet_or_wrong_family():
    with pytest.raises(ValueError):
        NamespacePlan("apaa-test", "apahost0", "apawork0", "10.0.0.1/30", "10.0.0.6/30",
                      "2001:db8:1::1/64", "2001:db8:1::2/64")


def test_nftables_policy_is_default_drop_and_proxy_only():
    rules = NftablesFirewallProvisioner.render_ruleset(["198.18.0.1", "2001:db8:1::1"], 3128)
    assert "policy drop" in rules
    assert "ip daddr 198.18.0.1 tcp dport 3128" in rules
    assert "ip6 daddr 2001:db8:1::1 tcp dport 3128" in rules
    assert "udp dport" not in rules
    assert "dport 53" not in rules
    assert "dport 443" not in rules


@pytest.mark.parametrize("ip", ["127.0.0.1", "169.254.1.1", "224.0.0.1", "::1", "fe80::1"])
def test_nftables_rejects_special_proxy_addresses(ip):
    with pytest.raises(ValueError):
        NftablesFirewallProvisioner.render_ruleset([ip], 3128)


def test_nftables_install_uses_namespace_and_stdin_ruleset():
    runner = Runner()
    provisioner = NftablesFirewallProvisioner(runner=runner, require_root=False)
    provisioner.install("apaa-test", ["198.18.0.1"], 3128)
    command, kwargs = runner.calls[0]
    assert command == ["ip", "netns", "exec", "apaa-test", "nft", "-f", "-"]
    assert "policy drop" in kwargs["input"]
    assert kwargs["shell"] is False


def _dns_record(ip):
    address = ipaddress.ip_address(ip)
    family = socket.AF_INET if address.version == 4 else socket.AF_INET6
    sockaddr = (address.compressed, 443) if address.version == 4 else (address.compressed, 443, 0, 0)
    return (family, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", sockaddr)


def test_dns_pin_rejects_mixed_public_and_private_answers():
    def resolver(*args):
        return [_dns_record("8.8.8.8"), _dns_record("10.0.0.1")]
    with pytest.raises(PinnedEgressError):
        resolve_and_pin("example.com", 443, resolver=resolver)


def test_dns_pin_keeps_ipv4_and_ipv6_answers():
    def resolver(*args):
        return [_dns_record("8.8.8.8"), _dns_record("2001:4860:4860::8888")]
    pinned = resolve_and_pin("example.com", 443, resolver=resolver)
    assert pinned.addresses == ("8.8.8.8", "2001:4860:4860::8888")


class FakeSocket:
    def __init__(self, peer):
        self.peer = peer
        self.connected = None
        self.closed = False

    def settimeout(self, value):
        self.timeout = value

    def connect(self, target):
        self.connected = target

    def getpeername(self):
        return (self.peer, 443)

    def close(self):
        self.closed = True


def test_pinned_dial_uses_numeric_address_without_hostname_lookup():
    pinned = resolve_and_pin("example.com", 443, resolver=lambda *args: [_dns_record("8.8.8.8")])
    fake = FakeSocket("8.8.8.8")
    sock = connect_pinned(pinned, "8.8.8.8", socket_factory=lambda *args: fake)
    assert sock is fake
    assert fake.connected == ("8.8.8.8", 443)


def test_pinned_dial_rejects_address_not_in_dns_pin():
    pinned = resolve_and_pin("example.com", 443, resolver=lambda *args: [_dns_record("8.8.8.8")])
    with pytest.raises(PinnedEgressError):
        connect_pinned(pinned, "1.1.1.1", socket_factory=lambda *args: FakeSocket("1.1.1.1"))


def test_seccomp_profile_requires_deny_by_default(tmp_path):
    profile = tmp_path / "seccomp.json"
    profile.write_text(json.dumps({
        "defaultAction": "SCMP_ACT_ERRNO",
        "syscalls": [{"names": ["read", "write"], "action": "SCMP_ACT_ALLOW"}],
    }))
    assert validate_seccomp_profile(profile)["defaultAction"] == "SCMP_ACT_ERRNO"


def test_seccomp_profile_rejects_allow_by_default(tmp_path):
    profile = tmp_path / "seccomp.json"
    profile.write_text(json.dumps({
        "defaultAction": "SCMP_ACT_ALLOW",
        "syscalls": [{"names": ["read"], "action": "SCMP_ACT_ALLOW"}],
    }))
    with pytest.raises(IsolationEnforcementError):
        validate_seccomp_profile(profile)
