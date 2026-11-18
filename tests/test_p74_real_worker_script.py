from __future__ import annotations

import pytest

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
    assert evidence["proxy_error"] == "ERR_PROXY_CONNECTION_FAILED"
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
    import pytest

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


def test_proxy_outage_probe_rejects_container_or_chromium_setup_failure(monkeypatch):
    from subprocess import CompletedProcess
    import pytest

    monkeypatch.setattr(
        qualification.subprocess, "run",
        lambda *args, **kwargs: CompletedProcess(args[0], 125, "", "Error: container is not running"),
    )
    with pytest.raises(RuntimeError, match="did not reach a Chromium proxy failure"):
        qualification._probe_proxy_outage(["podman", "exec"], "Allowed Marker", "ipv4")


def test_user_namespace_probe_requires_mapping_and_chroot(monkeypatch):
    from subprocess import CompletedProcess

    captured = {}
    def successful(command, **kwargs):
        captured["command"] = command
        return CompletedProcess(command, 0, "USERNS_CHROOT_OK\n", "")

    monkeypatch.setattr(qualification.subprocess, "run", successful)
    evidence = qualification._probe_user_namespace("worker-container")
    assert evidence["user_namespace_chroot_available"] is True
    assert "unshare(0x10000000)" in captured["command"][-1]
    assert "USERNS_CHROOT_OK" in captured["command"][-1]


def test_user_namespace_probe_fails_closed_when_mapping_or_chroot_fails(monkeypatch):
    from subprocess import CompletedProcess

    monkeypatch.setattr(
        qualification.subprocess, "run",
        lambda command, **kwargs: CompletedProcess(command, 12, "USERNS_CHROOT_ERR 1\n", ""),
    )
    evidence = qualification._probe_user_namespace("worker-container")
    assert evidence["user_namespace_chroot_available"] is False
    assert evidence["exit_code"] == 12


def test_chromium_qualification_disables_crashpad_without_disabling_browser_sandbox():
    import inspect

    source = inspect.getsource(qualification)
    assert '"--disable-crashpad-for-testing"' in source
    assert '"--no-sandbox"' not in source


def test_chromium_failure_diagnostics_are_bounded_and_redacted():
    from subprocess import CompletedProcess

    page = CompletedProcess(
        ["chromium"], 0,
        "<html>ERR_TUNNEL_CONNECTION_FAILED https://example.com/private?token=hidden</html>",
        "ERR_TUNNEL_CONNECTION_FAILED Authorization: Bearer secret-token user@example.com",
    )
    details = qualification._chromium_failure_details(page, "ipv4", "Example Domain")

    assert details["family"] == "ipv4"
    assert details["exit_code"] == 0
    assert details["stdout_html_present"] is True
    assert details["expected_marker_present"] is False
    assert details["stderr_bytes"] > 0
    assert "ERR_TUNNEL_CONNECTION_FAILED" in details["stderr_markers"]
    serialized = repr(details)
    for secret in ("hidden", "secret-token", "user@example.com", "/private"):
        assert secret not in serialized


def test_chromium_uses_explicit_plain_http_proxy_uri_for_both_address_families():
    assert qualification._http_proxy_uri("198.18.0.1", 3128) == "http://198.18.0.1:3128"
    assert qualification._http_proxy_uri("2001:db8:1::1", 3128) == "http://[2001:db8:1::1]:3128"


def test_proxy_tcp_preflight_builds_valid_multiline_python(monkeypatch):
    from subprocess import CompletedProcess

    captured = {}
    def successful(command, **kwargs):
        captured["command"] = command
        return CompletedProcess(command, 0, "APAA_PROXY_TCP_CONNECTED\n", "")

    monkeypatch.setattr(qualification.subprocess, "run", successful)
    result = qualification._probe_proxy_tcp("worker-container", "198.18.0.1", 3128)

    assert result["connected"] is True
    code = captured["command"][-1]
    assert "import socket,sys\n" in code
    assert "\\n" not in code


def test_chromium_local_dump_dom_smoke_requires_expected_marker(monkeypatch, tmp_path):
    from subprocess import CompletedProcess

    captured = {}
    def successful(command, cgroup_dir, timeout=45):
        captured["command"] = command
        return CompletedProcess(command, 0, "<html>APAA_LOCAL_DUMP_DOM_OK</html>", ""), {"snapshot_count": 1}

    monkeypatch.setattr(qualification, "_run_chromium_with_fd_snapshots", successful)
    result, diagnostics = qualification._probe_chromium_local_dump_dom(
        "worker-container", "chromium", tmp_path,
    )

    assert result["marker_present"] is True
    assert diagnostics["snapshot_count"] == 1
    assert "data:text/html," in captured["command"][-1]


