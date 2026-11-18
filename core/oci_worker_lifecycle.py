"""Two-phase OCI worker lifecycle orchestration with injected, inert-by-default ports.

This module never invokes subprocess or chooses a command runner. A caller must
explicitly inject a runner and a trusted evidence provider. Tests use fakes.
The runner contract is argv-only; no shell command strings are accepted.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Protocol, Sequence

from core.attested_browser_runtime import AttestedBrowserRuntime, BrowserRuntimeGateError
from core.browser_inspector import VerifiedInspectorEvidence
from core.browser_runtime import WorkerLaunchSpec
from core.oci_worker_plan import OCIWorkerPlan


class WorkerLifecycleError(RuntimeError):
    """Raised when an OCI worker lifecycle transition fails closed."""


class WorkerState(str, Enum):
    NEW = "new"
    CREATED = "created"
    INSPECTED = "inspected"
    ATTESTED = "attested"
    RUNNING = "running"
    STOPPED = "stopped"
    REMOVED = "removed"
    FAILED = "failed"


@dataclass(frozen=True)
class CommandResult:
    """Minimal normalized result returned by an injected command runner."""

    returncode: int
    stdout: str = ""


class CommandRunner(Protocol):
    def __call__(self, argv: Sequence[str], *, timeout_seconds: int) -> CommandResult: ...


EvidenceProvider = Callable[[OCIWorkerPlan, CommandResult], object]


class OCIWorkerLifecycle:
    """Orchestrate CREATE → INSPECT → ATTEST → START → CLEANUP.

    The command runner is an explicit privileged port and is never created by
    this class. The evidence provider must independently obtain a fresh signed
    inspector envelope for the stopped container. No start command is issued
    unless AttestedBrowserRuntime verifies that envelope successfully.
    """

    def __init__(
        self,
        plan: OCIWorkerPlan,
        spec: WorkerLaunchSpec,
        *,
        command_runner: CommandRunner,
        evidence_provider: EvidenceProvider,
        trusted_public_keys: dict[str, bytes],
        expected_proxy_addresses: Sequence[str],
    ) -> None:
        if not isinstance(plan, OCIWorkerPlan) or type(spec) is not WorkerLaunchSpec:
            raise TypeError("A validated OCIWorkerPlan and WorkerLaunchSpec are required.")
        if not callable(command_runner) or not callable(evidence_provider):
            raise TypeError("Explicit command_runner and evidence_provider ports are required.")
        if plan.launch_spec_digest != spec.digest:
            raise WorkerLifecycleError("OCI plan does not match the supplied launch specification.")
        self._plan = plan
        self._spec = spec
        self._runner = command_runner
        self._evidence_provider = evidence_provider
        self._trusted_keys = dict(trusted_public_keys)
        self._proxy_addresses = tuple(expected_proxy_addresses)
        self._state = WorkerState.NEW
        self._create_attempted = False
        self._start_attempted = False
        self._cleanup_started = False
        self._worker_result: CommandResult | None = None

    @property
    def state(self) -> WorkerState:
        return self._state

    def _run(self, argv: Sequence[str]) -> CommandResult:
        if not isinstance(argv, (tuple, list)) or not argv or any(type(x) is not str for x in argv):
            raise WorkerLifecycleError("Only non-empty argv vectors are accepted; shell strings are forbidden.")
        result = self._runner(tuple(argv), timeout_seconds=self._spec.job_timeout_seconds)
        if not isinstance(result, CommandResult) or type(result.returncode) is not int:
            raise WorkerLifecycleError("Command runner returned an invalid normalized result.")
        if result.returncode != 0:
            raise WorkerLifecycleError("OCI runtime command failed; lifecycle is fail-closed.")
        return result

    def launch(self, *, challenge: str, now: int) -> CommandResult:
        """Create and inspect a stopped worker, verify signed evidence, then start once."""
        if self._state is not WorkerState.NEW or self._cleanup_started:
            raise WorkerLifecycleError("Worker launch is not repeatable; create a fresh lifecycle.")
        self._create_attempted = True
        try:
            self._run(self._plan.create_argv)
            self._state = WorkerState.CREATED

            inspect_result = self._run(self._plan.inspect_argv)
            self._state = WorkerState.INSPECTED
            envelope = self._evidence_provider(self._plan, inspect_result)

            def start_only_after_attestation(
                passed_spec: WorkerLaunchSpec,
                evidence: VerifiedInspectorEvidence,
            ) -> CommandResult:
                if self._state is not WorkerState.INSPECTED:
                    raise WorkerLifecycleError("START is allowed only after successful INSPECT.")
                if passed_spec != self._spec or evidence.runtime.launch_spec_digest != self._spec.digest:
                    raise WorkerLifecycleError("Attestation is not bound to this exact worker plan.")
                if evidence.runtime.worker_state != "created":
                    raise WorkerLifecycleError("Attested worker is not in the stopped created state.")
                self._state = WorkerState.ATTESTED
                self._start_attempted = True
                result = self._run(self._plan.start_argv)
                self._worker_result = result
                self._state = WorkerState.RUNNING
                return result

            gate = AttestedBrowserRuntime(
                self._spec,
                trusted_public_keys=self._trusted_keys,
                expected_proxy_addresses=self._proxy_addresses,
                worker_start=start_only_after_attestation,
            )
            result = gate.launch(envelope, challenge=challenge, now=now)
            if self._state is not WorkerState.RUNNING or not isinstance(result, CommandResult):
                raise WorkerLifecycleError("Worker did not reach the verified running state.")
            return result
        except Exception as exc:
            self._state = WorkerState.FAILED
            self.cleanup()
            if isinstance(exc, WorkerLifecycleError):
                raise
            if isinstance(exc, BrowserRuntimeGateError):
                raise WorkerLifecycleError("Signed attestation rejected or worker start blocked.") from exc
            raise WorkerLifecycleError("Worker lifecycle failed; cleanup attempted and no fallback is allowed.") from exc

    def cleanup(self) -> None:
        """Best-effort idempotent cleanup; removal is attempted even if stop fails."""
        if self._state is WorkerState.REMOVED or self._cleanup_started:
            return
        self._cleanup_started = True
        stop_error: Exception | None = None
        if self._start_attempted:
            try:
                self._run(self._plan.stop_argv)
                self._state = WorkerState.STOPPED
            except Exception as exc:  # continue to remove even if stop failed
                stop_error = exc
        if self._create_attempted:
            try:
                self._run(self._plan.remove_argv)
                self._state = WorkerState.REMOVED
            except Exception as exc:
                self._state = WorkerState.FAILED
                raise WorkerLifecycleError("Worker removal failed; manual runtime inspection is required.") from exc
        if stop_error is not None:
            raise WorkerLifecycleError("Worker stop failed; removal was attempted.") from stop_error

    def abort(self) -> None:
        """Caller hook for timeout, cancellation, proxy outage or policy failure."""
        self._state = WorkerState.FAILED
        self.cleanup()
