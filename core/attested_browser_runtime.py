"""Fail-closed gate between signed isolation evidence and a worker adapter.

This module does not create a container, apply firewall rules, or launch a
browser itself. A separately reviewed worker adapter receives the immutable
launch contract only after independently signed, fresh runtime + firewall
evidence has passed verification.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Callable

from core.browser_inspector import (
    InspectorEvidenceError,
    VerifiedInspectorEvidence,
    verify_signed_inspector_evidence,
)
from core.browser_runtime import WorkerLaunchSpec


class BrowserRuntimeGateError(RuntimeError):
    """Raised when isolated browser worker launch is not authorized."""


WorkerStart = Callable[[WorkerLaunchSpec, VerifiedInspectorEvidence], object]


class AttestedBrowserRuntime:
    """Verify the pre-start boundary before delegating to a trusted worker adapter.

    The callback is a privileged integration point and MUST be implemented by
    a separately reviewed host/container adapter. It must launch the worker
    with exactly the supplied spec, configure the specified proxy, enforce
    proxy-only egress outside the browser process, and return a worker handle.
    This class deliberately has no default adapter and performs no side effects
    until launch is explicitly called.
    """

    def __init__(
        self,
        spec: WorkerLaunchSpec,
        *,
        trusted_public_keys: Mapping[str, bytes],
        expected_proxy_addresses: Sequence[str],
        worker_start: WorkerStart | None = None,
    ) -> None:
        if type(spec) is not WorkerLaunchSpec:
            raise TypeError("A validated WorkerLaunchSpec is required.")
        if not isinstance(trusted_public_keys, Mapping):
            raise TypeError("trusted_public_keys must be a mapping.")
        if worker_start is not None and not callable(worker_start):
            raise TypeError("worker_start must be callable.")
        self._spec = spec
        self._trusted_public_keys = dict(trusted_public_keys)
        self._proxy_addresses = tuple(expected_proxy_addresses)
        self._worker_start = worker_start

    def launch(
        self,
        signed_evidence: object,
        *,
        challenge: str,
        now: int,
        max_age_seconds: int = 60,
    ) -> object:
        """Verify evidence, then invoke the explicit worker adapter exactly once."""
        if self._worker_start is None:
            raise BrowserRuntimeGateError(
                "No trusted host/container worker adapter is configured; launch is blocked."
            )
        try:
            verified = verify_signed_inspector_evidence(
                self._spec,
                signed_evidence,
                trusted_public_keys=self._trusted_public_keys,
                expected_challenge=challenge,
                expected_proxy_addresses=self._proxy_addresses,
                now=now,
                max_age_seconds=max_age_seconds,
            )
        except (InspectorEvidenceError, TypeError, ValueError) as exc:
            raise BrowserRuntimeGateError(
                "Signed runtime/network-isolation evidence was rejected; worker launch is blocked."
            ) from exc

        try:
            return self._worker_start(self._spec, verified)
        except Exception as exc:
            raise BrowserRuntimeGateError(
                "Trusted worker adapter failed; no alternate or direct launch is permitted."
            ) from exc