def test_command_timeout_diagnostics_are_redacted(monkeypatch):
    import subprocess
    def timeout(command, **kwargs):
        raise subprocess.TimeoutExpired(command, kwargs["timeout"], output=b"", stderr=b"Authorization: Bearer timeout-secret")
    monkeypatch.setattr(qualification.subprocess, "run", timeout)

    with pytest.raises(RuntimeError, match="timed out") as error:
        qualification._run(["podman", "exec", "container", "chromium"], timeout=4)

    assert "timeout-secret" not in str(error.value)
    assert "[REDACTED]" in str(error.value)


def test_chromium_worker_disables_histogram_shared_memory_fd_handoff():
    import inspect

    source = inspect.getsource(qualification)
    assert source.count("--disable-features=PassHistogramSharedMemoryOnLaunch") >= 3
    assert '"--no-sandbox"' not in source


def test_chromium_exec_wrapper_closes_inherited_fds_and_preserves_stdio():
    command = qualification._podman_chromium_command(
        "worker-container", "chromium", ["--headless=new", "--dump-dom", "data:text/html,ok"]
    )
    assert command[:7] == [
        "podman", "exec", "--user", "65532:65532",
        "worker-container", "python3", "-c",
    ]
    wrapper = command[7]
    assert "os.listdir('/proc/self/fd')" in wrapper
    assert "if fd>2: os.close(fd)" in wrapper
    assert "os.execvp(sys.argv[1], sys.argv[1:])" in wrapper
    assert command[8:] == ["chromium", "--headless=new", "--dump-dom", "data:text/html,ok"]



def test_fd_ownership_crash_pid_and_stack_frames_are_extracted():
    stderr = (
        "[16:16:1117/183349.367321:ERROR:content/browser/network_service_instance_impl.cc:652] "
        "Network service crashed or was terminated, restarting service.\n"
        "Crashing due to FD ownership violation:\n"
        "#0 0x55c81044543e <unknown>\n"
        "#1 0x55c81043c19c <unknown>\n"
    )
    result = qualification._fd_ownership_crash_identity(stderr)
    assert result["detected"] is True
    assert result["log_pid"] == 16
    assert result["log_tid"] == 16
    assert result["preceding_log_pid"] == 16
    assert result["preceding_log_tid"] == 16
    assert result["pid_attribution"] == "preceding_prefixed_log_line_only"
    assert result["stack_frames"] == [
        {"frame": 0, "address": "0x55c81044543e"},
        {"frame": 1, "address": "0x55c81043c19c"},
    ]


def test_fd_ownership_log_pid_maps_to_host_pid_snapshot():
    failure = {
        "fd_ownership_log_pid": 16,
        "fd_ownership_stack_frames": [{"frame": 0, "address": "0x1150"}],
    }
    diagnostics = {
        "snapshots": [
            {"processes": [
                {"pid": 8271, "ppid": 8268, "comm": "chromium", "executable": "chromium",
                 "role": "other", "start_time_ticks": "11676", "fd_count_observed": 148,
                 "executable_mappings": [{"start": "0x1000", "end": "0x2000",
                                           "file_offset": "0x100", "module": "chromium"}],
                 "status": {"nspid": "8271 16", "uid": "65532 65532 65532 65532", "seccomp": "2"}},
            ]},
        ],
    }
    mapped = qualification._map_failure_to_fd_snapshot(failure, diagnostics)
    assert mapped["host_pid"] == 8271
    assert mapped["container_pid"] == "16"
    assert mapped["fd_count_observed"] == 148
    assert mapped["stack_frames_with_module_offsets"][0]["module"] == "chromium"
    assert mapped["stack_frames_with_module_offsets"][0]["module_offset"] == "0x250"



def test_chromium_build_id_probe_embedded_python_is_valid(monkeypatch):
    from subprocess import CompletedProcess

    def fake_run(command, **kwargs):
        compile(command[-1], "<chromium-build-id-probe>", "exec")
        return CompletedProcess(command, 0, "0123456789abcdef0123456789abcdef01234567\n", "")

    monkeypatch.setattr(qualification.subprocess, "run", fake_run)
    assert qualification._chromium_binary_build_id("worker-container") == "0123456789abcdef0123456789abcdef01234567"


def test_symbolication_fails_closed_when_debug_tools_are_missing(monkeypatch):
    monkeypatch.setattr(qualification.shutil, "which", lambda _name: None)
    result = qualification._symbolize_failure_frames({"process_mapping": {}}, "0123456789abcdef")
    assert result == {"status": "addr2line-unavailable", "build_id": "0123456789abcdef", "frames": []}



