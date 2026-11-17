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

def test_packet_capture_rejects_unrelated_arp_and_non_link_local_ndp(monkeypatch, tmp_path):
    from subprocess import CompletedProcess
    import pytest

    outputs = [
        "ARP, Request who-has 198.18.0.99 tell 198.18.0.2",
        "IP6 2001:db8:1::2 > ff02::1:ff00:1: ICMP6, neighbor solicitation",
    ]
    for output in outputs:
        monkeypatch.setattr(
            qualification, "_run",
            lambda command, timeout=90, output=output: CompletedProcess(command, 0, output, ""),
        )
        with pytest.raises(RuntimeError, match="non-proxy worker traffic"):
            qualification._audit_worker_capture(
                tmp_path / "worker.pcap",
                worker_ips={"198.18.0.2", "2001:db8:1::2"},
                proxy_ips={"198.18.0.1", "2001:db8:1::1"},
                proxy_port=3128,
            )


def test_packet_capture_accepts_only_link_local_ndp(monkeypatch, tmp_path):
    from subprocess import CompletedProcess

    output = "IP6 fe80::2 > ff02::1:ff00:1: ICMP6, neighbor solicitation"
    monkeypatch.setattr(
        qualification, "_run",
        lambda command, timeout=90: CompletedProcess(command, 0, output, ""),
    )
    # The capture contains only permitted control traffic, so the parser
    # correctly rejects it later because no approved proxy TCP flow exists.
    import pytest
    with pytest.raises(RuntimeError, match="did not observe the approved proxy TCP flow"):
        qualification._audit_worker_capture(
            tmp_path / "worker.pcap",
            worker_ips={"198.18.0.2", "2001:db8:1::2"},
            proxy_ips={"198.18.0.1", "2001:db8:1::1"},
            proxy_port=3128,
        )


def test_proxy_outage_probe_rejects_successful_direct_fallback(monkeypatch):
    from subprocess import CompletedProcess
    import pytest

    monkeypatch.setattr(
        qualification.subprocess, "run",
        lambda *args, **kwargs: CompletedProcess(args[0], 0, "<html>Allowed Marker</html>", ""),
    )
    with pytest.raises(RuntimeError, match="reached the allowed page"):
        qualification._probe_proxy_outage(["chromium"], "Allowed Marker", "ipv4")


def test_proxy_outage_probe_records_failure_without_leaking_response(monkeypatch):
    from subprocess import CompletedProcess

    monkeypatch.setattr(
        qualification.subprocess, "run",
        lambda *args, **kwargs: CompletedProcess(args[0], 1, "ERR_PROXY_CONNECTION_FAILED", ""),
    )
    evidence = qualification._probe_proxy_outage(["chromium"], "Allowed Marker", "ipv4")
    assert evidence["allowed_marker_absent"] is True
    assert evidence["exit_code"] == 1
    assert len(evidence["output_sha256"]) == 64


def test_direct_egress_probe_requires_socket_level_network_denial(monkeypatch):
    from subprocess import CompletedProcess

    monkeypatch.setattr(
        qualification.subprocess, "run",
        lambda command, **kwargs: CompletedProcess(command, 1, "", "TimeoutError: timed out"),
    )
    evidence = qualification._probe_blocked(["podman", "exec", "id", "python3"], "direct TCP")
    assert evidence["denial"] == "timeout"
    assert len(evidence["output_sha256"]) == 64


def test_direct_egress_probe_rejects_runtime_or_executable_failure(monkeypatch):
    from subprocess import CompletedProcess
    import pytest

    monkeypatch.setattr(
        qualification.subprocess, "run",
        lambda command, **kwargs: CompletedProcess(command, 125, "", "Error: container is not running"),
    )
    with pytest.raises(RuntimeError, match="recognized socket-level denial"):
        qualification._probe_blocked(["podman", "exec", "id", "python3"], "direct TCP")


def test_qualification_command_error_identifies_action_and_redacts_url(monkeypatch):
    from subprocess import CompletedProcess
    import pytest

    monkeypatch.setattr(
        qualification.subprocess, "run",
        lambda command, **kwargs: CompletedProcess(command, 126, "", "failed https://example.invalid/path?token=secret"),
    )
    with pytest.raises(RuntimeError) as error:
        qualification._run(["podman", "exec", "--user", "65532:65532", "id", "/usr/bin/chromium"])
    assert "podman exec chromium" in str(error.value)
    assert "secret" not in str(error.value)


def test_udp_probe_records_seccomp_socket_creation_denial_separately(monkeypatch):
    from subprocess import CompletedProcess

    monkeypatch.setattr(
        qualification.subprocess, "run",
        lambda command, **kwargs: CompletedProcess(
            command, 1, "", "PermissionError: [Errno 1] Operation not permitted",
        ),
    )
    evidence = qualification._probe_blocked(
        ["podman", "exec", "id", "python3"], "direct UDP DNS",
        allow_seccomp_socket_denial=True,
    )
    assert evidence["denial"] == "seccomp_socket_creation_denied"
    with pytest.raises(RuntimeError, match="recognized socket-level denial"):
        qualification._probe_blocked(
            ["podman", "exec", "id", "python3"], "direct TCP",
        )
