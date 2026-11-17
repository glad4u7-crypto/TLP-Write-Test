"""Provision and qualify one disposable, isolated Chromium worker on a real Linux host.

This is opt-in and destructive only to uniquely named APAA resources created by
this run. It never enables public browsing. Requires a local digest-pinned
Chromium image, deny-by-default seccomp profile, delegated cgroup-v2 subtree,
Podman, iproute2 and nftables. The proxy is started on both host-side veth IPs;
it permits only the exact HTTPS hostname and dials a numeric address from one
validated DNS answer set. TLS remains end-to-end in Chromium (SNI/cert checks).
"""
from __future__ import annotations

import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
import time

from core.browser_security import canonicalize_https_url
from core.cgroup_seccomp_provisioner import (
    CgroupLimits,
    CgroupV2Provisioner,
    validate_seccomp_profile,
)
from core.linux_network_namespace import LinuxNetworkNamespaceProvisioner, NamespacePlan
from core.nftables_firewall_provisioner import NftablesFirewallProvisioner
from core.nftables_attestation import NftablesPolicy, attest_nftables_json
from core.oci_runtime_backend import OCIWorkerSpec, PodmanOCIRuntime, WorkerLimits
from core.oci_runtime_observer import PodmanWorkerObserver
from core.pinned_connect_proxy import PinnedConnectProxy


def _required(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise RuntimeError(f"required environment variable is missing: {name}")
    return value


def _run(command: list[str], timeout: int = 90) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, check=False, capture_output=True, text=True,
                            timeout=timeout, shell=False)
    if result.returncode:
        raise RuntimeError(f"qualification command failed: {command[0]}")
    return result


def _probe_blocked(command: list[str], description: str) -> None:
    result = subprocess.run(command, check=False, capture_output=True, text=True,
                             timeout=8, shell=False)
    if result.returncode == 0:
        raise RuntimeError(f"network bypass unexpectedly succeeded: {description}")


def _probe_proxy_outage(command: list[str], expected_marker: str, description: str) -> dict:
    """A dead mandatory proxy must not produce the allowed page via direct fallback."""
    result = subprocess.run(command, check=False, capture_output=True, text=True,
                            timeout=45, shell=False)
    output = (result.stdout or "") + (result.stderr or "")
    if expected_marker in output:
        raise RuntimeError(f"browser reached the allowed page while its proxy was unavailable: {description}")
    return {
        "exit_code": result.returncode,
        "output_sha256": hashlib.sha256(output.encode("utf-8")).hexdigest(),
        "allowed_marker_absent": True,
    }