def test_crash_pid_mapping_prefers_process_whose_executable_contains_stack_pc():
    failure = {
        "fd_ownership_log_pid": 17,
        "fd_ownership_stack_frames": [{"frame": 0, "address": "0x1150"}],
    }
    diagnostics = {
        "snapshots": [
            {"wall_time_ns": 100, "processes": [
                {"pid": 500, "ppid": 490, "comm": "chromium", "executable": "chromium",
                 "role": "other", "start_time_ticks": "10", "fd_count_observed": 148,
                 "executable_mappings": [{"start": "0x1000", "end": "0x2000",
                                           "file_offset": "0x100", "module": "chromium"}],
                 "status": {"nspid": "500 17 1"}},
            ]},
            {"wall_time_ns": 200, "processes": [
                {"pid": 501, "ppid": 490, "comm": "chromium", "executable": "chromium",
                 "role": "other", "start_time_ticks": "20", "fd_count_observed": 148,
                 "executable_mappings": [{"start": "0x3000", "end": "0x4000",
                                           "file_offset": "0x100", "module": "chromium"}],
                 "status": {"nspid": "501 17"}},
            ]},
        ],
    }
    mapped = qualification._map_failure_to_fd_snapshot(failure, diagnostics)
    assert mapped["host_pid"] == 500
    assert mapped["nspid_match_index"] == 1
    assert mapped["stack_frame_match_count"] == 1
    assert mapped["stack_frames_with_module_offsets"][0]["module_offset"] == "0x250"



def test_unprefixed_fd_crash_stack_maps_to_child_process_not_log_prefix_pid():
    failure = {
        "fd_ownership_log_pid": 17,
        "fd_ownership_stack_frames": [{"frame": 0, "address": "0x1150"}],
    }
    diagnostics = {
        "snapshots": [
            {"wall_time_ns": 100, "processes": [
                {"pid": 8632, "ppid": 8629, "comm": "chromium", "executable": "chromium",
                 "role": "other", "start_time_ticks": "6877", "fd_count_observed": 148,
                 "executable_mappings": [{"start": "0x3000", "end": "0x4000",
                                           "file_offset": "0x100", "module": "chromium"}],
                 "status": {"nspid": "8632 17"}},
                {"pid": 15027, "ppid": 8632, "comm": "chromium", "executable": "chromium",
                 "role": "other", "start_time_ticks": "11475", "fd_count_observed": 12,
                 "executable_mappings": [{"start": "0x1000", "end": "0x2000",
                                           "file_offset": "0x100", "module": "chromium"}],
                 "status": {"nspid": "15027 255"}},
            ]},
        ],
    }
    mapped = qualification._map_failure_to_fd_snapshot(failure, diagnostics)
    assert mapped["host_pid"] == 15027
    assert mapped["container_pid"] == "255"
    assert mapped["mapping_confidence"] == "all_stack_frames_match_candidate_process_image"
    assert mapped["log_process_mapping"]["host_pid"] == 8632



def test_symbolizer_prefers_exact_local_debian_dbgsym(monkeypatch, tmp_path):
    from subprocess import CompletedProcess

    build_id = "4a74f6497529d42bb61262c76d7b1add49c4dea6"
    debug_file = tmp_path / ".build-id" / build_id[:2] / (build_id[2:] + ".debug")
    debug_file.parent.mkdir(parents=True)
    debug_file.write_bytes(b"test-debug-symbol-placeholder")
    monkeypatch.setenv("APAA_CHROMIUM_DEBUG_ROOT", str(tmp_path))
    monkeypatch.setattr(
        qualification.shutil, "which",
        lambda name: "/usr/bin/eu-addr2line" if name == "eu-addr2line" else None,
    )
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        return CompletedProcess(command, 0, "base::ScopedFD::reset()\nsrc/base/files/scoped_file.cc:123\n", "")

    monkeypatch.setattr(qualification.subprocess, "run", fake_run)
    result = qualification._symbolize_failure_frames(
        {"process_mapping": {"stack_frames_with_module_offsets": [
            {"frame": 0, "module_offset": "0x9c6343e"},
        ]}},
        build_id,
    )
    assert result["status"] == "symbolized"
    assert result["symbol_source"] == "exact-debian-dbgsym"
    assert result["frames"][0]["function"] == "base::ScopedFD::reset()"
    assert captured["command"][-1] == "0x9c6343e"



