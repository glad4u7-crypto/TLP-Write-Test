"""Owner-authenticated, approval-gated boundary for future browser control.

This module deliberately registers no browser handler and performs no browser,
network, DNS, process, or filesystem operation. It connects the existing
Personal Runtime Owner identity, durable ApprovalAuthority, and Action Audit
to a bounded browser-job contract while keeping dispatch fail-closed.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import asdict
import time
from typing import Any

from core.approvals import ApprovalAuthority, ApprovalReceipt
from core.audit import JsonlAuditLog
from core.browser_security import BrowserJob, validate_browser_job
from core.execution import ActionHandlerDisabled, ExecutionGateway, ExecutionResult
from core.identity import Principal, require_authenticated
from core.storage import TenantKey


BROWSER_APPROVAL_ACTION = "browser_read"
BROWSER_APPROVAL_TTL_SECONDS = 60


class BrowserControlSecurityError(PermissionError):
    """Raised when Owner/session/approval requirements are not satisfied."""


def _job_payload(job: BrowserJob) -> dict[str, Any]:
    value = asdict(job)
    value["allowed_origins"] = list(job.allowed_origins)
    return value


class BrowserControlBoundary:
    """A private Owner/session-bound browser approval and audit boundary.

    owner_verified must be supplied only by the trusted app controller after
    its local Owner login or configured global-Owner check succeeds.
    owner_session_check is re-evaluated on every request and dispatch.
    """

    BROWSER_HANDLER_ENABLED = False

    def __init__(
        self,
        *,
        owner_principal: Principal,
        owner_tenant: TenantKey,
        owner_verified: bool,
        session_scope: str,
        approval_authority: ApprovalAuthority,
        audit_log: JsonlAuditLog,
        owner_session_check: Callable[[], bool],
    ) -> None:
        principal = require_authenticated(owner_principal)
        if not isinstance(owner_tenant, TenantKey):
            raise TypeError("A validated Owner tenant is required.")
        if (principal.issuer, principal.subject) != (
            owner_tenant.issuer, owner_tenant.subject
        ):
            raise BrowserControlSecurityError(
                "Authenticated Owner identity does not match the runtime tenant."
            )
        if owner_verified is not True:
            raise BrowserControlSecurityError(
                "The trusted app controller has not verified Owner authority."
            )
        if not isinstance(session_scope, str) or len(session_scope) < 8 or len(session_scope) > 256:
            raise ValueError("A fresh bounded Owner session scope is required.")
        if not isinstance(approval_authority, ApprovalAuthority):
            raise TypeError("A trusted ApprovalAuthority is required.")
        if not callable(getattr(audit_log, "append", None)) or not callable(
            getattr(audit_log, "verify", None)
        ):
            raise TypeError("A durable Action Audit adapter is required.")
        if not callable(owner_session_check):
            raise TypeError("An Owner session validator is required.")

        self._principal = principal
        self._tenant = owner_tenant
        self._session_scope = session_scope
        self._approval_authority = approval_authority
        self._audit_log = audit_log
        self._owner_session_check = owner_session_check
        # Register an explicit disabled handler to provide a clear, audited stop.
        self._gateway = ExecutionGateway(
            {BROWSER_APPROVAL_ACTION: self._browser_handler_disabled},
            approval_authority=approval_authority,
            audit_log=audit_log,
            session_scope=session_scope,
        )

    @property
    def browser_handler_enabled(self) -> bool:
        """Always false in BCS-01; no enable switch exists in this boundary."""
        return self.BROWSER_HANDLER_ENABLED

    @property
    def browser_handler_registered(self) -> bool:
        """True: a guarded handler is registered with an explicit disabled outcome."""
        return True

    @staticmethod
    def _browser_handler_disabled(_payload: Mapping[str, Any]) -> None:
        """Fail closed before any browser, network, process, or filesystem side effect."""
        raise ActionHandlerDisabled(
            "Browser handler is registered but DISABLED: a reviewed host adapter "
            "and verified isolated-worker egress evidence are not configured."
        )

    def _require_active_owner(self) -> None:
        require_authenticated(self._principal)
        try:
            active = self._owner_session_check()
        except Exception as exc:
            raise BrowserControlSecurityError(
                "Owner session validation failed; browser control is blocked."
            ) from exc
        if active is not True:
            raise BrowserControlSecurityError(
                "Owner session is inactive or expired; browser control is blocked."
            )

    def request_approval(
        self,
        raw_job: Mapping[str, Any],
        *,
        owner_confirmed: bool,
        now: int | None = None,
    ) -> ApprovalReceipt:
        """Issue a short-lived receipt only after an explicit Owner confirmation."""
        self._require_active_owner()
        if owner_confirmed is not True:
            raise BrowserControlSecurityError(
                "A fresh explicit Owner confirmation is required."
            )
        current = int(time.time()) if now is None else now
        if type(current) is not int or current < 0:
            raise ValueError("Browser approval time is invalid.")
        job = validate_browser_job(raw_job, now=current)
        remaining = job.expires_at - current
        ttl = min(BROWSER_APPROVAL_TTL_SECONDS, remaining)
        if ttl < 1:
            raise BrowserControlSecurityError("Browser job has expired.")
        return self._approval_authority.issue(
            BROWSER_APPROVAL_ACTION,
            _job_payload(job),
            ttl_seconds=ttl,
            tenant=self._tenant,
            session_scope=self._session_scope,
        )

    def dispatch(
        self,
        raw_job: Mapping[str, Any],
        *,
        approval_receipt: ApprovalReceipt | None,
        now: int | None = None,
    ) -> ExecutionResult:
        """Consume the exact Owner receipt and audit a blocked disabled-handler dispatch.

        A guarded handler is registered, but it raises ActionHandlerDisabled
        before any side effect. A valid receipt is consumed once and the gateway
        records a denied disabled outcome. This is not browser execution.
        """
        self._require_active_owner()
        current = int(time.time()) if now is None else now
        if type(current) is not int or current < 0:
            raise ValueError("Browser dispatch time is invalid.")
        job = validate_browser_job(raw_job, now=current)
        return self._gateway.execute(
            BROWSER_APPROVAL_ACTION,
            _job_payload(job),
            approval_receipt=approval_receipt,
            tenant=self._tenant,
        )
