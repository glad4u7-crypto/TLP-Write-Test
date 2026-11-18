"""P74 browser execution boundary: pinned HTTPS transport and job lifecycle.

This module provides enforceable client-side primitives and an adapter contract.
It does NOT create an OS sandbox or firewall. Production browser execution must
be supplied by a separately reviewed container/VM adapter and verified by the
signed attestation gate in core.attested_browser_runtime.
"""
from __future__ import annotations

from dataclasses import dataclass
import http.client
import ipaddress
import json
import ssl
import threading
import time
import uuid
from collections.abc import Callable, Mapping, Sequence
from typing import Any, Protocol

from core.attested_browser_runtime import AttestedBrowserRuntime
from core.browser_security import (
    BrowserJob,
    BrowserPolicyError,
    canonicalize_https_url,
    validate_browser_job,
    validate_dns_answers,
    validate_redirect,
    validate_destination,
)


class BrowserExecutionError(RuntimeError):
    """Raised when secure browser execution cannot proceed."""


class BrowserCancelled(BrowserExecutionError):
    """Raised when a browser job is cancelled."""


class BrowserTimeout(BrowserExecutionError):
    """Raised when the hard browser job deadline expires."""


class CancellationToken:
    """Thread-safe cooperative cancellation token with idempotent cancel()."""

    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> bool:
        was_set = self._event.is_set()
        self._event.set()
        return not was_set

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    def raise_if_cancelled(self) -> None:
        if self.cancelled:
            raise BrowserCancelled("Browser job was cancelled.")


@dataclass(frozen=True)
class PinnedDestination:
    """Exact DNS pin set bound to an HTTPS origin."""

    hostname: str
    port: int
    addresses: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.hostname or type(self.port) is not int or not 1 <= self.port <= 65535:
            raise ValueError("Invalid pinned destination.")
        try:
            host_literal = ipaddress.ip_address(self.hostname)
            host_for_url = f"[{self.hostname}]" if host_literal.version == 6 else self.hostname
        except ValueError:
            host_for_url = self.hostname
        canonical = canonicalize_https_url(f"https://{host_for_url}:{self.port}/")
        if canonical.hostname != self.hostname.lower() or canonical.port != self.port:
            raise ValueError("Pinned hostname/port must be canonical.")
        if not self.addresses:
            raise ValueError("At least one pinned address is required.")
        try:
            normalized = validate_dns_answers(self.hostname, self.addresses)
        except BrowserPolicyError as exc:
            raise ValueError("Pinned destinations must contain only public unicast IPs.") from exc
        if len(normalized) != len(self.addresses):
            raise ValueError("Duplicate pinned addresses are not permitted.")
        object.__setattr__(self, "addresses", normalized)


def resolve_pinned_destination(
    url: str,
    *,
    resolver: Callable[[str], Sequence[str]],
) -> tuple[Any, PinnedDestination]:
    """Resolve a canonical HTTPS URL now and bind its complete validated IP set."""
    if not callable(resolver):
        raise BrowserExecutionError("A live DNS resolver is required for destination pinning.")
    target = canonicalize_https_url(url)
    try:
        literal = ipaddress.ip_address(target.hostname)
        answers: Sequence[str] = [literal.compressed]
    except ValueError:
        try:
            answers = resolver(target.hostname)
        except Exception as exc:
            raise BrowserExecutionError("Destination DNS resolution failed during DNS/IP pin validation.") from exc
    try:
        addresses = validate_dns_answers(target.hostname, answers)
        destination = PinnedDestination(target.hostname, target.port, addresses)
    except (BrowserPolicyError, TypeError, ValueError) as exc:
        raise BrowserExecutionError("Destination failed live DNS/IP pin validation.") from exc
    return target, destination


def authorize_redirect_and_pin(
    current_url: str,
    location: str,
    allowed_origins: Sequence[str],
    *,
    resolver: Callable[[str], Sequence[str]],
) -> tuple[Any, PinnedDestination]:
    """Authorize one redirect and resolve a fresh pin set before it can connect.

    This deliberately returns a new destination object. Callers must discard the
    previous connection/pin and create a new PinnedHTTPSConnection from this pin.
    """
    if not callable(resolver):
        raise BrowserExecutionError("Redirects require a live DNS resolver.")
    try:
        validate_destination(current_url, allowed_origins)
        target = validate_redirect(current_url, location, allowed_origins)
    except BrowserPolicyError as exc:
        raise BrowserExecutionError("Redirect target failed URL/origin policy.") from exc
    return resolve_pinned_destination(target.url, resolver=resolver)