def test_chromium_dynamic_close_symbol_is_parsed_and_stack_pc_annotated(monkeypatch):
    from subprocess import CompletedProcess

    def fake_run(command, **kwargs):
        return CompletedProcess(command, 0, "0000000009c63400 T close\n", "")

    monkeypatch.setattr(qualification.subprocess, "run", fake_run)
    symbols = qualification._chromium_dynamic_symbols("worker-container")
    assert int(symbols["close_symbol_offset"], 16) == 0x9c63400
    failure = {"process_mapping": {"stack_frames_with_module_offsets": [
        {"frame": 1, "module": "chromium", "module_offset": "0x9c6343e"},
        {"frame": 2, "module": "chromium", "module_offset": "0x9c64000"},
    ]}}
    matches = qualification._annotate_known_dynamic_symbols(failure, symbols)
    assert matches == [{
        "frame": 1,
        "module_offset": "0x9c6343e",
        "candidate_symbol": "close",
        "symbol_offset": "0x9c63400",
        "interpretation": "near_exported_close_symbol_candidate",
    }]



def test_disassembly_helper_is_bounded_and_uses_only_chromium_offsets(monkeypatch):
    from subprocess import CompletedProcess

    commands = []

    def fake_run(command, **kwargs):
        commands.append(command)
        return CompletedProcess(command, 0, "0000000009c5a100 <close>:\n  9c5a100: 48 89 e5 mov %rsp,%rbp\n", "")

    monkeypatch.setattr(qualification.subprocess, "run", fake_run)
    failure = {"process_mapping": {"stack_frames_with_module_offsets": [
        {"frame": 0, "module": "chromium", "module_offset": "0x9c6343e"},
        {"frame": 1, "module": "chromium", "module_offset": "0x9c5a19c"},
        {"frame": 2, "module": "libc.so.6", "module_offset": "0x1234"},
    ]}}
    windows = qualification._disassemble_chromium_stack("worker-container", failure)
    assert len(windows) == 2
    assert len(commands) == 2
    assert all("objdump" in command for command in commands)
    assert all("--start-address=" in " ".join(command) for command in commands)


def test_fd_ownership_failure_does_not_claim_preceding_log_pid_is_crash_pid():
    from subprocess import CompletedProcess

    stderr = (
        "[19:19:1118/014149.894302:ERROR:network_service.cc:652] "
        "Network service crashed or was terminated.\\n"
        "Crashing due to FD ownership violation:\\n"
        "#0 0x55b8e346843e <unknown>\\n"
    )
    details = qualification._chromium_failure_details(
        CompletedProcess(["chromium"], 0, "", stderr), "local-data-url", "marker",
    )
    assert details["fd_ownership_preceding_log_pid"] == 19
    assert details["fd_ownership_preceding_log_tid"] == 19
    assert details["fd_ownership_pid_attribution"] == "preceding_prefixed_log_line_only"
    assert details["fd_ownership_crash_pid_proven"] is False
    assert details["fd_ownership_instrumentation_present"] is False


def test_fd_ownership_structured_diagnostic_proves_fatal_process_identity():
    from subprocess import CompletedProcess

    stderr = (
        "APAA_FD_OWNERSHIP_DIAG fd=7 operation=close previous_owned=1 "
        "requested_owned=0 pid=288 tid=288\\n"
        "Crashing due to FD ownership violation:\\n"
        "#0 0x55b8e346843e <unknown>\\n"
    )
    details = qualification._chromium_failure_details(
        CompletedProcess(["chromium"], 0, "", stderr), "local-data-url", "marker",
    )
    assert details["fd_ownership_instrumentation_present"] is True
    assert details["fd_ownership_crash_pid_proven"] is True
    assert details["fd_ownership_diagnostics"] == [{
        "fd": 7, "operation": "close", "previous_owned": True,
        "requested_owned": False, "pid": 288, "tid": 288,
    }]


def test_chromium_package_metadata_is_bounded_for_exact_dbgsym_lookup(monkeypatch):
    from subprocess import CompletedProcess

    def fake_run(command, **kwargs):
        return CompletedProcess(command, 0, "156.0.8078.79-1~deb12u1| amd64\\n", "")

    monkeypatch.setattr(qualification.subprocess, "run", fake_run)
    assert qualification._chromium_package_metadata("container-id") == (
        "156.0.8078.79-1~deb12u1", "amd64"
    )


def test_chromium_package_metadata_rejects_unknown_architecture(monkeypatch):
    from subprocess import CompletedProcess

    def fake_run(command, **kwargs):
        return CompletedProcess(command, 0, "156.0.8078.79-1~deb12u1| mipsel\\n", "")

    monkeypatch.setattr(qualification.subprocess, "run", fake_run)
    assert qualification._chromium_package_metadata("container-id") == (
        "156.0.8078.79-1~deb12u1", None
    )
