"""Opt-in real-host Chromium worker qualification; never runs in ordinary CI.

Set APAA_P74_REAL_HOST=1 only on an owner-approved disposable Linux host.
This test is a qualification probe, not a public browsing feature.
"""
from __future__ import annotations

import ipaddress
import os
import subprocess
import sys
from urllib.parse import urlsplit

from core.browser_security import canonicalize_https_url
from core.nftables_firewall_provisioner import NftablesFirewallProvisioner
from core.oci_runtime_backend import OCIWorkerSpec, PodmanOCIRuntime, WorkerLimits


def _required(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise RuntimeError(f"required environment variable is missing: {name}")
    return value


def _run(command: list[str], timeout: int = 90) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command, check=False, capture_output=True, text=True,
        timeout=timeout, shell=False,
    )
    if result.returncode:
        raise RuntimeError("real worker qualification command failed")
    return result


def main() -> int:
    if os.environ.get("APAA_P74_REAL_HOST") != "1":
        print("BLOCKED: set APAA_P74_REAL_HOST=1 only on an approved disposable Linux host")
        return 2

    container_id = None
    runtime = PodmanOCIRuntime(timeout_seconds=30)
    try:
        image = _required("APAA_P74_IMAGE_DIGEST")
        namespace_path = _required("APAA_P74_NETNS_PATH")
        seccomp_profile = _required("APAA_P74_SECCOMP_PROFILE")
        worker_id = _required("APAA_P74_WORKER_ID")
        proxy_ip = ipaddress.ip_address(_required("APAA_P74_PROXY_IP"))
        proxy_port = int(_required("APAA_P74_PROXY_PORT"))
        target = canonicalize_https_url(_required("APAA_P74_TEST_URL"))
        allowed_origin = _required("APAA_P74_ALLOWED_ORIGIN")
        chromium_bin = os.environ.get("APAA_P74_CHROMIUM_BIN", "chromium")

        if target.origin != allowed_origin:
            raise RuntimeError("test URL does not match the exact approved origin")
        if not 1 <= proxy_port <= 65535:
            raise RuntimeError("proxy port is invalid")
        if not chromium_bin or "/" in chromium_bin or "\x00" in chromium_bin:
            raise RuntimeError("Chromium executable must be a command name")
        if not namespace_path.startswith("/run/netns/"):
            raise RuntimeError("network namespace path is outside /run/netns")

        namespace = namespace_path.rsplit("/", 1)[-1]
        rules = NftablesFirewallProvisioner().verify_ruleset(namespace)
        family_token = f"{'ip' if proxy_ip.version == 4 else 'ip6'} daddr {proxy_ip.compressed}"
        if "policy drop" not in rules or family_token not in rules or f"tcp dport {proxy_port}" not in rules:
            raise RuntimeError("installed firewall does not match the approved proxy endpoint")

        spec = OCIWorkerSpec(
            image=image,
            network_namespace=namespace_path,
            seccomp_profile=seccomp_profile,
            worker_id=worker_id,
            limits=WorkerLimits(),
        )
        container_id = runtime.create(spec)
        inspected = runtime.inspect(container_id)
        host = inspected.get("HostConfig") or {}
        config = inspected.get("Config") or {}
        security = host.get("SecurityOpt") or []
        cap_drop = host.get("CapDrop") or []
        if not host.get("ReadonlyRootfs") or "ALL" not in cap_drop:
            raise RuntimeError("OCI inspect did not confirm read-only rootfs and all capabilities dropped")
        if not any(item.startswith("no-new-privileges") for item in security):
            raise RuntimeError("OCI inspect did not confirm no-new-privileges")
        if not any(item == f"seccomp={seccomp_profile}" for item in security):
            raise RuntimeError("OCI inspect did not confirm the requested seccomp profile")
        if host.get("Memory") != spec.limits.memory_bytes or host.get("PidsLimit") != spec.limits.pids_limit:
            raise RuntimeError("OCI inspect did not confirm memory and PID limits")
        if config.get("User") != "65532:65532" or not str(host.get("NetworkMode", "")).startswith("ns:"):
            raise RuntimeError("OCI inspect did not confirm non-root user and isolated network namespace")

        runtime.start(container_id)
        proxy_host = f"[{proxy_ip.compressed}]" if proxy_ip.version == 6 else proxy_ip.compressed
        proxy_url = f"http://{proxy_host}:{proxy_port}"
        _run([
            "podman", "exec", "--user", "65532:65532", container_id,
            chromium_bin,
            "--headless=new",
            "--disable-gpu",
            "--disable-quic",
            "--disable-background-networking",
            "--disable-component-update",
            "--disable-sync",
            "--no-first-run",
            "--proxy-server=" + proxy_url,
            "--proxy-bypass-list=<-loopback>",
            "--dump-dom",
            target.url,
        ], timeout=120)
        print("PASS: Chromium ran inside the isolated container through the configured proxy.")
        print("NOTE: sink-side packet capture, TLS negative tests, DNS rebinding and full bypass matrix still require independent host evidence.")
        return 0
    except Exception as exc:
        print(f"BLOCKED: {type(exc).__name__}: {exc}")
        return 1
    finally:
        if container_id:
            try:
                runtime.stop(container_id, timeout_seconds=5)
            except Exception:
                pass
            try:
                runtime.remove(container_id)
            except Exception:
                print("CLEANUP_REQUIRED: OCI container removal failed", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
