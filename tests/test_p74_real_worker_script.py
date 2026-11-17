from __future__ import annotations

from scripts import p74_real_worker_chromium_e2e as qualification


def test_real_host_qualification_is_opt_in_and_does_not_touch_host(monkeypatch):
    monkeypatch.delenv("APAA_P74_REAL_HOST", raising=False)
    assert qualification.main() == 2


def test_real_host_qualification_rejects_unsafe_worker_id(monkeypatch):
    monkeypatch.setenv("APAA_P74_REAL_HOST", "1")
    monkeypatch.setenv("APAA_P74_WORKER_ID", "../host")
    assert qualification.main() == 2


def test_packet_capture_accepts_only_the_approved_proxy_flows(monkeypatch, tmp_path):
    from subprocess import CompletedProcess

    output = """reading from file worker.pcap, link-type EN10MB
IP 198.18.0.2.40000 > 198.18.0.1.3128: Flags [S]
IP6 2001:db8:1::2.40001 > 2001:db8:1::1.3128: Flags [S]
ARP, Request who-has 198.18.0.1 tell 198.18.0.2
IP6 fe80::2 > ff02::1:ff00:1: ICMP6, neighbor solicitation
"""
    monkeypatch.setattr(
        qualification, "_run",
        lambda command, timeout=90: CompletedProcess(command, 0, output, ""),
    )
    summary = qualification._audit_worker_capture(
        tmp_path / "worker.pcap",
        worker_ips={"198.18.0.2", "2001:db8:1::2"},
        proxy_ips={"198.18.0.1", "2001:db8:1::1"},
        proxy_port=3128,
    )
    assert summary["allowed_proxy_tcp_packets"] == 2
    assert summary["arp_packets"] == 1
    assert summary["ipv6_neighbor_discovery_packets"] == 1


def test_packet_capture_rejects_direct_dns_egress(monkeypatch, tmp_path):
    from subprocess import CompletedProcess
    import pytest

    output = "IP 198.18.0.2.53000 > 8.8.8.8.53: UDP, length 32"
    monkeypatch.setattr(
        qualification, "_run",
        lambda command, timeout=90: CompletedProcess(command, 0, output, ""),
    )
    with pytest.raises(RuntimeError, match="non-proxy worker traffic"):
        qualification._audit_worker_capture(
            tmp_path / "worker.pcap",
            worker_ips={"198.18.0.2"},
            proxy_ips={"198.18.0.1"},
            proxy_port=3128,
        )
