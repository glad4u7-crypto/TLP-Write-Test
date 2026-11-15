"""Fail-closed Playwright navigation controller.

The controller applies NavigationPolicy to the initial URL and every routed
request (including redirect hops) before allowing the browser request to
continue. It is a policy enforcement layer, not a network sandbox: DNS
rebinding and browser/OS traffic outside this page route remain out of scope.
"""
from __future__ import annotations

from typing import Any

from core.browser_navigation import NavigationPolicy, NavigationPolicyError


class SafeNavigationError(RuntimeError):
    """Raised when navigation is blocked or cannot be completed safely."""


class SafeNavigationController:
    """Navigate one page while validating every request observed by Playwright."""

    def __init__(self, page: Any, policy: NavigationPolicy) -> None:
        if page is None:
            raise TypeError("page is required.")
        if not isinstance(policy, NavigationPolicy):
            raise TypeError("policy must be a NavigationPolicy.")
        self._page = page
        self._policy = policy
        self._navigating = False

    def navigate(self, url: str, *, timeout_ms: int = 15_000) -> Any:
        """Navigate after installing a temporary all-request policy route."""
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
            self._page.route("**/*", guard)
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
                    self._page.unroute("**/*", guard)
            finally:
                self._navigating = False
