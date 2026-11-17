"""Fail-closed Playwright navigation controller.

Context-level routing can be installed for the full BrowserContext lifetime.
This is a request-layer control, not a substitute for an OS/container egress
firewall: browser-process traffic outside Playwright remains out of scope.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from core.browser_navigation import NavigationPolicy, NavigationPolicyError


class SafeNavigationError(RuntimeError):
    """Raised when navigation is blocked or cannot be completed safely."""


RequestValidator = Callable[[Any], None]


class SafeNavigationController:
    """Validate every routed request, redirect and subresource.

    install() enables persistent context-wide routing. Without it,
    navigate() retains the legacy temporary-route behavior.
    """

    def __init__(
        self,
        page: Any,
        policy: NavigationPolicy,
        *,
        context: Any | None = None,
        request_validator: RequestValidator | None = None,
    ) -> None:
        if page is None:
            raise TypeError("page is required.")
        if not isinstance(policy, NavigationPolicy):
            raise TypeError("policy must be a NavigationPolicy.")
        if context is not None and not callable(getattr(context, "route", None)):
            raise TypeError("context must provide a route method.")
        if request_validator is not None and not callable(request_validator):
            raise TypeError("request_validator must be callable.")
        self._page = page
        self._context = context
        self._router = context if context is not None else page
        self._policy = policy
        self._request_validator = request_validator
        self._navigating = False
        self._installed = False

    @property
    def context_wide(self) -> bool:
        return self._context is not None

    @property
    def installed(self) -> bool:
        return self._installed

    def _guard(self, route: Any) -> None:
        try:
            self._policy.validate_url(route.request.url)
            if self._request_validator is not None:
                self._request_validator(route.request)
        except Exception:
            route.abort(error_code="blockedbyclient")
        else:
            route.continue_()

    def install(self) -> None:
        """Install a persistent route covering all pages in the context."""
        if self._installed:
            return
        if not self.context_wide:
            raise SafeNavigationError("Persistent routing requires a BrowserContext.")
        try:
            self._router.route("**/*", self._guard)
        except Exception as exc:
            raise SafeNavigationError("Could not install persistent request policy.") from exc
        self._installed = True

    def close(self) -> None:
        """Remove the persistent route; safe to call more than once."""
        if not self._installed:
            return
        try:
            self._router.unroute("**/*", self._guard)
        except Exception as exc:
            raise SafeNavigationError("Could not remove persistent request policy.") from exc
        finally:
            self._installed = False

    def navigate(self, url: str, *, timeout_ms: int = 15_000) -> Any:
        if self._navigating:
            raise SafeNavigationError("Concurrent navigation is not supported.")
        if type(timeout_ms) is not int or not 1_000 <= timeout_ms <= 60_000:
            raise ValueError("timeout_ms must be an integer from 1000 to 60000.")
        self._policy.validate_url(url)
        self._navigating = True
        blocked: list[Exception] = []
        persistent = self._installed

        def temporary_guard(route: Any) -> None:
            try:
                self._policy.validate_url(route.request.url)
                if self._request_validator is not None:
                    self._request_validator(route.request)
            except Exception as exc:
                blocked.append(exc)
                route.abort(error_code="blockedbyclient")
                return
            route.continue_()

        installed_here = False
        try:
            if not persistent:
                self._router.route("**/*", temporary_guard)
                installed_here = True
            response = self._page.goto(
                url, wait_until="domcontentloaded", timeout=timeout_ms
            )
            if blocked:
                raise SafeNavigationError(
                    "A request or redirect was blocked by navigation policy."
                ) from blocked[0]
            return response
        except SafeNavigationError:
            raise
        except Exception as exc:
            if blocked:
                raise SafeNavigationError(
                    "A request or redirect was blocked by navigation policy."
                ) from blocked[0]
            raise SafeNavigationError("Browser navigation failed.") from exc
        finally:
            try:
                if installed_here:
                    self._router.unroute("**/*", temporary_guard)
            finally:
                self._navigating = False