class PinnedHTTPSConnection(http.client.HTTPSConnection):
    """HTTPS connection that dials only a pre-authorized IP, with normal TLS SNI.

    Certificate-chain validation and hostname verification remain enabled.
    The HTTP Host header remains the logical hostname. Redirects are deliberately
    not followed here; callers must re-authorize every redirect and obtain a new
    pin set. A host firewall/proxy is still required to prevent other processes
    or browser traffic from bypassing this transport.
    """

    def __init__(
        self,
        destination: PinnedDestination,
        *,
        timeout: float = 10.0,
        context: ssl.SSLContext | None = None,
    ) -> None:
        if type(destination) is not PinnedDestination:
            raise TypeError("A validated PinnedDestination is required.")
        self.destination = destination
        tls_context = context or ssl.create_default_context(purpose=ssl.Purpose.SERVER_AUTH)
        if tls_context.verify_mode != ssl.CERT_REQUIRED or not tls_context.check_hostname:
            raise ValueError("TLS certificate-chain and hostname verification are mandatory.")
        if tls_context.minimum_version < ssl.TLSVersion.TLSv1_2:
            raise ValueError("TLS 1.2 or newer is mandatory.")
        if (
            tls_context.maximum_version != ssl.TLSVersion.MAXIMUM_SUPPORTED
            and tls_context.maximum_version < ssl.TLSVersion.TLSv1_2
        ):
            raise ValueError("TLS context does not permit TLS 1.2 or newer.")
        super().__init__(
            destination.hostname,
            destination.port,
            timeout=timeout,
            context=tls_context,
        )

    def connect(self) -> None:
        last_error: OSError | None = None
        for pinned_ip in self.destination.addresses:
            raw = None
            try:
                raw = self._create_connection((pinned_ip, self.destination.port), self.timeout)
                peer = ipaddress.ip_address(raw.getpeername()[0]).compressed
                if peer != pinned_ip:
                    raise BrowserExecutionError("Socket peer differs from the authorized pinned IP.")
                self.sock = self._context.wrap_socket(
                    raw,
                    server_hostname=self.destination.hostname,
                )
                return
            except BrowserExecutionError:
                if raw is not None:
                    try:
                        raw.close()
                    except OSError:
                        pass
                # A peer mismatch is a security violation, never a fallback case.
                raise
            except ssl.SSLCertVerificationError as exc:
                if raw is not None:
                    try:
                        raw.close()
                    except OSError:
                        pass
                # Certificate/hostname failures are terminal. Trying another IP
                # could hide a broken or malicious endpoint configuration.
                raise BrowserExecutionError("TLS certificate or hostname verification failed.") from exc
            except ssl.SSLError as exc:
                if raw is not None:
                    try:
                        raw.close()
                    except OSError:
                        pass
                raise BrowserExecutionError("TLS handshake failed; pinned connection aborted.") from exc
            except OSError as exc:
                last_error = exc
                if raw is not None:
                    try:
                        raw.close()
                    except OSError:
                        pass
        raise BrowserExecutionError("All pinned HTTPS connection attempts failed.") from last_error


class BrowserWorker(Protocol):
    """Trusted adapter contract; implementation must provide OS-level isolation."""

    def run(
        self,
        job: BrowserJob,
        *,
        session_id: str,
        cancellation: CancellationToken,
        deadline_monotonic: float,
        pinned_destination: PinnedDestination,
    ) -> Mapping[str, Any]:
        """Return only after the per-job browser context and profile are destroyed."""

    def terminate(self, session_id: str) -> bool:
        """Kill the isolated worker and block until OS confirms process exit.

        Return True only after process exit and ephemeral storage cleanup are
        confirmed. Returning None/False is a security failure.
        """


AuditWriter = Callable[[Mapping[str, Any]], None]


def _validate_json_tree(value: Any, *, depth: int = 0) -> None:
    """Reject non-JSON objects, non-string object keys, and excessive nesting."""
    if depth > 64:
        raise ValueError("Worker result nesting exceeds the safety limit.")
    if isinstance(value, Mapping):
        for key, child in value.items():
            if type(key) is not str:
                raise TypeError("JSON object keys must be strings.")
            _validate_json_tree(child, depth=depth + 1)
    elif isinstance(value, (list, tuple)):
        for child in value:
            _validate_json_tree(child, depth=depth + 1)
    elif value is not None and type(value) not in (str, bool, int, float):
        raise TypeError("Worker result contains a non-JSON value.")


