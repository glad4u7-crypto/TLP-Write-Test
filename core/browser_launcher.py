"""Fail-closed Playwright Chromium launcher adapter.

Runs inside an already-created, independently attested isolated worker.
It does not create the worker, namespaces, firewall, or egress proxy.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any

from core.browser_runtime import RuntimeAttestationError, RuntimeSecurityAttestation, WorkerLaunchSpec, verify_prestart_attestation


class BrowserLaunchError(RuntimeError):
    """Raised when a browser cannot be launched under the approved contract."""


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


def launch_chromium(browser_type: Any, spec: WorkerLaunchSpec, raw_attestation: object, *, now: int | None = None) -> BrowserSession:
    """Verify fresh isolation evidence, then launch Chromium through one proxy.

    browser_type is normally Playwright's chromium BrowserType. Evidence must
    come from a trusted host/runtime inspector, not caller-authored booleans.
    No arbitrary launch args, executable path, persistent profile, certificate
    bypass, or direct-network fallback is exposed.
    """
    try:
        attestation: RuntimeSecurityAttestation = verify_prestart_attestation(spec, raw_attestation, now=now)
    except (RuntimeAttestationError, TypeError, ValueError) as exc:
        raise BrowserLaunchError("Worker isolation attestation rejected; browser was not started.") from exc

    if attestation.worker_state != "created" or attestation.launch_spec_digest != spec.digest:
        raise BrowserLaunchError("Worker state or launch specification is not approved.")
    if attestation.proxy_endpoint != spec.egress_proxy:
        raise BrowserLaunchError("Attested proxy endpoint does not match the approved endpoint.")
    if not callable(getattr(browser_type, "launch", None)):
        raise TypeError("browser_type must expose a callable launch method.")

    browser = None
    try:
        browser = browser_type.launch(
            headless=True,
            chromium_sandbox=True,
            proxy={"server": attestation.proxy_endpoint},
            args=[
                "--disable-background-networking",
                "--disable-component-update",
                "--disable-sync",
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
        raise BrowserLaunchError("Chromium launch failed closed; no alternate network path was attempted.") from exc
