"""Validated private network contract for the APAA proxy/worker boundary.

Configuration validation only: this module never creates an OCI network,
binds a proxy socket, alters routes, or installs firewall rules.
"""
from __future__ import annotations
from dataclasses import dataclass
import ipaddress
import re
from urllib.parse import urlsplit

class ProxyWorkerTopologyError(ValueError):
    """Unsafe or ambiguous proxy/worker network configuration."""

_NAME = re.compile(r"^[a-z][a-z0-9_-]{2,47}$")

@dataclass(frozen=True)
class ProxyWorkerTopology:
    network_name: str
    subnet: str
    proxy_address: str
    worker_address: str
    proxy_port: int = 3128

    @classmethod
    def build(cls, *, network_name: str, subnet: str, proxy_address: str,
              worker_address: str, proxy_port: int = 3128) -> "ProxyWorkerTopology":
        if type(network_name) is not str or not _NAME.fullmatch(network_name):
            raise ProxyWorkerTopologyError("A dedicated explicit APAA network name is required.")
        try:
            network = ipaddress.ip_network(subnet, strict=True)
            proxy = ipaddress.ip_address(proxy_address)
            worker = ipaddress.ip_address(worker_address)
        except (TypeError, ValueError) as exc:
            raise ProxyWorkerTopologyError("Subnet and endpoint addresses must be canonical IP values.") from exc
        if network.version != 4 or not network.is_private or network.is_link_local:
            raise ProxyWorkerTopologyError("Worker network must be a private IPv4 subnet.")
        if proxy.version != 4 or worker.version != 4:
            raise ProxyWorkerTopologyError("Only IPv4 proxy/worker endpoints are supported.")
        if proxy not in network or worker not in network or proxy == worker:
            raise ProxyWorkerTopologyError("Proxy and worker need distinct addresses in the exact subnet.")
        if proxy in (network.network_address, network.broadcast_address) or worker in (
            network.network_address, network.broadcast_address
        ):
            raise ProxyWorkerTopologyError("Network and broadcast addresses cannot be endpoints.")
        if type(proxy_port) is not int or not 1024 <= proxy_port <= 65535:
            raise ProxyWorkerTopologyError("Proxy port must be an unprivileged TCP port.")
        return cls(network_name, str(network), proxy.compressed, worker.compressed, proxy_port)

    @property
    def worker_proxy_url(self) -> str:
        return f"http://{self.proxy_address}:{self.proxy_port}"

    @property
    def expected_proxy_addresses(self) -> tuple[str, ...]:
        return (self.proxy_address,)

    def validate_worker_proxy_url(self, value: object) -> None:
        if type(value) is not str:
            raise ProxyWorkerTopologyError("Worker proxy URL must be explicit text.")
        parsed = urlsplit(value)
        try:
            port = parsed.port
        except ValueError as exc:
            raise ProxyWorkerTopologyError("Worker proxy URL has an invalid port.") from exc
        if (parsed.scheme != "http" or parsed.hostname != self.proxy_address
                or port != self.proxy_port or parsed.username is not None
                or parsed.password is not None or parsed.path not in ("",)
                or parsed.query or parsed.fragment):
            raise ProxyWorkerTopologyError("Worker must target the exact private proxy IP and TCP port.")

    def deployment_invariants(self) -> tuple[str, ...]:
        return (
            "OCI network is dedicated to APAA browser workers and marked internal",
            "worker has exactly one non-loopback interface on the dedicated subnet",
            "proxy listens only on the proxy_address:proxy_port interface",
            "proxy port is not published on host or public interfaces",
            "worker default egress is host-enforced DROP; only TCP to proxy_address:proxy_port is allowed",
            "worker has no direct DNS resolver, internet gateway, IPv6 route, or alternate NIC",
            "proxy performs DNS resolution and pins validated upstream IPs per connection",
            "proxy management access is out-of-band and not reachable from the worker subnet",
        )