def _audit_worker_capture(
    pcap_path: Path,
    *,
    worker_ips: set[str],
    proxy_ips: set[str],
    proxy_port: int,
) -> dict:
    output = _run(["tcpdump", "-nn", "-r", str(pcap_path)], timeout=30).stdout
    allowed_tcp = 0
    arp_packets = 0
    ndp_packets = 0
    unexpected = []
    endpoint_pattern = re.compile(r"\bIP6?\s+(\S+)\s+>\s+(\S+):")
    worker_v4 = next((value for value in worker_ips if ipaddress.ip_address(value).version == 4), None)
    host_v4 = next((value for value in proxy_ips if ipaddress.ip_address(value).version == 4), None)
    for line in output.splitlines():
        if "ARP," in line:
            # Only the expected worker -> veth-gateway resolution and its reply
            # are legitimate on this point-to-point link.
            expected_request = bool(worker_v4 and host_v4 and
                                    f"who-has {host_v4} tell {worker_v4}" in line)
            expected_reply = bool(host_v4 and f"Reply {host_v4} is-at " in line)
            if expected_request or expected_reply:
                arp_packets += 1
            else:
                unexpected.append(line[:240])
            continue
        match = endpoint_pattern.search(line)
        if not match:
            if line.strip() and not line.startswith(("reading from file", "tcpdump:")):
                unexpected.append(line[:240])
            continue
        source_text, destination_text = match.groups()
        # NDP is the only non-TCP exception. It must remain link-local and
        # use link-local or link-scoped multicast destinations; arbitrary
        # ICMPv6 traffic is not silently treated as harmless neighbour traffic.
        if "ICMP6" in line and ("neighbor solicitation" in line or "neighbor advertisement" in line):
            try:
                source_ip = ipaddress.ip_address(source_text)
                destination_ip = ipaddress.ip_address(destination_text.rstrip(":"))
            except ValueError:
                unexpected.append(line[:240])
                continue
            scoped_multicast = (destination_ip.version == 6 and destination_ip.is_multicast
                                and destination_ip.packed[1] & 0x0F == 2)
            if source_ip.version == 6 and source_ip.is_link_local and (
                    destination_ip.is_link_local or scoped_multicast):
                ndp_packets += 1
            else:
                unexpected.append(line[:240])
            continue
        try:
            source_ip_text, source_port_text = source_text.rsplit(".", 1)
            destination_ip_text, destination_port_text = destination_text.rsplit(".", 1)
            source_ip = ipaddress.ip_address(source_ip_text).compressed
            destination_ip = ipaddress.ip_address(destination_ip_text).compressed
            source_port = int(source_port_text)
            destination_port = int(destination_port_text)
        except (ValueError, IndexError):
            unexpected.append(line[:240])
            continue
        forward = source_ip in worker_ips and destination_ip in proxy_ips and destination_port == proxy_port
        reverse = source_ip in proxy_ips and destination_ip in worker_ips and source_port == proxy_port
        if (forward or reverse) and ("Flags" in line or "tcp" in line.lower()):
            allowed_tcp += 1
        else:
            unexpected.append(line[:240])
    if unexpected:
        raise RuntimeError("sink-side veth packet capture found non-proxy worker traffic: " + unexpected[0])
    if allowed_tcp == 0:
        raise RuntimeError("sink-side packet capture did not observe the approved proxy TCP flow")
    return {
        "allowed_proxy_tcp_packets": allowed_tcp,
        "arp_packets": arp_packets,
        "ipv6_neighbor_discovery_packets": ndp_packets,
        "unexpected_packets": 0,
        "capture_text_sha256": hashlib.sha256(output.encode("utf-8")).hexdigest(),
    }


def _evidence_write(path_value: str, evidence: dict) -> None:
    if not path_value:
        return
    path = Path(path_value)
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("evidence path must be an absolute normalized path")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(evidence, indent=2, sort_keys=True), encoding="utf-8")
    os.chmod(temporary, 0o600)
    temporary.replace(path)