class BrowserExecutionCoordinator:
    """Fail-closed coordinator joining validation, cancellation and audit.

    The worker is an explicit privileged adapter. No default or local-process
    fallback exists. Audit write failure blocks execution and is also surfaced
    during completion. Session identifiers are generated per job and never
    reused; worker adapters must use a fresh browser context/profile each time.
    """

    def __init__(
        self,
        worker: BrowserWorker | None,
        *,
        audit: AuditWriter,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if worker is not None and not callable(getattr(worker, "run", None)):
            raise TypeError("worker must implement run().")
        if not callable(audit):
            raise TypeError("audit must be callable.")
        self._worker = worker
        self._audit = audit
        self._clock = clock
        self._active: dict[str, tuple[CancellationToken, str, threading.Event, threading.Event]] = {}
        self._lock = threading.RLock()

    @classmethod
    def from_attested_runtime(
        cls,
        runtime_gate: Any,
        signed_evidence: object,
        *,
        challenge: str,
        now: int,
        audit: AuditWriter,
        clock: Callable[[], float] = time.monotonic,
    ) -> "BrowserExecutionCoordinator":
        """Create a coordinator only after the signed runtime/firewall gate passes."""
        if type(runtime_gate) is not AttestedBrowserRuntime:
            raise TypeError("A concrete AttestedBrowserRuntime gate is required.")
        worker = runtime_gate.launch(signed_evidence, challenge=challenge, now=now)
        if not callable(getattr(worker, "run", None)) or not callable(getattr(worker, "terminate", None)):
            raise BrowserExecutionError("Attested runtime returned an invalid worker handle.")
        return cls(worker, audit=audit, clock=clock)

    def _record(self, event: str, *, job_id: str, session_id: str, detail: str) -> None:
        # Never place cookies, page contents, credentials, or URL query values
        # in the audit record. The caller may attach a separate approved digest.
        record = {
            "schema_version": 1,
            "event": event,
            "job_id": job_id,
            "session_id": session_id,
            "detail": detail,
            "timestamp_unix": time.time(),
        }
        self._audit(record)

    def cancel(self, job_id: str) -> bool:
        with self._lock:
            active = self._active.get(job_id)
            if active is None:
                return False
            token, session_id, termination_confirmed, completed = active
            changed = token.cancel()
        if not changed:
            return False
        # Record cancellation before terminating the worker: otherwise the
        # worker's completion thread can race ahead and write job_cancelled
        # before cancel_requested. Audit failure must not prevent termination.
        audit_error = None
        try:
            self._record("cancel_requested", job_id=job_id, session_id=session_id, detail="user_or_controller")
        except Exception as exc:
            audit_error = exc
        termination_error = None
        if self._worker is not None:
            try:
                if self._worker.terminate(session_id) is not True:
                    raise BrowserExecutionError("Worker termination was not confirmed.")
                termination_confirmed.set()
                if not completed.wait(timeout=2.0):
                    raise BrowserExecutionError("Worker supervisor did not stop after process termination.")
            except Exception as exc:
                termination_error = exc
        if termination_error is not None:
            try:
                self._record("worker_terminate_error", job_id=job_id, session_id=session_id, detail="adapter_error")
            except Exception as exc:
                if audit_error is None:
                    audit_error = exc
        if termination_error is not None:
            raise BrowserExecutionError("Worker termination failed; job remains cancelled.") from termination_error
        if audit_error is not None:
            raise BrowserExecutionError("Cancellation audit write failed after worker termination.") from audit_error
        return changed

    def execute(self, raw_job: object, *, resolver: Callable[[str], list[str]]) -> Mapping[str, Any]:
        if self._worker is None:
            raise BrowserExecutionError("No attested isolated worker adapter is configured; execution is disabled.")
        # Live execution always resolves now, validates every answer, and passes
        # the exact pin set to the worker.
        try:
            job = validate_browser_job(raw_job)
            target, pinned = resolve_pinned_destination(job.url, resolver=resolver)
        except (BrowserPolicyError, TypeError, ValueError, OSError) as exc:
            raise BrowserExecutionError("Browser job failed live DNS/IP pin validation.") from exc

        session_id = uuid.uuid4().hex
        token = CancellationToken()
        termination_confirmed = threading.Event()
        completed = threading.Event()
        outcome: dict[str, Any] = {}
        deadline = self._clock() + job.max_runtime_seconds
        cleanup_mode: str | None = None
        try:
            self._record("job_accepted", job_id=job.job_id, session_id=session_id, detail="policy_validated")
            token.raise_if_cancelled()
            def invoke_worker() -> None:
                try:
                    outcome["result"] = self._worker.run(
                        job,
                        session_id=session_id,
                        cancellation=token,
                        deadline_monotonic=deadline,
                        pinned_destination=pinned,
                    )
                except BaseException as exc:
                    outcome["error"] = exc
                finally:
                    completed.set()

            worker_thread = threading.Thread(
                target=invoke_worker,
                name=f"apaa-browser-{session_id[:12]}",
                daemon=True,
            )
            # Register and start while holding the lock: cancel() cannot observe
            # a session whose worker thread has not started yet.
            with self._lock:
                if job.job_id in self._active:
                    raise BrowserExecutionError("Duplicate active browser job ID.")
                self._active[job.job_id] = (token, session_id, termination_confirmed, completed)
                worker_thread.start()
            timed_out = False
            while not completed.is_set():
                remaining = deadline - self._clock()
                if remaining <= 0:
                    timed_out = True
                    break
                completed.wait(timeout=min(remaining, 0.05))
                if token.cancelled:
                    break
            if timed_out:
                token.cancel()
                try:
                    if self._worker.terminate(session_id) is not True:
                        raise BrowserExecutionError("Worker termination was not confirmed.")
                    if not completed.wait(timeout=2.0):
                        raise BrowserExecutionError("Worker supervisor did not stop after process termination.")
                    cleanup_mode = "worker_process_exit_confirmed"
                except Exception as exc:
                    self._record("worker_terminate_error", job_id=job.job_id, session_id=session_id, detail="timeout_termination_error")
                    raise BrowserExecutionError("Timed-out browser worker could not be terminated.") from exc
                self._record("job_timed_out", job_id=job.job_id, session_id=session_id, detail="hard_deadline")
                raise BrowserTimeout("Browser job exceeded its hard runtime deadline.")
            token.raise_if_cancelled()
            if "error" in outcome:
                raise outcome["error"]
            result = outcome.get("result")
            cleanup_mode = "browser_context_destroyed"  # run() returned after context/profile teardown.
            if self._clock() > deadline:
                self._record("job_timed_out", job_id=job.job_id, session_id=session_id, detail="hard_deadline")
                raise BrowserTimeout("Browser job exceeded its hard runtime deadline.")
            if not isinstance(result, Mapping):
                raise BrowserExecutionError("Worker returned an invalid result envelope.")
            try:
                result_dict = dict(result)
                _validate_json_tree(result_dict)
                encoded_result = json.dumps(
                    result_dict, ensure_ascii=False, allow_nan=False,
                    separators=(",", ":"),
                ).encode("utf-8")
            except (TypeError, ValueError, UnicodeError, RecursionError) as exc:
                raise BrowserExecutionError("Worker result is not a valid JSON envelope.") from exc
            if len(encoded_result) > job.max_response_bytes:
                raise BrowserExecutionError("Worker result exceeded the approved response byte limit.")
            self._record("job_completed", job_id=job.job_id, session_id=session_id, detail="success")
            return result_dict
        except BrowserCancelled:
            self._record("job_cancelled", job_id=job.job_id, session_id=session_id, detail="cancelled")
            raise
        except BrowserTimeout:
            raise
        except Exception:
            self._record("job_failed", job_id=job.job_id, session_id=session_id, detail="execution_error")
            raise
        finally:
            with self._lock:
                self._active.pop(job.job_id, None)
            if termination_confirmed.is_set():
                cleanup_mode = "worker_process_exit_confirmed"
            elif token.cancelled:
                # Give the cancelling controller a bounded opportunity to
                # confirm OS process exit before emitting the cleanup audit.
                if termination_confirmed.wait(timeout=2.0):
                    cleanup_mode = "worker_process_exit_confirmed"
            try:
                self._record(
                    "session_closed" if cleanup_mode is not None else "session_cleanup_unconfirmed",
                    job_id=job.job_id, session_id=session_id,
                    detail=cleanup_mode or "termination_not_confirmed",
                )
            except Exception as exc:
                # Audit integrity is mandatory: never silently swallow it.
                raise BrowserExecutionError("Final browser audit write failed.") from exc
