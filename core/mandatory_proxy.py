"""Mandatory pinned-IP HTTPS proxy tunnel. No direct-origin fallback."""
from __future__ import annotations
import ipaddress, ssl
from dataclasses import dataclass
from typing import Any
from core.egress_policy import EgressAuthorizationError, EgressTarget
from core.pinned_ip_connector import PinnedIPConnector

class ProxyBoundaryError(RuntimeError):
    """Mandatory proxy boundary failure."""

@dataclass(frozen=True)
class ProxyEndpoint:
    target: EgressTarget
    def __post_init__(self):
        if not isinstance(self.target,EgressTarget) or self.target.scheme!="https" or not self.target.pinned_addresses:
            raise ValueError("A pinned HTTPS proxy endpoint is mandatory.")

@dataclass
class ProxiedConnection:
    stream: Any
    proxy_ip: str
    origin_ip: str
    origin_hostname: str
    origin_port: int
    def close(self): self.stream.close()
    def __enter__(self): return self
    def __exit__(self,*args): self.close()

class MandatoryProxyConnector:
    """TLS-to-proxy + numeric-IP CONNECT + TLS-to-origin with hostname checks."""
    def __init__(self,proxy:ProxyEndpoint,*,connector=None,proxy_tls_context=None,
                 origin_tls_context=None,timeout:float=8.0):
        if not isinstance(proxy,ProxyEndpoint): raise TypeError("proxy must be ProxyEndpoint.")
        if isinstance(timeout,bool) or not isinstance(timeout,(int,float)) or not 0<timeout<=60:
            raise ValueError("Invalid timeout.")
        self.proxy=proxy; self.connector=connector or PinnedIPConnector(timeout=timeout)
        self.proxy_tls=proxy_tls_context or ssl.create_default_context()
        self.origin_tls=origin_tls_context or ssl.create_default_context()
        self.timeout=float(timeout)
        for ctx in (self.proxy_tls,self.origin_tls):
            if ctx.verify_mode!=ssl.CERT_REQUIRED or not ctx.check_hostname:
                raise ValueError("TLS certificate and hostname verification are mandatory.")

    @staticmethod
    def _authority(ip,port):
        addr=ipaddress.ip_address(ip); host=f"[{addr.compressed}]" if addr.version==6 else addr.compressed
        return f"{host}:{port}"

    def connect(self,origin:EgressTarget)->ProxiedConnection:
        if not isinstance(origin,EgressTarget) or origin.scheme not in {"https","http"} or not origin.pinned_addresses:
            raise EgressAuthorizationError("Origin target is not authorized.")
        # EgressTarget is a public data object; re-check it at this trust boundary
        # so a forged target cannot turn the proxy into an SSRF relay.
        if not isinstance(origin.hostname,str) or not origin.hostname or len(origin.hostname)>253:
            raise EgressAuthorizationError("Origin hostname is malformed.")
        for candidate in origin.pinned_addresses:
            try:
                parsed=ipaddress.ip_address(candidate)
            except (TypeError,ValueError) as exc:
                raise EgressAuthorizationError("Origin pin is malformed.") from exc
            if not parsed.is_global or parsed.compressed != candidate:
                raise EgressAuthorizationError("Non-public or non-canonical origin pin denied.")
        raw=proxy_tls=origin_tls=None
        try:
            pinned=self.connector.connect(self.proxy.target); raw=pinned.socket
            proxy_tls=self.proxy_tls.wrap_socket(raw,server_hostname=self.proxy.target.hostname)
            proxy_tls.settimeout(self.timeout)
            ip=origin.pinned_addresses[0]; authority=self._authority(ip,origin.port)
            proxy_tls.sendall((f"CONNECT {authority} HTTP/1.1\r\nHost: {authority}\r\nProxy-Connection: Keep-Alive\r\n\r\n").encode("ascii"))
            response=bytearray()
            while b"\r\n\r\n" not in response:
                if len(response)>=16384: raise ProxyBoundaryError("CONNECT response too large.")
                part=proxy_tls.recv(min(1024,16384-len(response)))
                if not part: raise ProxyBoundaryError("Proxy closed during CONNECT.")
                response.extend(part)
            header,extra=bytes(response).split(b"\r\n\r\n",1)
            if extra or not header.startswith(b"HTTP/1.") or header.split(b" ",2)[1:2]!=[b"200"]:
                raise ProxyBoundaryError("Proxy CONNECT was rejected or malformed.")
            stream=proxy_tls
            if origin.scheme=="https":
                origin_tls=self.origin_tls.wrap_socket(proxy_tls,server_hostname=origin.hostname)
                origin_tls.settimeout(self.timeout); stream=origin_tls
            return ProxiedConnection(stream,pinned.pinned_ip,ip,origin.hostname,origin.port)
        except Exception as exc:
            for item in (origin_tls,proxy_tls,raw):
                if item is not None:
                    try: item.close()
                    except Exception: pass
            if isinstance(exc,ProxyBoundaryError): raise
            raise ProxyBoundaryError("Mandatory proxy failed closed; direct fallback is forbidden.") from exc
