"""Restricted HTTP CONNECT proxy with DNS-answer validation and numeric-IP dialing."""
from __future__ import annotations

import ipaddress
import select
import socket
import socketserver
import threading
from core.browser_security import canonicalize_https_url
from core.pinned_egress import PinnedEgressError, connect_pinned, resolve_and_pin


class ProxyPolicyError(RuntimeError):
    pass


def _canonical_host(value: str) -> str:
    if type(value) is not str or not value or value.endswith(".") or "%" in value:
        raise ProxyPolicyError("invalid CONNECT hostname")
    try:
        ipaddress.ip_address(value)
    except ValueError:
        pass
    else:
        raise ProxyPolicyError("IP literals are not accepted as CONNECT hostnames")
    try:
        return canonicalize_https_url("https://" + value + "/").hostname
    except ValueError:
        raise ProxyPolicyError("invalid CONNECT hostname") from None
