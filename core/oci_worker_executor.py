"""Fail-closed OCI worker lifecycle executor.

Commands are executed as argv (never through a shell). The executor creates a
stopped container, inspects its effective configuration, obtains fresh signed
host evidence, verifies that evidence, and only then starts the worker.
No default host command is run at import or construction time.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import secrets
import shutil
import subprocess
import time
from collections.abc import Callable, Mapping, Sequence
from typing import Protocol

from core.browser_inspector import verify_signed_inspector_evidence
from core.browser_runtime import WorkerLaunchSpec
from core.oci_worker_plan import OCIWorkerPlan
from core.inspector_control_plane import InspectorEvidenceControlPlane
from core.storage import TenantKey


class OCIExecutionError(RuntimeError):
    """Raised when an OCI lifecycle stage fails closed."""


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
        try:
            decoded = json.loads(raw)
        except (TypeError, ValueError) as exc:
            raise OCIExecutionError("inspect: runtime returned invalid JSON.") from exc
        if not isinstance(decoded, list) or len(decoded) != 1 or not isinstance(decoded[0], dict):
            raise OCIExecutionError("inspect: expected exactly one container object.")
        item = decoded[0]
        state = item.get("State")
        config = item.get("Config")
        host = item.get("HostConfig")
        network = host.get("NetworkMode") if isinstance(host, dict) else None
        if not isinstance(state, dict) or state.get("Status") != "created":
            raise OCIExecutionError("inspect: worker is not confirmed stopped in created state.")
        container_id = item.get("Id")
        if type(container_id) is not str or len(container_id) < 12:
            raise OCIExecutionError("inspect: runtime did not return a valid immutable container ID.")
        if not isinstance(config, dict) or config.get("Image") != plan.image:
            raise OCIExecutionError("inspect: effective image differs from the digest-pinned plan.")
        if not isinstance(host, dict):
            raise OCIExecutionError("inspect: effective host configuration is missing.")
        if host.get("ReadonlyRootfs") is not True:
            raise OCIExecutionError("inspect: read-only root filesystem is not enforced.")
        if network != plan.network_name:
            raise OCIExecutionError("inspect: effective network differs from the approved APAA network.")
        if host.get("Privileged") is True or host.get("PidMode") == "host" or host.get("IpcMode") == "host":
            raise OCIExecutionError("inspect: privileged or host namespace mode detected.")
        caps = host.get("CapDrop")
        if not isinstance(caps, list) or "ALL" not in caps:
            raise OCIExecutionError("inspect: Linux capabilities are not fully dropped.")
        security = host.get("SecurityOpt")
        if not isinstance(security, list) or not any(
            isinstance(x, str) and x.startswith("no-new-privileges") for x in security
        ) or not any(isinstance(x, str) and x.startswith("seccomp=") for x in security):
            raise OCIExecutionError("inspect: no-new-privileges/seccomp are not both enforced.")
        snapshot = {
            "container_id": container_id,
            "container_name": plan.container_name,
            "image": config.get("Image"),
            "state": state.get("Status"),
            "network": network,
            "readonly_rootfs": host.get("ReadonlyRootfs"),
            "cap_drop": tuple(caps),
            "security_options": tuple(security),
            "launch_spec_digest": plan.launch_spec_digest,
        }
        return container_id, snapshot

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
            self._run(plan.create_argv, "create")
            created = True
            events.append(LifecycleEvent("CREATE", "PASS", "container created stopped"))
            inspect_result = self._run(plan.inspect_argv, "inspect")
            container_id, snapshot = self._inspect_snapshot(inspect_result.stdout, plan)
            events.append(LifecycleEvent("INSPECT", "PASS", "effective stopped configuration checked"))

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
                try:
                    cleanup = plan.stop_argv if started else plan.remove_argv
                    self._run(cleanup, "cleanup")
                    if started:
                        self._run(plan.remove_argv, "cleanup-remove")
                    events.append(LifecycleEvent("CLEANUP", "PASS", "worker cleanup completed"))
                    cleaned = True
                except Exception:
                    events.append(LifecycleEvent("CLEANUP", "FAIL", "manual host cleanup required"))
                    cleaned = False
            else:
                cleaned = True
            return OCIExecutionReport(None, tuple(events), False, cleaned)