def main() -> int:
    if os.environ.get("APAA_P74_REAL_HOST") != "1":
        print("BLOCKED: set APAA_P74_REAL_HOST=1 only on an owner-approved disposable Linux host")
        return 2

    worker_id = os.environ.get("APAA_P74_WORKER_ID", "worker-p74-01")
    if not re.fullmatch(r"[a-z][a-z0-9_-]{0,31}", worker_id):
        print("BLOCKED: worker ID must be a lowercase safe identifier")
        return 2

    namespace_name = os.environ.get("APAA_P74_NETNS_NAME", "apaa-w1")
    host_veth = os.environ.get("APAA_P74_HOST_VETH", "apahost0")
    worker_veth = os.environ.get("APAA_P74_WORKER_VETH", "apawork0")
    plan = NamespacePlan(
        name=namespace_name,
        host_veth=host_veth,
        worker_veth=worker_veth,
        host_ipv4=os.environ.get("APAA_P74_HOST_IPV4", "198.18.0.1/30"),
        worker_ipv4=os.environ.get("APAA_P74_WORKER_IPV4", "198.18.0.2/30"),
        host_ipv6=os.environ.get("APAA_P74_HOST_IPV6", "2001:db8:1::1/64"),
        worker_ipv6=os.environ.get("APAA_P74_WORKER_IPV6", "2001:db8:1::2/64"),
    )

    container_id = None
    cgroup_path = None
    namespace_created = False
    proxy_servers: list[PinnedConnectProxy] = []
    capture_process = None
    capture_temp = None
    cleanup_errors: list[str] = []
    evidence: dict = {
        "result": "BLOCKED",
        "worker_id": worker_id,
        "namespace": namespace_name,
        "host_veth": host_veth,
        "worker_veth": worker_veth,
        "tests": {},
    }
    runtime = PodmanOCIRuntime(timeout_seconds=30)
    namespace = LinuxNetworkNamespaceProvisioner()
    firewall = NftablesFirewallProvisioner()
    cgroups = CgroupV2Provisioner("/sys/fs/cgroup/apaa")

    try:
        image = _required("APAA_P74_IMAGE_DIGEST")
        seccomp_profile = _required("APAA_P74_SECCOMP_PROFILE")
        target = canonicalize_https_url(_required("APAA_P74_TEST_URL"))
        allowed_origin = _required("APAA_P74_ALLOWED_ORIGIN")
        expected_marker = _required("APAA_P74_EXPECTED_MARKER")
        if not 1 <= len(expected_marker) <= 256:
            raise RuntimeError("expected page marker must contain 1 to 256 characters")
        chromium_bin = os.environ.get("APAA_P74_CHROMIUM_BIN", "chromium")
        proxy_port = int(os.environ.get("APAA_P74_PROXY_PORT", "3128"))
        if target.origin != allowed_origin or target.port != 443:
            raise RuntimeError("test URL must be the exact approved HTTPS origin on port 443")
        if not chromium_bin or "/" in chromium_bin or "\x00" in chromium_bin:
            raise RuntimeError("Chromium executable must be a command name")
        if not 1024 <= proxy_port <= 65535:
            raise RuntimeError("proxy port is outside the permitted range")
        validate_seccomp_profile(seccomp_profile)
        if not image.startswith("sha256:") and "@sha256:" not in image:
            raise RuntimeError("Chromium image must be addressed by an immutable sha256 digest")

        host4 = str(ipaddress.ip_interface(plan.host_ipv4).ip)
        host6 = str(ipaddress.ip_interface(plan.host_ipv6).ip)
        proxy_ips = [host4, host6]
        namespace_path = f"/run/netns/{namespace_name}"
        evidence.update({
            "image_digest": image,
            "target_origin": target.origin,
            "proxy_ips": proxy_ips,
            "proxy_port": proxy_port,
            "seccomp_profile": seccomp_profile,
        })

        namespace.provision(plan)
        namespace_created = True
        evidence["tests"]["namespace_provisioned"] = True

        links = json.loads(_run(["ip", "netns", "exec", namespace_name, "ip", "-j", "link", "show"]).stdout)
        if {item.get("ifname") for item in links} != {"lo", worker_veth}:
            raise RuntimeError("worker namespace contains an unexpected network interface")
        route4 = json.loads(_run(["ip", "netns", "exec", namespace_name, "ip", "-j", "route", "show", "default"]).stdout)
        route6 = json.loads(_run(["ip", "netns", "exec", namespace_name, "ip", "-6", "-j", "route", "show", "default"]).stdout)
        if (len(route4) != 1 or route4[0].get("gateway") != host4 or route4[0].get("dev") != worker_veth
                or len(route6) != 1 or route6[0].get("gateway") != host6 or route6[0].get("dev") != worker_veth):
            raise RuntimeError("IPv4/IPv6 default routes do not lead exclusively to the approved proxy host")
        addresses = json.loads(_run(["ip", "netns", "exec", namespace_name, "ip", "-j", "addr", "show", "dev", worker_veth]).stdout)
        addr_values = {
            item.get("local")
            for device in addresses for item in device.get("addr_info", [])
        }
        if not {str(ipaddress.ip_interface(plan.worker_ipv4).ip), str(ipaddress.ip_interface(plan.worker_ipv6).ip)}.issubset(addr_values):
            raise RuntimeError("worker veth does not hold the configured IPv4 and IPv6 addresses")
        evidence["network_snapshot"] = {
            "interfaces": sorted(item.get("ifname", "") for item in links),
            "ipv4_default_route": route4,
            "ipv6_default_route": route6,
            "worker_addresses": sorted(addr_values),
        }
        evidence["tests"]["dual_stack_namespace_routes_and_no_alternate_interface"] = True

        firewall.install(namespace_name, proxy_ips, proxy_port)
        ruleset = firewall.verify_ruleset(
            namespace_name, proxy_ips=proxy_ips, proxy_port=proxy_port
        )
        evidence["nftables_ruleset"] = ruleset
        live_json_ruleset = _run([
            "ip", "netns", "exec", namespace_name, "nft", "-j", "list", "table", "inet", "apaa"
        ]).stdout
        # Retain the exact, bounded firewall JSON in the private qualification
        # artifact so a failed semantic attestation can be debugged without
        # guessing from the human-readable nft output.
        if len(live_json_ruleset) > 1_000_000:
            raise RuntimeError("nftables JSON evidence exceeds the bounded artifact size")
        evidence["nftables_json_snapshot"] = json.loads(live_json_ruleset)
        nft_attestation = attest_nftables_json(
            live_json_ruleset, NftablesPolicy(tuple(proxy_ips), proxy_port)
        )
        evidence["nftables_attestation"] = {
            "ruleset_sha256": nft_attestation.ruleset_sha256,
            "accept_rule_count": nft_attestation.accept_rule_count,
            "chains": list(nft_attestation.chains),
        }
        evidence["tests"]["nftables_exact_default_drop"] = True
        evidence["tests"]["nftables_json_semantic_attestation"] = True

        for bind_ip in proxy_ips:
            proxy = PinnedConnectProxy(
                bind_ip, proxy_port, allowed_hosts=[target.hostname], allowed_port=443
            )
            proxy.start()
            proxy_servers.append(proxy)
        evidence["tests"]["pinned_proxy_ipv4_ipv6_listeners"] = True

        capture_temp = tempfile.TemporaryDirectory(prefix="apaa-p74-pcap-")
        capture_path = Path(capture_temp.name) / "worker-veth.pcap"
        capture_process = subprocess.Popen(
            ["tcpdump", "-nn", "-i", host_veth, "-U", "-w", str(capture_path)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        time.sleep(0.25)
        if capture_process.poll() is not None:
            raise RuntimeError("sink-side tcpdump capture could not start")

        cgroup_path = cgroups.create(worker_id, CgroupLimits())
        evidence["cgroup_parent"] = str(cgroup_path)
        spec = OCIWorkerSpec(
            image=image,
            network_namespace=namespace_path,
            seccomp_profile=seccomp_profile,
            worker_id=worker_id,
            limits=WorkerLimits(),
            cgroup_parent=str(cgroup_path),
        )
        container_id = runtime.create(spec)
        evidence["container_id"] = container_id
        inspected = runtime.inspect(container_id)
        host = inspected.get("HostConfig") or {}
        config = inspected.get("Config") or {}
        state = inspected.get("State") or {}
        security = host.get("SecurityOpt") or []
        cap_drop = host.get("CapDrop") or []
        # Keep only the small, non-secret fields needed to diagnose a failed
        # runtime-policy assertion in the sanitized evidence artifact.
        evidence["oci_inspect_security"] = {
            "readonly_rootfs": host.get("ReadonlyRootfs"),
            "cap_drop": cap_drop,
            "security_options": security,
            "memory": host.get("Memory"),
            "pids_limit": host.get("PidsLimit"),
            "nano_cpus": host.get("NanoCpus"),
            "user": config.get("User"),
            "cgroup_parent": host.get("CgroupParent"),
            "network_mode": host.get("NetworkMode"),
            "state_status": state.get("Status"),
        }
        expected_cpu_nanos = int(spec.limits.cpu_count * 1_000_000_000)
        if not host.get("ReadonlyRootfs") or "ALL" not in cap_drop:
            raise RuntimeError("OCI inspect did not confirm read-only rootfs and all capabilities dropped")
        if not any(item.startswith("no-new-privileges") for item in security):
            raise RuntimeError("OCI inspect did not confirm no-new-privileges")
        if not any(item == f"seccomp={seccomp_profile}" for item in security):
            raise RuntimeError("OCI inspect did not confirm the requested seccomp profile")
        if (host.get("Memory") != spec.limits.memory_bytes
                or host.get("PidsLimit") != spec.limits.pids_limit
                or host.get("NanoCpus") != expected_cpu_nanos):
            raise RuntimeError("OCI inspect did not confirm CPU, memory and PID limits")
        if config.get("User") != "65532:65532":
            raise RuntimeError("OCI inspect did not confirm the unprivileged worker UID/GID")
        if host.get("CgroupParent") != str(cgroup_path):
            raise RuntimeError("OCI inspect did not confirm the dedicated cgroup parent")
        if host.get("NetworkMode") != f"ns:{namespace_path}":
            raise RuntimeError("OCI inspect did not confirm the exact isolated network namespace")
        if state.get("Status") not in ("created", "configured"):
            raise RuntimeError("OCI worker did not remain in the created pre-start state")
        evidence["oci_inspect"] = {
            "readonly_rootfs": host.get("ReadonlyRootfs"),
            "cap_drop": cap_drop,
            "security_opt": security,
            "memory_bytes": host.get("Memory"),
            "nano_cpus": host.get("NanoCpus"),
            "pids_limit": host.get("PidsLimit"),
            "network_mode": host.get("NetworkMode"),
            "user": config.get("User"),
        }
        evidence["tests"]["oci_inspect_hardening"] = True

        runtime.start(container_id)
        observation = PodmanWorkerObserver(runtime).observe(container_id, spec)
        evidence["runtime_observation"] = {
            "host_pid": observation.host_pid,
            "process_start_time_ticks": observation.process_start_time_ticks,
            "network_namespace_inode": observation.network_namespace_inode,
            "cgroup_path": observation.cgroup_path,
            "memory_max": observation.memory_max,
            "cpu_max": observation.cpu_max,
            "pids_max": observation.pids_max,
            "seccomp_mode": observation.seccomp_mode,
            "image_id": observation.image_id,
        }
        evidence["tests"]["independent_runtime_kernel_observation"] = True
        inspected = runtime.inspect(container_id)
        state = inspected.get("State") or {}
        host_pid = state.get("Pid")
        if type(host_pid) is not int or host_pid <= 1:
            raise RuntimeError("OCI runtime did not expose a valid host PID for namespace attestation")
        if os.stat(f"/proc/{host_pid}/ns/net").st_ino != os.stat(namespace_path).st_ino:
            raise RuntimeError("container init process is not in the provisioned network namespace")
        process_cgroup = Path(f"/proc/{host_pid}/cgroup").read_text(encoding="ascii")
        if f"/{worker_id}/" not in process_cgroup:
            raise RuntimeError("container init process is not inside its dedicated APAA cgroup")
        evidence["tests"]["network_namespace_inode_match"] = True
        evidence["tests"]["host_pid_cgroup_membership"] = True

        def container_read(path: str) -> str:
            return _run(["podman", "exec", container_id, "cat", path]).stdout.strip()

        memory = container_read("/sys/fs/cgroup/memory.max")
        cpu = container_read("/sys/fs/cgroup/cpu.max")
        pids = container_read("/sys/fs/cgroup/pids.max")
        status = _run(["podman", "exec", container_id, "cat", "/proc/self/status"]).stdout
        if (memory != str(spec.limits.memory_bytes)
                or cpu != "100000 100000"
                or pids != str(spec.limits.pids_limit)):
            raise RuntimeError("kernel cgroup-v2 read-back does not match requested worker limits")
        seccomp_lines = [line for line in status.splitlines() if line.startswith("Seccomp:")]
        if seccomp_lines != ["Seccomp:\t2"]:
            raise RuntimeError("kernel does not report an active seccomp filter")
        evidence["cgroup_readback"] = {"memory.max": memory, "cpu.max": cpu, "pids.max": pids}
        evidence["tests"]["kernel_cgroup_v2_readback"] = True
        evidence["tests"]["kernel_seccomp_active"] = True

        # Direct DNS and direct IPv4/IPv6 TCP must fail from inside the worker.
        _probe_blocked([
            "podman", "exec", container_id, "python3", "-c",
            "import socket; q=bytes.fromhex('123401000001000000000000076578616d706c6503636f6d0000010001'); s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); s.settimeout(2); s.sendto(q,('1.1.1.1',53)); s.recvfrom(4096)",
        ], "direct UDP DNS query")
        _probe_blocked([
            "podman", "exec", container_id, "python3", "-c",
            "import socket; socket.create_connection(('1.1.1.1',53),2)",
        ], "direct TCP DNS query")
        _probe_blocked([
            "podman", "exec", container_id, "python3", "-c",
            "import socket; socket.create_connection(('1.1.1.1',443),2)",
        ], "direct IPv4 TCP")
        _probe_blocked([
            "podman", "exec", container_id, "python3", "-c",
            "import socket; s=socket.socket(socket.AF_INET6); s.settimeout(2); s.connect(('2606:4700:4700::1111',443))",
        ], "direct IPv6 TCP")
        _probe_blocked([
            "podman", "exec", container_id, "python3", "-c",
            "import socket; s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); s.settimeout(2); s.sendto(b'APAA-UDP-PROBE',('1.1.1.1',443)); s.recvfrom(1)",
        ], "direct UDP/443 QUIC-style egress")
        evidence["tests"]["direct_dns_blocked"] = True
        evidence["tests"]["direct_tcp_dns_blocked"] = True
        evidence["tests"]["direct_ipv4_blocked"] = True
        evidence["tests"]["direct_ipv6_blocked"] = True
        evidence["tests"]["direct_udp_443_blocked"] = True

        for family, proxy_ip in (("ipv4", host4), ("ipv6", host6)):
            proxy_host = f"[{proxy_ip}]" if ":" in proxy_ip else proxy_ip
            proxy_argument = f"http={proxy_host}:{proxy_port};https={proxy_host}:{proxy_port}"
            page = _run([
                "podman", "exec", "--user", "65532:65532", container_id,
                chromium_bin,
                "--headless=new",
                "--disable-gpu",
                "--disable-quic",
                "--disable-background-networking",
                "--disable-component-update",
                "--disable-sync",
                "--no-first-run",
                "--proxy-server=" + proxy_argument,
                "--proxy-bypass-list=<-loopback>",
                "--dump-dom",
                target.url,
            ], timeout=120)
            if "<html" not in page.stdout.lower() or expected_marker not in page.stdout:
                raise RuntimeError(f"Chromium did not return the expected controlled-page marker over the {family} proxy")
            evidence["tests"][f"chromium_https_via_{family}_proxy"] = True
            evidence[f"chromium_{family}_evidence"] = {
                "stdout_sha256": hashlib.sha256(page.stdout.encode("utf-8")).hexdigest(),
                "stdout_bytes": len(page.stdout.encode("utf-8")),
                "expected_marker_present": True,
            }

        if capture_process is None or capture_temp is None:
            raise RuntimeError("sink-side packet capture was not active during Chromium execution")
        capture_process.send_signal(signal.SIGINT)
        capture_returncode = capture_process.wait(timeout=10)
        capture_process = None
        if capture_returncode != 0:
            raise RuntimeError("sink-side tcpdump did not exit cleanly")
        packet_summary = _audit_worker_capture(
            capture_path,
            worker_ips={str(ipaddress.ip_interface(plan.worker_ipv4).ip), str(ipaddress.ip_interface(plan.worker_ipv6).ip)},
            proxy_ips=set(proxy_ips),
            proxy_port=proxy_port,
        )
        evidence["packet_capture"] = packet_summary
        evidence["tests"]["sink_side_packet_capture_proxy_only"] = True
        capture_temp.cleanup()
        capture_temp = None

        evidence["proxy_dialed_addresses"] = {
            "ipv4_listener": list(proxy_servers[0].dialed_addresses),
            "ipv6_listener": list(proxy_servers[1].dialed_addresses),
        }
        evidence["proxy_accepted_connections"] = {
            "ipv4_listener": proxy_servers[0].accepted_connections,
            "ipv6_listener": proxy_servers[1].accepted_connections,
        }
        if not all(evidence["proxy_accepted_connections"].values()):
            raise RuntimeError("one or both proxy families did not record an upstream pinned TCP connection")

        # Shut down each mandatory proxy and prove Chromium cannot reach the
        # allowed origin through a direct fallback. The namespace firewall
        # remains installed and default-DROP during both negative probes.
        for family, proxy_ip, proxy in (
            ("ipv4", host4, proxy_servers[0]),
            ("ipv6", host6, proxy_servers[1]),
        ):
            proxy.close()
            proxy_host = f"[{proxy_ip}]" if ":" in proxy_ip else proxy_ip
            proxy_argument = f"http={proxy_host}:{proxy_port};https={proxy_host}:{proxy_port}"
            outage = _probe_proxy_outage([
                "podman", "exec", "--user", "65532:65532", container_id,
                chromium_bin, "--headless=new", "--disable-gpu", "--disable-quic",
                "--disable-background-networking", "--disable-component-update",
                "--disable-sync", "--no-first-run", "--proxy-server=" + proxy_argument,
                "--proxy-bypass-list=<-loopback>", "--dump-dom", target.url,
            ], expected_marker, family)
            evidence["tests"][f"proxy_outage_no_direct_fallback_{family}"] = True
            evidence[f"proxy_outage_{family}_evidence"] = outage

        evidence["result"] = "PASS"
        print("PASS: Chromium ran inside the isolated OCI worker through both IPv4 and IPv6 pinned proxies.")
        print("PASS: direct DNS, direct IPv4 TCP and direct IPv6 TCP were blocked.")
    except Exception as exc:
        evidence["error"] = f"{type(exc).__name__}: {exc}"
        print(f"BLOCKED: {type(exc).__name__}: {exc}")
    finally:
        if capture_process is not None:
            try:
                capture_process.send_signal(signal.SIGINT)
                capture_process.wait(timeout=5)
            except Exception:
                try:
                    capture_process.kill()
                    capture_process.wait(timeout=2)
                except Exception:
                    cleanup_errors.append("packet-capture: stop-not-confirmed")
        if capture_temp is not None:
            try:
                capture_temp.cleanup()
            except Exception:
                cleanup_errors.append("packet-capture: temp-cleanup-failed")
        for proxy in reversed(proxy_servers):
            try:
                proxy.close()
            except Exception as exc:
                cleanup_errors.append(f"proxy: {type(exc).__name__}")
        if container_id:
            try:
                runtime.stop(container_id, timeout_seconds=5)
            except Exception:
                pass
            try:
                runtime.remove(container_id)
            except Exception as exc:
                cleanup_errors.append(f"container: {type(exc).__name__}")
        if cgroup_path is not None:
            try:
                cgroups.remove(cgroup_path)
            except Exception as exc:
                cleanup_errors.append(f"cgroup: {type(exc).__name__}")
        if namespace_created:
            try:
                namespace.remove(plan)
            except Exception as exc:
                cleanup_errors.append(f"namespace/veth: {type(exc).__name__}")
        evidence["cleanup_errors"] = cleanup_errors
        evidence["cleanup_confirmed"] = not cleanup_errors
        evidence["finished_at_unix"] = int(time.time())
        if cleanup_errors:
            evidence["result"] = "CLEANUP_REQUIRED"
            print("CLEANUP_REQUIRED: one or more worker resources could not be confirmed removed.", file=sys.stderr)
        try:
            _evidence_write(os.environ.get("APAA_P74_EVIDENCE_PATH", ""), evidence)
        except Exception as exc:
            cleanup_errors.append(f"evidence: {type(exc).__name__}")
            evidence["result"] = "CLEANUP_REQUIRED"
            evidence["cleanup_errors"] = cleanup_errors
            evidence["cleanup_confirmed"] = False

    return 0 if evidence["result"] == "PASS" and not cleanup_errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
