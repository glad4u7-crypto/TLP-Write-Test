"""Attested per-job browser worker bootstrap and lifecycle supervisor.

The module coordinates an independently reviewed OS/container backend with the
existing signed runtime/firewall evidence gate. It does not create namespaces,
containers or nftables rules itself. No backend is bundled or selected by
default; without an explicitly injected trusted backend, execution is blocked.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import ipaddress
import re
import secrets
import threading
import time
from collections.abc import Mapping, Sequence
from typing import Any, Protocol

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from core.attested_browser_runtime import AttestedBrowserRuntime
from core.browser_execution import BrowserExecutionError, CancellationToken
from core.browser_nftables import HostSnapshotSource, collect_signed_inspector_evidence
from core.browser_runtime import WorkerLaunchSpec


class BrowserWorkerBootstrapError(BrowserExecutionError):
    """Raised when a worker cannot be provisioned, attested or reaped safely."""


class RemoteBrowserProcess(Protocol):
    """Control channel to one already-provisioned isolated browser container."""

    def run(
        self,
        job: Any,
        *,
        session_id: str,
        cancellation: CancellationToken,
        deadline_monotonic: float,
        pinned_destination: Any,
    ) -> Mapping[str, Any]: ...

    def terminate(self) -> bool:
        """Return True only after the browser process has exited."""


class IsolatedWorkerBackend(Protocol):
    """Privileged host adapter contract; implementations require separate review.

    provision() must create an unstarted, unprivileged container/VM from exactly
    the supplied immutable spec: dedicated user/PID/network/IPC/UTS/mount
    namespaces, read-only root, no capabilities, no host/secret mounts, bounded
    resources, fresh ephemeral profile, seccomp and no-new-privileges.

    snapshot_source() must read fresh host/runtime state and effective nftables
    state for that exact worker. It must not synthesize or cache evidence.

    start_worker() is called only after the Ed25519/firewall gate passes. The
    backend must start the browser only inside that provisioned worker, with
    the signed numeric proxy endpoint, no direct egress and no host control
    socket/CDP exposure.

    destroy_worker() must remove the worker and its ephemeral storage, and
    return True only after the runtime confirms process exit and cleanup.
    """

    def provision(self, spec: WorkerLaunchSpec, *, session_id: str) -> object: ...
    def snapshot_source(self, handle: object) -> HostSnapshotSource: ...
    def start_worker(
        self, handle: object, spec: WorkerLaunchSpec, verified_evidence: object
    ) -> RemoteBrowserProcess: ...
    def destroy_worker(self, handle: object) -> bool: ...


@dataclass
class _WorkerState:
    session_id: str
    cancelled: threading.Event = field(default_factory=threading.Event)
    ready: threading.Event = field(default_factory=threading.Event)
    closed: threading.Event = field(default_factory=threading.Event)
    cleanup_lock: threading.Lock = field(default_factory=threading.Lock)
    handle: object | None = None
    process: RemoteBrowserProcess | None = None
    cleanup_ok: bool | None = None
    cleanup_error: Exception | None = None
    process_stopped: bool = False


class AttestedBrowserWorkerAdapter:
    """BrowserWorker implementation with one fresh attested worker per job.

    Provisioning happens before evidence collection; browser process startup
    happens only inside AttestedBrowserRuntime's verified worker_start callback.
    Every success, failure, timeout and cancellation attempts worker termination
    and ephemeral-storage deletion. Failed cleanup is never reported as success.
    """

    def __init__(
        self,
        spec: WorkerLaunchSpec,
        *,
        backend: IsolatedWorkerBackend,
        signing_key: Ed25519PrivateKey,
        key_id: str,
        trusted_public_keys: Mapping[str, bytes],
        expected_proxy_addresses: Sequence[str],
        challenge_factory: Any = secrets.token_hex,
        cleanup_wait_seconds: float = 15.0,
    ) -> None:
        if type(spec) is not WorkerLaunchSpec:
            raise TypeError("A validated WorkerLaunchSpec is required.")
        required = ("provision", "snapshot_source", "start_worker", "destroy_worker")
        if backend is None or any(not callable(getattr(backend, name, None)) for name in required):
            raise TypeError("A complete trusted IsolatedWorkerBackend is required.")
        if not isinstance(signing_key, Ed25519PrivateKey):
            raise TypeError("An externally provisioned Ed25519 signing key is required.")
        if type(key_id) is not str or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{2,127}", key_id):
            raise ValueError("A valid inspector key ID is required.")
        if not isinstance(trusted_public_keys, Mapping) or key_id not in trusted_public_keys:
            raise ValueError("The matching inspector public key must be explicitly trusted.")
        if (not isinstance(expected_proxy_addresses, Sequence)
                or isinstance(expected_proxy_addresses, (str, bytes))
                or not 1 <= len(expected_proxy_addresses) <= 8):
            raise ValueError("One to eight exact proxy IP pins are required.")
        normalized_proxy_ips: list[str] = []
        for raw_ip in expected_proxy_addresses:
            if type(raw_ip) is not str:
                raise ValueError("Proxy IP pins must be strings.")
            try:
                address = ipaddress.ip_address(raw_ip)
            except ValueError as exc:
                raise ValueError("Proxy IP pin is malformed.") from exc
            if address.is_unspecified or address.is_loopback or address.is_link_local or address.is_multicast or address.is_reserved:
                raise ValueError("Proxy IP pin is not a usable unicast endpoint.")
            normalized_proxy_ips.append(address.compressed.lower())
        if len(set(normalized_proxy_ips)) != len(normalized_proxy_ips):
            raise ValueError("Duplicate proxy IP pins are not permitted.")
        if not callable(challenge_factory):
            raise TypeError("challenge_factory must be callable.")
        if isinstance(cleanup_wait_seconds, bool) or not isinstance(cleanup_wait_seconds, (int, float)) or not 0 < cleanup_wait_seconds <= 60:
            raise ValueError("cleanup_wait_seconds must be between 0 and 60 seconds.")
        self._spec = spec
        self._backend = backend
        self._signing_key = signing_key
        self._key_id = key_id
        self._trusted_keys = dict(trusted_public_keys)
        self._proxy_addresses = tuple(sorted(normalized_proxy_ips))
        self._challenge_factory = challenge_factory
        self._cleanup_wait = float(cleanup_wait_seconds)
        self._states: dict[str, _WorkerState] = {}
        self._lock = threading.RLock()

    def run(
        self,
        job: Any,
        *,
        session_id: str,
        cancellation: CancellationToken,
        deadline_monotonic: float,
        pinned_destination: Any,
    ) -> Mapping[str, Any]:
        if type(session_id) is not str or len(session_id) < 16:
            raise BrowserWorkerBootstrapError("A unique worker session ID is required.")
        state = _WorkerState(session_id=session_id)
        with self._lock:
            if session_id in self._states:
                raise BrowserWorkerBootstrapError("Worker session IDs cannot be reused.")
            self._states[session_id] = state

        try:
            self._check_cancel(state, cancellation, deadline_monotonic)
            state.handle = self._backend.provision(self._spec, session_id=session_id)
            if state.handle is None:
                raise BrowserWorkerBootstrapError("Backend did not return a worker handle.")
            self._check_cancel(state, cancellation, deadline_monotonic)

            source = self._backend.snapshot_source(state.handle)
            if not isinstance(source, HostSnapshotSource):
                raise BrowserWorkerBootstrapError("Backend did not provide a trusted host snapshot source.")
            challenge = self._challenge_factory(32)
            if type(challenge) is not str or len(challenge) != 64:
                raise BrowserWorkerBootstrapError("Challenge factory did not return a 256-bit hex challenge.")

            evidence = collect_signed_inspector_evidence(
                source,
                self._spec,
                challenge=challenge,
                key_id=self._key_id,
                signing_key=self._signing_key,
                expected_proxy_addresses=self._proxy_addresses,
                now=int(time.time()),
            )
            self._check_cancel(state, cancellation, deadline_monotonic)

            def start_after_gate(spec: WorkerLaunchSpec, verified: object) -> RemoteBrowserProcess:
                self._check_cancel(state, cancellation, deadline_monotonic)
                process = self._backend.start_worker(state.handle, spec, verified)
                if process is None or not callable(getattr(process, "run", None)) or not callable(getattr(process, "terminate", None)):
                    raise BrowserWorkerBootstrapError("Backend returned an invalid remote browser process.")
                state.process = process
                state.ready.set()
                return process

            gate = AttestedBrowserRuntime(
                self._spec,
                trusted_public_keys=self._trusted_keys,
                expected_proxy_addresses=self._proxy_addresses,
                worker_start=start_after_gate,
            )
            process = gate.launch(
                evidence,
                challenge=challenge,
                now=int(time.time()),
            )
            if process is not state.process:
                raise BrowserWorkerBootstrapError("Attested gate returned an unexpected worker process.")
            self._check_cancel(state, cancellation, deadline_monotonic)
            result = process.run(
                job,
                session_id=session_id,
                cancellation=cancellation,
                deadline_monotonic=deadline_monotonic,
                pinned_destination=pinned_destination,
            )
            if not isinstance(result, Mapping):
                raise BrowserWorkerBootstrapError("Remote browser returned a non-mapping result.")
            return dict(result)
        except BrowserWorkerBootstrapError:
            raise
        except Exception as exc:
            raise BrowserWorkerBootstrapError("Isolated browser worker bootstrap or execution failed closed.") from exc
        finally:
            if not self._cleanup(state):
                raise BrowserWorkerBootstrapError("Worker process exit or ephemeral-storage cleanup was not confirmed.") from state.cleanup_error
            with self._lock:
                self._states.pop(session_id, None)

    @staticmethod
    def _check_cancel(
        state: _WorkerState,
        cancellation: CancellationToken,
        deadline_monotonic: float,
    ) -> None:
        if state.cancelled.is_set() or cancellation.cancelled:
            raise BrowserWorkerBootstrapError("Worker bootstrap or execution was cancelled.")
        if time.monotonic() >= deadline_monotonic:
            raise BrowserWorkerBootstrapError("Worker bootstrap or execution exceeded its hard deadline.")

    def terminate(self, session_id: str) -> bool:
        """Request cancellation and wait for confirmed worker + storage teardown."""
        with self._lock:
            state = self._states.get(session_id)
        if state is None:
            return False
        state.cancelled.set()
        # Never destroy a handle from the cancellation thread while run() may
        # still be provisioning it. If a process already exists, ask that
        # process to stop; run() owns final resource teardown in its finally.
        process_stopped = True
        if not state.cleanup_lock.acquire(timeout=self._cleanup_wait):
            return False
        try:
            process = state.process
            if process is not None and not state.process_stopped:
                try:
                    state.process_stopped = process.terminate() is True
                except Exception:
                    state.process_stopped = False
                process_stopped = state.process_stopped
        finally:
            state.cleanup_lock.release()
        if not state.closed.wait(timeout=self._cleanup_wait):
            return False
        return process_stopped and state.cleanup_ok is True

    def _cleanup(self, state: _WorkerState) -> bool:
        if not state.cleanup_lock.acquire(timeout=self._cleanup_wait):
            return False
        try:
            if state.closed.is_set():
                return state.cleanup_ok is True
            errors: list[Exception] = []
            if state.process is not None and not state.process_stopped:
                try:
                    if state.process.terminate() is not True:
                        raise RuntimeError("Remote browser process exit was not confirmed.")
                    state.process_stopped = True
                except Exception as exc:
                    errors.append(exc)
            if state.handle is not None:
                try:
                    if self._backend.destroy_worker(state.handle) is not True:
                        raise RuntimeError("Container/VM and ephemeral storage removal was not confirmed.")
                except Exception as exc:
                    errors.append(exc)
            state.cleanup_ok = not errors
            state.cleanup_error = errors[0] if errors else None
            state.closed.set()
            return state.cleanup_ok
        finally:
            state.cleanup_lock.release()
