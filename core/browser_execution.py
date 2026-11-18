"""P74 browser execution boundary: pinned HTTPS transport and job lifecycle.

This module provides enforceable client-side primitives and an adapter contract.
It does NOT create an OS sandbox or firewall. Production browser execution must
be supplied by a separately reviewed container/VM adapter and verified by the
signed attestation gate in core.attested_browser_runtime.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import http.client
import ipaddress
import json
import ssl
import threading
import time
import uuid
from collections.abc import Callable, Mapping, Sequence
from typing import Any, Protocol

from core.approvals import ApprovalAuthority, ApprovalReceipt
from core.attested_browser_runtime import AttestedBrowserRuntime
from core.browser_recovery import BrowserDispatchBlocked, RecoveryLedgerError, SQLiteBrowserRecoveryLedger
from core.identity import Principal, require_authenticated
from core.storage import TenantKey
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


def _approval_job_payload(job: BrowserJob) -> dict[str, Any]:
    payload = asdict(job)
    payload["allowed_origins"] = list(job.allowed_origins)
    return payload


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
        recovery_ledger: SQLiteBrowserRecoveryLedger | None = None,
        approval_authority: ApprovalAuthority | None = None,
        owner_principal: Principal | None = None,
        owner_tenant: TenantKey | None = None,
        session_scope: str | None = None,
        owner_session_check: Callable[[], bool] | None = None,
    ) -> None:
        approval_config = (approval_authority, owner_principal, owner_tenant, session_scope, owner_session_check)
        if any(value is not None for value in approval_config) and not all(value is not None for value in approval_config):
            raise TypeError("Owner approval authority, principal, tenant, session and validator must be configured together.")
        if all(value is not None for value in approval_config):
            verified_principal = require_authenticated(owner_principal)
            if not isinstance(owner_tenant, TenantKey) or (
                verified_principal.issuer, verified_principal.subject
            ) != (owner_tenant.issuer, owner_tenant.subject):
                raise BrowserExecutionError("Authenticated Owner identity does not match the browser tenant.")
            if not isinstance(approval_authority, ApprovalAuthority):
                raise TypeError("A trusted ApprovalAuthority is required.")
            if type(session_scope) is not str or not 8 <= len(session_scope) <= 256:
                raise ValueError("A bounded Owner session scope is required.")
            if not callable(owner_session_check):
                raise TypeError("An Owner session validator is required.")
            if type(recovery_ledger) is not SQLiteBrowserRecoveryLedger:
                raise TypeError("Owner-approved browser execution requires a durable recovery/approval-correlation ledger.")
        if worker is not None and not callable(getattr(worker, "run", None)):
            raise TypeError("worker must implement run().")
        if not callable(audit):
            raise TypeError("audit must be callable.")
        self._worker = worker
        self._audit = audit
        if recovery_ledger is not None and not callable(getattr(recovery_ledger, "claim", None)):
            raise TypeError("recovery_ledger must provide durable atomic job claims.")
        self._clock = clock
        self._recovery_ledger = recovery_ledger
        self._approval_authority = approval_authority
        self._owner_principal = owner_principal
        self._owner_tenant = owner_tenant
        self._session_scope = session_scope
        self._owner_session_check = owner_session_check
        self._audit_failed = False
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
        recovery_ledger: SQLiteBrowserRecoveryLedger | None = None,
        approval_authority: ApprovalAuthority | None = None,
        owner_principal: Principal | None = None,
        owner_tenant: TenantKey | None = None,
        session_scope: str | None = None,
        owner_session_check: Callable[[], bool] | None = None,
    ) -> "BrowserExecutionCoordinator":
        """Fail closed until trusted Owner approval is consumed by this execution path.

        The coordinator now verifies and consumes an exact Owner approval and
        persists opaque approval-to-job correlation when a recovery ledger is
        configured. Dispatch nevertheless remains disabled until real-host
        Chromium/FD qualification, Android acceptance and independent security
        review pass. A valid attestation or approval alone is not release approval.
        """
        raise BrowserExecutionError(
            "Browser dispatch is disabled: real-host Chromium/FD qualification, "
            "Android acceptance and independent security review remain outstanding."
        )
        if type(runtime_gate) is not AttestedBrowserRuntime:
            raise TypeError("A concrete AttestedBrowserRuntime gate is required.")
        if type(recovery_ledger) is not SQLiteBrowserRecoveryLedger:
            raise TypeError("Production browser dispatch requires a durable SQLite recovery ledger.")
        if (
            not isinstance(approval_authority, ApprovalAuthority)
            or not isinstance(owner_principal, Principal)
            or not isinstance(owner_tenant, TenantKey)
            or type(session_scope) is not str
            or not callable(owner_session_check)
        ):
            raise BrowserExecutionError("Production browser dispatch requires the complete trusted Owner approval boundary.")
        # This factory is a process-start boundary. Interrupted jobs are made
        # terminal and retained for owner review; they are never auto-replayed.
        interrupted = recovery_ledger.recover_interrupted()
        if interrupted:
            recovery_ledger.latch_dispatch_block("interrupted_jobs_require_owner_review")
            raise BrowserExecutionError(
                "Interrupted browser jobs require verified orphan cleanup and Owner review; dispatch remains blocked."
            )
        worker = runtime_gate.launch(signed_evidence, challenge=challenge, now=now)
        if not callable(getattr(worker, "run", None)) or not callable(getattr(worker, "terminate", None)):
            raise BrowserExecutionError("Attested runtime returned an invalid worker handle.")
        return cls(
            worker, audit=audit, clock=clock, recovery_ledger=recovery_ledger,
            approval_authority=approval_authority, owner_principal=owner_principal,
            owner_tenant=owner_tenant, session_scope=session_scope,
            owner_session_check=owner_session_check,
        )

    def _require_owner_session(self) -> None:
        self._require_owner_session()

    def _consume_owner_approval(self, job: BrowserJob, receipt: ApprovalReceipt | None) -> tuple[str, str, str]:
        """Re-check Owner identity/session and consume the exact one-time job receipt."""
        if (self._approval_authority is None or self._owner_principal is None or
                self._owner_tenant is None or self._session_scope is None or
                self._owner_session_check is None):
            raise BrowserExecutionError("Trusted Owner approval boundary is not configured; dispatch is blocked.")
        try:
            principal = require_authenticated(self._owner_principal)
            if (principal.issuer, principal.subject) != (self._owner_tenant.issuer, self._owner_tenant.subject):
                raise BrowserExecutionError("Owner identity changed; browser dispatch is blocked.")
            if self._owner_session_check() is not True:
                raise BrowserExecutionError("Owner session is inactive or expired; browser dispatch is blocked.")
        except BrowserExecutionError:
            raise
        except Exception as exc:
            raise BrowserExecutionError("Owner session validation failed; browser dispatch is blocked.") from exc
        if not self._approval_authority.consume(
            receipt, "browser_read", _approval_job_payload(job),
            tenant=self._owner_tenant, session_scope=self._session_scope,
        ):
            raise BrowserExecutionError("Owner approval is missing, expired, mismatched or already consumed.")
        if not isinstance(receipt, ApprovalReceipt):
            raise BrowserExecutionError("Consumed Owner approval receipt is malformed.")
        approval_ref = hashlib.sha256((receipt.nonce + "\n" + receipt.signature).encode("utf-8")).hexdigest()
        owner_ref = hashlib.sha256((self._owner_tenant.issuer + "\n" + self._owner_tenant.subject).encode("utf-8")).hexdigest()
        session_ref = hashlib.sha256(self._session_scope.encode("utf-8")).hexdigest()
        return approval_ref, owner_ref, session_ref

    def recover_interrupted_jobs(self) -> list[str]:
        """Explicit process-start recovery; returned jobs require owner review."""
        if self._recovery_ledger is None:
            raise BrowserExecutionError("Durable crash recovery is not configured.")
        try:
            interrupted = self._recovery_ledger.recover_interrupted()
            if interrupted:
                self._recovery_ledger.latch_dispatch_block("interrupted_jobs_require_owner_review")
            return interrupted
        except RecoveryLedgerError as exc:
            self._audit_failed = True
            raise BrowserExecutionError("Crash recovery failed; dispatch is blocked.") from exc

    def _record(self, event: str, *, job_id: str, session_id: str, detail: str) -> None:
        # Never place cookies, page contents, credentials, or URL query values
        # in the audit record. The caller may attach a separate approved digest.
        # Job/session identifiers are opaque correlation handles, but callers
        # may choose a job ID. Persist only one-way references, never raw IDs.
        record = {
            "schema_version": 1,
            "event": event,
            "job_ref": hashlib.sha256(job_id.encode("utf-8")).hexdigest()[:24],
            "session_ref": hashlib.sha256(session_id.encode("utf-8")).hexdigest()[:24],
            "detail": detail,
            "timestamp_unix": time.time(),
        }
        try:
            self._audit(record)
        except Exception as exc:
            self._audit_failed = True
            if self._recovery_ledger is not None:
                try:
                    self._recovery_ledger.latch_dispatch_block("audit_write_failure")
                except Exception:
                    pass
            raise BrowserExecutionError("Audit write failed; browser dispatch is blocked.") from exc

    def cancel(self, job_id: str) -> bool:
        with self._lock:
            active = self._active.get(job_id)
            if active is None:
                return False
            token, session_id, termination_confirmed, completed = active
            if completed.is_set():
                return False
            changed = token.cancel()
        if not changed:
            return False
        # Record cancellation before terminating the worker: otherwise the
        # worker's completion thread can race ahead and write job_cancelled
        # before cancel_requested. Audit failure must not prevent termination.
        audit_error = None
        if self._recovery_ledger is not None:
            try:
                self._recovery_ledger.transition(job_id, "cancel_requested", outcome_code="owner_cancel")
            except RecoveryLedgerError as exc:
                audit_error = exc
                self._audit_failed = True
                try:
                    self._recovery_ledger.latch_dispatch_block("recovery_state_failure")
                except Exception:
                    pass
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
            self._audit_failed = True
            if self._recovery_ledger is not None:
                try:
                    self._recovery_ledger.latch_dispatch_block("worker_termination_unconfirmed")
                except Exception:
                    pass
            try:
                self._record("worker_terminate_error", job_id=job_id, session_id=session_id, detail="adapter_error")
            except Exception as exc:
                if audit_error is None:
                    audit_error = exc
        if termination_error is not None:
            raise BrowserExecutionError("Worker termination failed; job remains cancelled.") from termination_error
        if audit_error is not None:
            raise BrowserExecutionError("Cancellation audit write failed or recovery state could not be persisted after worker termination.") from audit_error
        return changed

    def execute(
        self,
        raw_job: object,
        *,
        resolver: Callable[[str], list[str]],
        approval_receipt: ApprovalReceipt | None = None,
    ) -> Mapping[str, Any]:
        if self._audit_failed:
            raise BrowserExecutionError("Audit integrity previously failed; browser dispatch remains blocked.")
        if self._recovery_ledger is not None:
            try:
                if self._recovery_ledger.dispatch_blocked():
                    raise BrowserDispatchBlocked("durable dispatch block is active")
            except BrowserDispatchBlocked as exc:
                raise BrowserExecutionError("Browser dispatch is blocked by the durable audit/recovery latch.") from exc
            except RecoveryLedgerError as exc:
                self._audit_failed = True
                raise BrowserExecutionError("Recovery/audit state unavailable; dispatch refused.") from exc
        if self._worker is None:
            raise BrowserExecutionError("No attested isolated worker adapter is configured; execution is disabled.")
        if self._worker is None:
            raise BrowserExecutionError("No attested isolated worker adapter is configured; execution is disabled.")
        # Consume Owner approval before DNS resolution or any browser-side operation.
        try:
            job = validate_browser_job(raw_job)
            approval_refs = self._consume_owner_approval(job, approval_receipt)
        except (BrowserPolicyError, TypeError, ValueError) as exc:
            raise BrowserExecutionError("Browser job or Owner approval failed validation.") from exc
        try:
            target, pinned = resolve_pinned_destination(job.url, resolver=resolver)
        except (BrowserPolicyError, TypeError, ValueError, OSError) as exc:
            raise BrowserExecutionError("Browser job failed live DNS/IP pin validation.") from exc

        session_id = uuid.uuid4().hex
        ledger_state: str | None = None
        if self._recovery_ledger is not None:
            try:
                request_bytes = json.dumps(
                    asdict(job), sort_keys=True, ensure_ascii=False,
                    separators=(",", ":"), allow_nan=False,
                ).encode("utf-8")
                request_digest = hashlib.sha256(request_bytes).hexdigest()
                self._recovery_ledger.claim(job.job_id, request_digest, session_id=session_id)
                ledger_state = "accepted"
                self._recovery_ledger.record_approval_correlation(
                    job.job_id, approval_ref=approval_refs[0], owner_ref=approval_refs[1],
                    session_ref=approval_refs[2], request_digest=request_digest,
                )
            except (RecoveryLedgerError, TypeError, ValueError) as exc:
                if ledger_state == "accepted":
                    try:
                        self._recovery_ledger.transition(job.job_id, "failed", outcome_code="approval_correlation_failure")
                        self._recovery_ledger.latch_dispatch_block("approval_correlation_failure")
                    except Exception:
                        pass
                raise BrowserExecutionError("Browser job claim or approval correlation failed; dispatch is blocked.") from exc
        token = CancellationToken()
        termination_confirmed = threading.Event()
        completed = threading.Event()
        outcome: dict[str, Any] = {}
        deadline = self._clock() + job.max_runtime_seconds
        cleanup_mode: str | None = None
        try:
            self._record("approval_consumed", job_id=job.job_id, session_id=session_id, detail="owner_job_session_bound")
            self._record("job_accepted", job_id=job.job_id, session_id=session_id, detail="policy_validated")
            if self._recovery_ledger is not None:
                self._recovery_ledger.transition(job.job_id, "running")
                ledger_state = "running"
            token.raise_if_cancelled()
            def invoke_worker() -> None:
                try:
                    self._require_owner_session()
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
                    self._audit_failed = True
                    if self._recovery_ledger is not None and ledger_state in {"accepted", "running", "cancel_requested"}:
                        try:
                            self._recovery_ledger.transition(
                                job.job_id, "interrupted", outcome_code="timeout_cleanup_unconfirmed"
                            )
                            ledger_state = "interrupted"
                        except RecoveryLedgerError:
                            pass
                        try:
                            self._recovery_ledger.latch_dispatch_block("worker_termination_unconfirmed")
                        except Exception:
                            pass
                    self._record("worker_terminate_error", job_id=job.job_id, session_id=session_id, detail="timeout_termination_error")
                    raise BrowserExecutionError("Timed-out browser worker could not be terminated.") from exc
                if self._recovery_ledger is not None:
                    self._recovery_ledger.transition(job.job_id, "timed_out", outcome_code="hard_deadline")
                    ledger_state = "timed_out"
                self._record("job_timed_out", job_id=job.job_id, session_id=session_id, detail="hard_deadline")
                raise BrowserTimeout("Browser job exceeded its hard runtime deadline.")
            token.raise_if_cancelled()
            if "error" in outcome:
                raise outcome["error"]
            result = outcome.get("result")
            cleanup_mode = "browser_context_destroyed"  # run() returned after context/profile teardown.
            if self._clock() > deadline:
                if self._recovery_ledger is not None:
                    self._recovery_ledger.transition(job.job_id, "timed_out", outcome_code="hard_deadline")
                    ledger_state = "timed_out"
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
            if self._recovery_ledger is not None:
                self._recovery_ledger.transition(job.job_id, "completed", outcome_code="success")
                ledger_state = "completed"
            self._record("job_completed", job_id=job.job_id, session_id=session_id, detail="success")
            return result_dict
        except BrowserCancelled:
            cancellation_confirmed = termination_confirmed.is_set() and completed.is_set()
            if self._recovery_ledger is not None and ledger_state in {"accepted", "running", "cancel_requested"}:
                try:
                    terminal_state = "cancelled" if cancellation_confirmed else "interrupted"
                    outcome_code = "owner_cancel" if cancellation_confirmed else "cancel_cleanup_unconfirmed"
                    self._recovery_ledger.transition(job.job_id, terminal_state, outcome_code=outcome_code)
                    ledger_state = terminal_state
                except RecoveryLedgerError:
                    self._audit_failed = True
                    try:
                        self._recovery_ledger.latch_dispatch_block("recovery_state_failure")
                    except Exception:
                        pass
            if not cancellation_confirmed:
                self._audit_failed = True
                if self._recovery_ledger is not None:
                    try:
                        self._recovery_ledger.latch_dispatch_block("worker_termination_unconfirmed")
                    except Exception:
                        pass
            self._record(
                "job_cancelled" if cancellation_confirmed else "job_cancel_unconfirmed",
                job_id=job.job_id, session_id=session_id,
                detail="cancelled" if cancellation_confirmed else "termination_unconfirmed",
            )
            raise
        except BrowserTimeout:
            raise
        except Exception:
            if self._recovery_ledger is not None and ledger_state in {"accepted", "running", "cancel_requested"}:
                try:
                    self._recovery_ledger.transition(job.job_id, "failed", outcome_code="execution_error")
                    ledger_state = "failed"
                except RecoveryLedgerError:
                    self._audit_failed = True
                    try:
                        self._recovery_ledger.latch_dispatch_block("recovery_state_failure")
                    except Exception:
                        pass
            self._record("job_failed", job_id=job.job_id, session_id=session_id, detail="execution_error")
            raise
        finally:
            with self._lock:
                self._active.pop(job.job_id, None)
            if termination_confirmed.is_set() and completed.is_set():
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
