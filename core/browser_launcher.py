"""Fail-closed legacy host Playwright launcher.

The signed inspector gate is not permission to start Chromium on the host:
the verified network namespace and firewall belong to the OCI worker, not the
host process. Until a production IsolatedWorkerBackend launches Chromium inside
that attested worker, this legacy launcher deliberately refuses to start it.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

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
    """Return a legacy callback that refuses unsafe host-local Chromium launch.

    This compatibility entry point is intentionally inert. A signed runtime
    attestation proves the OCI worker state; it does not move a host Playwright
    process into that worker's network namespace. Production browsing must use
    a separately reviewed IsolatedWorkerBackend and its worker-side RPC.
    """
    if not callable(getattr(browser_type, "launch", None)):
        raise TypeError("browser_type must expose a callable launch method.")

    def worker_start(spec, evidence: VerifiedInspectorEvidence) -> BrowserSession:
        raise BrowserLaunchError(
            "Host-local Playwright launch is forbidden. A production isolated "
            "OCI worker backend is required; no direct or host fallback is allowed."
        )

    return worker_start

def launch_chromium(
    runtime_gate: AttestedBrowserRuntime,
    signed_evidence: object,
    *,
    challenge: str,
    now: int,
) -> BrowserSession:
    """Legacy host-launch wrapper; fails until a worker-backed session adapter exists."""
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
