"""Fail-closed OCI worker lifecycle executor.

Commands are executed as argv (never through a shell). The executor creates a
stopped container, inspects its effective configuration, obtains fresh signed
host evidence, verifies that evidence, and only then starts the worker.
No default host command is run at import or construction time.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import re
import secrets
import shutil
import subprocess
import time
from collections.abc import Callable, Mapping, Sequence
from typing import Protocol

from core.browser_inspector import verify_signed_inspector_evidence
from core.oci_errors import OCIExecutionError
from core.oci_inspect_normalizer import normalize_oci_inspect
from core.browser_runtime import WorkerLaunchSpec
from core.oci_worker_plan import OCIWorkerPlan
from core.inspector_control_plane import InspectorEvidenceControlPlane
from core.storage import TenantKey


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


class CommandRunner(Protocol):
    def __call__(self, argv: Sequence[str], timeout_seconds: int) -> CommandResult: ...


@dataclass(frozen=True)
class LifecycleEvent:
    stage: str
    outcome: str
    detail: str = ""


@dataclass(frozen=True)
class OCIWorkerHandle:
    container_id: str
    container_name: str
    launch_spec_digest: str
    runtime: str


@dataclass(frozen=True)
class OCIExecutionReport:
    handle: OCIWorkerHandle | None
    events: tuple[LifecycleEvent, ...]
    started: bool
    cleaned: bool


def subprocess_command_runner(argv: Sequence[str], timeout_seconds: int) -> CommandResult:
    """Run one argv vector without a shell; binary lookup is explicit and bounded."""
    if not isinstance(argv, (tuple, list)) or not argv or any(type(x) is not str or not x for x in argv):
        raise OCIExecutionError("Command must be a non-empty argv sequence.")
    if type(timeout_seconds) is not int or not 1 <= timeout_seconds <= 120:
        raise OCIExecutionError("Command timeout must be between 1 and 120 seconds.")
    executable = shutil.which(argv[0])
    if executable is None:
        raise OCIExecutionError("Requested OCI runtime binary is not installed.")
    try:
        completed = subprocess.run(
            (executable, *argv[1:]), shell=False, check=False,
            capture_output=True, text=True, timeout=timeout_seconds,
            close_fds=True,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise OCIExecutionError("OCI command could not complete within its bounded execution window.") from exc
    return CommandResult(completed.returncode, completed.stdout, completed.stderr)


class OCIWorkerExecutor:
    """Create -> inspect -> attest -> start, with bounded fail-closed cleanup."""

    def __init__(
        self,
        *,
        runner: CommandRunner,
        evidence_supplier: Callable[[str, Mapping[str, object]], object],
        trusted_public_keys: Mapping[str, bytes],
        expected_proxy_addresses: Sequence[str],
        inspector_control_plane: InspectorEvidenceControlPlane | None = None,
        tenant: TenantKey | None = None,
        clock: Callable[[], int] = lambda: int(time.time()),
        challenge_factory: Callable[[], str] = lambda: secrets.token_hex(32),
        command_timeout_seconds: int = 15,
    ) -> None:
        if not callable(runner) or not callable(evidence_supplier):
            raise TypeError("Explicit command runner and evidence supplier are required.")
        if not isinstance(trusted_public_keys, Mapping) or not trusted_public_keys:
            raise TypeError("Out-of-band trusted inspector keys are required.")
        if not isinstance(expected_proxy_addresses, Sequence) or isinstance(expected_proxy_addresses, (str, bytes)):
            raise TypeError("Expected proxy IP addresses must be an explicit sequence.")
        if type(command_timeout_seconds) is not int or not 1 <= command_timeout_seconds <= 120:
            raise ValueError("Command timeout must be between 1 and 120 seconds.")
        self._runner = runner
        self._evidence_supplier = evidence_supplier
        self._keys = dict(trusted_public_keys)
        self._proxy_ips = tuple(expected_proxy_addresses)
        if (inspector_control_plane is None) != (tenant is None):
            raise TypeError('Inspector control plane and tenant must be configured together.')
        if inspector_control_plane is not None and not isinstance(inspector_control_plane, InspectorEvidenceControlPlane):
            raise TypeError('A trusted InspectorEvidenceControlPlane is required.')
        if tenant is not None and not isinstance(tenant, TenantKey):
            raise TypeError('A validated TenantKey is required.')
        self._control_plane = inspector_control_plane
        self._tenant = tenant
        self._clock = clock
        self._challenge_factory = challenge_factory
        self._timeout = command_timeout_seconds

    def _run(self, argv: Sequence[str], stage: str) -> CommandResult:
        result = self._runner(tuple(argv), self._timeout)
        if not isinstance(result, CommandResult) or type(result.returncode) is not int:
            raise OCIExecutionError(f"{stage}: command runner returned an invalid result.")
        if result.returncode != 0:
            raise OCIExecutionError(f"{stage}: OCI command failed (exit {result.returncode}).")
        return result

    @staticmethod
    def _inspect_snapshot(raw: str, plan: OCIWorkerPlan) -> tuple[str, dict[str, object]]:
        normalized = normalize_oci_inspect(raw, plan)
        snapshot = {
            "container_id": normalized.container_id,
            "container_name": normalized.container_name,
            "image": normalized.image,
            "state": normalized.state,
            "network": normalized.network,
            "readonly_rootfs": normalized.readonly_rootfs,
            "cap_drop": normalized.cap_drop,
            "security_options": normalized.security_options,
            "launch_spec_digest": normalized.launch_spec_digest,
        }
        return normalized.container_id, snapshot

    def _cleanup(
        self, plan: OCIWorkerPlan, events: list[LifecycleEvent], *, started: bool,
        container_id: str | None,
    ) -> bool:
        """Always attempt force-remove by immutable ID, even if graceful stop fails."""
        target = container_id or plan.container_name
        stop_argv = (plan.runtime, "stop", "--time", "2", target)
        remove_argv = (plan.runtime, "rm", "--force", target)
        if started:
            try:
                self._run(stop_argv, "cleanup-stop")
                events.append(LifecycleEvent("STOP", "PASS", "graceful stop completed"))
            except Exception as exc:
                events.append(LifecycleEvent("STOP", "FAIL", type(exc).__name__))
        try:
            self._run(remove_argv, "cleanup-remove")
            events.append(LifecycleEvent("CLEANUP", "PASS", "force-remove completed"))
            # A successful force-remove is the authoritative no-container result.
            return True
        except Exception as exc:
            events.append(LifecycleEvent("CLEANUP", "FAIL", type(exc).__name__))
            return False

    def stop(self, handle: OCIWorkerHandle, plan: OCIWorkerPlan) -> OCIExecutionReport:
        """Stop and remove only the exact worker represented by a validated plan/handle."""
        if not isinstance(handle, OCIWorkerHandle) or not isinstance(plan, OCIWorkerPlan):
            raise TypeError("A worker handle and its validated OCIWorkerPlan are required.")
        if (
            handle.runtime != plan.runtime
            or handle.container_name != plan.container_name
            or handle.launch_spec_digest != plan.launch_spec_digest
            or type(handle.container_id) is not str
            or re.fullmatch(r"[0-9a-fA-F]{12,64}", handle.container_id) is None
        ):
            raise OCIExecutionError("Worker handle does not match the supplied immutable OCI plan.")
        events: list[LifecycleEvent] = [LifecycleEvent("STOP_REQUEST", "PASS", "exact plan/handle binding validated")]
        cleaned = self._cleanup(plan, events, started=True, container_id=handle.container_id)
        return OCIExecutionReport(None, tuple(events), False, cleaned)

    def launch(self, plan: OCIWorkerPlan, spec: WorkerLaunchSpec) -> OCIExecutionReport:
        if not isinstance(plan, OCIWorkerPlan) or type(spec) is not WorkerLaunchSpec:
            raise TypeError("A validated OCIWorkerPlan and WorkerLaunchSpec are required.")
        if plan.launch_spec_digest != spec.digest:
            raise OCIExecutionError("Plan and worker launch specification digest do not match.")

        events: list[LifecycleEvent] = []
        created = False
        started = False
        container_id: str | None = None
        try:
            create_result = self._run(plan.create_argv, "create")
            created = True
            created_id = create_result.stdout.strip()
            if re.fullmatch(r"[0-9a-fA-F]{12,64}", created_id) is None:
                raise OCIExecutionError("create: runtime did not return a valid immutable container ID.")
            container_id = created_id
            events.append(LifecycleEvent("CREATE", "PASS", "stopped container created; immutable ID captured"))
            inspect_argv = (plan.runtime, "inspect", container_id)
            inspect_result = self._run(inspect_argv, "inspect")
            inspected_id, snapshot = self._inspect_snapshot(inspect_result.stdout, plan)
            if inspected_id.lower() != container_id.lower():
                raise OCIExecutionError("inspect: immutable container ID differs from CREATE result.")
            events.append(LifecycleEvent("INSPECT", "PASS", "effective stopped configuration checked by immutable ID"))

            if self._control_plane is None or self._tenant is None:
                raise OCIExecutionError(
                    "attestation: durable tenant-bound challenge control plane is required; stateless launch is blocked."
                )
            challenge = self._control_plane.issue_challenge(
                self._tenant, runtime_id=container_id,
                worker_id=plan.container_name, ttl_seconds=60, now=self._clock(),
            )
            evidence = self._evidence_supplier(challenge.value, snapshot)
            accepted = self._control_plane.verify_and_consume(
                self._tenant, spec, evidence,
                expected_challenge=challenge.value,
                expected_runtime_id=container_id,
                expected_worker_id=plan.container_name,
                expected_proxy_addresses=self._proxy_ips,
                now=self._clock(), max_age_seconds=60,
            )
            if (accepted.evidence.runtime.launch_spec_digest != plan.launch_spec_digest
                    or accepted.evidence.runtime.runtime_id != container_id
                    or accepted.evidence.runtime.worker_id != plan.container_name):
                raise OCIExecutionError("attestation: signed evidence is not bound to this exact OCI worker.")
            events.append(LifecycleEvent("ATTEST", "PASS", "signed evidence, exact OCI identity and single-use challenge verified"))

            self._run(plan.start_argv, "start")
            started = True
            events.append(LifecycleEvent("START", "PASS", "worker start authorized after attestation"))
            handle = OCIWorkerHandle(container_id, plan.container_name, plan.launch_spec_digest, plan.runtime)
            return OCIExecutionReport(handle, tuple(events), True, False)
        except Exception as exc:
            events.append(LifecycleEvent("BLOCK", "PASS", type(exc).__name__))
            if created:
                cleaned = self._cleanup(plan, events, started=started, container_id=container_id)
            else:
                cleaned = True
            return OCIExecutionReport(None, tuple(events), False, cleaned)
