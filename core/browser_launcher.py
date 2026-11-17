"""Playwright Chromium launcher behind the signed inspector runtime gate.

This module never accepts caller-authored runtime-attestation dictionaries.
The only supported public launch path is an AttestedBrowserRuntime instance
whose worker_start callback is created by create_playwright_worker_start().
"""
from __future__ import annotations

from dataclasses import dataclass
import ipaddress
from typing import Any
from urllib.parse import urlsplit

from core.attested_browser_runtime import AttestedBrowserRuntime, BrowserRuntimeGateError
from core.browser_inspector import VerifiedInspectorEvidence


class BrowserLaunchError(RuntimeError):
    """Raised when Chromium cannot be launched under the approved contract."""


@dataclass
class BrowserSession:
    """Owned browser/context pair with idempotent, best-effort cleanup."""
    browser: Any
    context: Any
    closed: bool = False

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        first_error = None
        for resource in (self.context, self.browser):
            try:
                resource.close()
            except Exception as exc:
                if first_error is None:
                    first_error = exc
        if first_error is not None:
            raise BrowserLaunchError("Browser session cleanup was incomplete.") from first_error


def create_playwright_worker_start(browser_type: Any):
    """Create the privileged worker_start callback for AttestedBrowserRuntime.

    The callback is invoked only after Ed25519 signature, challenge, runtime
    attestation and host-firewall evidence have been verified by the gate.
    It pins Chromium's proxy endpoint to an IP explicitly allowed by the signed
    firewall evidence; it does not use proxy-host DNS or any direct fallback.
    """
    if not callable(getattr(browser_type, "launch", None)):
        raise TypeError("browser_type must expose a callable launch method.")

    def worker_start(spec, evidence: VerifiedInspectorEvidence) -> BrowserSession:
        if type(evidence) is not VerifiedInspectorEvidence:
            raise BrowserLaunchError("Only signed, verified inspector evidence is accepted.")
        if evidence.runtime.launch_spec_digest != spec.digest:
            raise BrowserLaunchError("Verified evidence does not match the worker launch specification.")
        if evidence.runtime.worker_state != "created":
            raise BrowserLaunchError("Worker must be attested before browser startup.")
        firewall = evidence.firewall
        if firewall.default_egress_policy != "drop":
            raise BrowserLaunchError("Firewall default egress policy must be DROP.")
        if firewall.runtime_id != evidence.runtime.runtime_id or firewall.worker_id != evidence.runtime.worker_id:
            raise BrowserLaunchError("Firewall evidence is not bound to the attested worker.")
        parsed = urlsplit(spec.egress_proxy)
        if parsed.scheme != "http" or not parsed.hostname or parsed.port != firewall.proxy_port:
            raise BrowserLaunchError("Proxy endpoint does not match signed firewall evidence.")
        if not firewall.allowed_proxy_addresses:
            raise BrowserLaunchError("Signed firewall evidence contains no proxy IP pin.")

        # Use a numeric proxy address from the signed firewall allowlist. This
        # prevents proxy hostname DNS from creating an unpinned connection.
        proxy_ip = firewall.allowed_proxy_addresses[0]
        try:
            address = ipaddress.ip_address(proxy_ip)
        except ValueError as exc:
            raise BrowserLaunchError("Signed proxy IP pin is malformed.") from exc
        proxy_host = f"[{address.compressed}]" if address.version == 6 else address.compressed
        proxy_server = f"http://{proxy_host}:{firewall.proxy_port}"

        browser = None
        try:
            browser = browser_type.launch(
                headless=True,
                chromium_sandbox=True,
                proxy={"server": proxy_server},
                args=[
                    "--disable-background-networking",
                    "--disable-component-update",
                    "--disable-sync",
                    "--disable-http2",
                    "--disable-quic",
                    "--proxy-bypass-list=<-loopback>",
                ],
            )
            context = browser.new_context(
                ignore_https_errors=False,
                accept_downloads=False,
                service_workers="block",
            )
            return BrowserSession(browser=browser, context=context)
        except Exception as exc:
            if browser is not None:
                try:
                    browser.close()
                except Exception:
                    pass
            raise BrowserLaunchError(
                "Chromium launch failed closed; no alternate or direct network path was attempted."
            ) from exc

    return worker_start


def launch_chromium(
    runtime_gate: AttestedBrowserRuntime,
    signed_evidence: object,
    *,
    challenge: str,
    now: int,
) -> BrowserSession:
    """Launch Chromium only through the concrete signed-evidence runtime gate."""
    if type(runtime_gate) is not AttestedBrowserRuntime:
        raise TypeError("A concrete AttestedBrowserRuntime gate is required.")
    try:
        session = runtime_gate.launch(signed_evidence, challenge=challenge, now=now)
    except BrowserRuntimeGateError as exc:
        # Distinguish a rejected signature/firewall gate from a failure after
        # the verified gate invoked the trusted browser worker callback.
        if isinstance(exc.__cause__, BrowserLaunchError):
            raise BrowserLaunchError(str(exc.__cause__)) from exc
        cause = exc.__cause__
        detail = cause.__cause__ if cause is not None and cause.__cause__ is not None else exc
        raise BrowserLaunchError(
            f"Signed runtime/firewall verification failed; browser was not started ({detail})."
        ) from exc
    if type(session) is not BrowserSession:
        raise BrowserLaunchError("Verified worker adapter did not return a BrowserSession.")
    return session
