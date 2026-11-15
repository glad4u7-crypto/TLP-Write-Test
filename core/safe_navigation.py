"""Fail-closed Playwright navigation controller.

Context-level routing is preferred because it observes requests from every page
in the context. This remains a browser request policy layer, not a network
sandbox: WebSockets, browser/OS background traffic and traffic outside Playwright
routing still require a separately enforced network egress boundary.
"""
from __future__ import annotations

from typing import Any

from core.browser_navigation import NavigationPolicy, NavigationPolicyError


class SafeNavigationError(RuntimeError):
    """Raised when navigation is blocked or cannot be completed safely."""


class SafeNavigationController:
    """Navigate with context-wide routing when a BrowserContext is supplied.

    Pass both context and page to enable context-level interception. Supplying
    only page preserves the earlier page-scoped behavior for compatibility;
    that narrower mode must not be treated as context-wide protection.
    """

    def __init__(self, page: Any, policy: NavigationPolicy, *, context: Any | None = None) -> None:
        if page is None:
            raise TypeError("page is required.")
        if not isinstance(policy, NavigationPolicy):
            raise TypeError("policy must be a NavigationPolicy.")
        if context is not None and not callable(getattr(context, "route", None)):
            raise TypeError("context must provide a route method.")
        self._page = page
        self._context = context
        self._router = context if context is not None else page
        self._policy = policy
        self._navigating = False

    @property
    def context_wide(self) -> bool:
        """Whether routing is installed on the entire BrowserContext."""
        return self._context is not None

    def navigate(self, url: str, *, timeout_ms: int = 15_000) -> Any:
        """Navigate after installing a temporary request policy route."""
        if self._navigating:
            raise SafeNavigationError("Concurrent navigation is not supported.")
        if type(timeout_ms) is not int or not 1_000 <= timeout_ms <= 60_000:
            raise ValueError("timeout_ms must be an integer from 1000 to 60000.")
        self._policy.validate_url(url)
        self._navigating = True
        blocked: list[NavigationPolicyError] = []

        def guard(route: Any) -> None:
            try:
                self._policy.validate_url(route.request.url)
            except NavigationPolicyError as exc:
                blocked.append(exc)
                route.abort(error_code="blockedbyclient")
                return
            route.continue_()

        installed = False
        try:
            self._router.route("**/*", guard)
            installed = True
            response = self._page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            if blocked:
                raise SafeNavigationError("A request or redirect was blocked by navigation policy.") from blocked[0]
            return response
        except SafeNavigationError:
            raise
        except Exception as exc:
            if blocked:
                raise SafeNavigationError("A request or redirect was blocked by navigation policy.") from blocked[0]
            raise SafeNavigationError("Browser navigation failed.") from exc
        finally:
            try:
                if installed:
                    self._router.unroute("**/*", guard)
            finally:
                self._navigating = False
