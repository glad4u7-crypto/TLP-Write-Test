"""Fail-closed, read-only browser adapter for APAA Personal Edition.

This adapter is defense in depth inside Playwright. It requires a separately
trusted egress_guard for every HTTP request and does not claim to constrain
browser/OS traffic that bypasses Playwright. Browser dispatch remains disabled
until a real host adapter and network egress boundary are independently proven.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from core.browser_launch import BrowserSession, PlaywrightBrowserLauncher
from core.browser_navigation import NavigationPolicy, NavigationPolicyError
from core.safe_navigation import SafeNavigationController


EgressGuard = Callable[[str, str], bool]
_ALLOWED_METHODS = frozenset({"GET", "HEAD"})
_ALLOWED_RESOURCE_TYPES = frozenset({
    "document", "stylesheet", "image", "font", "script", "xhr", "fetch", "manifest",
})


class SecureBrowserAdapterError(RuntimeError):
    """Raised when the secure browser adapter cannot uphold its policy."""


class SecureBrowserAdapter:
    """One-job browser session with fresh context and default-deny traffic.

    An egress_guard is mandatory and must be backed by a trusted network
    boundary, not merely a second DNS lookup. It is called for every routed
    HTTP request and must return the literal boolean True.
    """

    def __init__(
        self,
        *,
        policy: NavigationPolicy,
        egress_guard: EgressGuard,
        launcher: PlaywrightBrowserLauncher | None = None,
        allowed_resource_types: frozenset[str] = _ALLOWED_RESOURCE_TYPES,
    ) -> None:
        if not isinstance(policy, NavigationPolicy):
            raise TypeError("policy must be a NavigationPolicy.")
        if not callable(egress_guard):
            raise TypeError("A trusted egress_guard is mandatory.")
        if not isinstance(allowed_resource_types, frozenset) or not allowed_resource_types:
            raise TypeError("allowed_resource_types must be a non-empty frozenset.")
        if not allowed_resource_types <= _ALLOWED_RESOURCE_TYPES:
            raise ValueError("Unknown browser resource type.")
        self._policy = policy
        self._egress_guard = egress_guard
        self._launcher = launcher or PlaywrightBrowserLauncher()
        self._allowed_resource_types = allowed_resource_types
        self._session: BrowserSession | None = None
        self._navigation: SafeNavigationController | None = None
        self._started = False

    @property
    def started(self) -> bool:
        return self._started

    def _validate_request(self, request: Any) -> None:
        method = getattr(request, "method", None)
        if not isinstance(method, str) or method.upper() not in _ALLOWED_METHODS:
            raise NavigationPolicyError("Only GET and HEAD requests are permitted.")
        if getattr(request, "post_data", None) is not None:
            raise NavigationPolicyError("Request bodies and uploads are prohibited.")
        resource_type = getattr(request, "resource_type", None)
        if resource_type not in self._allowed_resource_types:
            raise NavigationPolicyError("Background or unsupported resource type is blocked.")
        headers = getattr(request, "headers", {}) or {}
        content_type = str(headers.get("content-type", "")).lower()
        if "multipart/form-data" in content_type:
            raise NavigationPolicyError("Multipart upload requests are prohibited.")
        try:
            authorized = self._egress_guard(request.url, method.upper())
        except Exception as exc:
            raise NavigationPolicyError("Trusted egress authorization failed.") from exc
        if authorized is not True:
            raise NavigationPolicyError("Trusted egress boundary denied the request.")

    @staticmethod
    def _block_websocket(websocket_route: Any) -> None:
        try:
            websocket_route.close(code=1008, reason="WebSocket traffic is disabled by APAA policy")
        except Exception as exc:
            raise SecureBrowserAdapterError("Could not block WebSocket traffic.") from exc

    @staticmethod
    def _clear_file_selection(file_chooser: Any) -> None:
        # Empty selection prevents page scripts receiving a local file handle.
        try:
            file_chooser.set_files([])
        except Exception as exc:
            raise SecureBrowserAdapterError("Could not reject file selection.") from exc

    def _attach_page(self, page: Any) -> None:
        """Apply upload prevention to every page and popup in the context."""
        try:
            page.on("filechooser", self._clear_file_selection)
        except Exception as exc:
            raise SecureBrowserAdapterError("Could not enforce file chooser policy.") from exc

    def start(self) -> None:
        if self._started:
            raise SecureBrowserAdapterError("Adapter is already started.")
        session = self._launcher.launch()
        try:
            context = session.context
            page = session.page
            if not callable(getattr(context, "route_web_socket", None)):
                raise SecureBrowserAdapterError(
                    "Browser runtime cannot enforce the required WebSocket-deny policy."
                )
            if not callable(getattr(context, "on", None)):
                raise SecureBrowserAdapterError(
                    "Browser runtime cannot enforce page-wide file chooser policy."
                )
            navigation = SafeNavigationController(
                page,
                self._policy,
                context=context,
                request_validator=self._validate_request,
            )
            navigation.install()
            context.route_web_socket("**/*", self._block_websocket)
            context.on("page", self._attach_page)
            self._attach_page(page)
            self._session = session
            self._navigation = navigation
            self._started = True
        except Exception as exc:
            try:
                session.close()
            except Exception:
                pass
            if isinstance(exc, SecureBrowserAdapterError):
                raise
            raise SecureBrowserAdapterError("Secure browser setup failed closed.") from exc

    def navigate(self, url: str, *, timeout_ms: int = 15_000) -> Any:
        if not self._started or self._navigation is None:
            raise SecureBrowserAdapterError("Adapter is not started.")
        return self._navigation.navigate(url, timeout_ms=timeout_ms)

    def close(self) -> None:
        if not self._started:
            return
        error: Exception | None = None
        try:
            if self._navigation is not None:
                self._navigation.close()
        except Exception as exc:
            error = exc
        try:
            if self._session is not None:
                self._session.close()
        except Exception as exc:
            error = error or exc
        finally:
            self._navigation = None
            self._session = None
            self._started = False
        if error is not None:
            raise SecureBrowserAdapterError("Browser session cleanup failed.") from error

    def __enter__(self) -> "SecureBrowserAdapter":
        self.start()
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.close()
