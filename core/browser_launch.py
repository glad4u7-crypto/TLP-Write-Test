"""Fail-closed, ephemeral Playwright browser launch boundary.

P01 launches a local Chromium process only. It deliberately exposes no URL
navigation, page interaction, download, persistent-profile, remote-debugging,
or arbitrary launch-argument API. Playwright remains an optional dependency.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from core.runtime_support import require_browser_runtime


MIN_LAUNCH_TIMEOUT_MS = 1_000
MAX_LAUNCH_TIMEOUT_MS = 60_000


class BrowserLaunchError(RuntimeError):
    """Raised when a browser cannot be launched safely."""


@dataclass(frozen=True)
class BrowserLaunchPolicy:
    """Small allowlisted launch policy; unsafe knobs are not configurable."""

    headless: bool = True
    launch_timeout_ms: int = 15_000

    def __post_init__(self) -> None:
        if type(self.headless) is not bool:
            raise TypeError("headless must be a boolean.")
        if type(self.launch_timeout_ms) is not int:
            raise TypeError("launch_timeout_ms must be an integer.")
        if not MIN_LAUNCH_TIMEOUT_MS <= self.launch_timeout_ms <= MAX_LAUNCH_TIMEOUT_MS:
            raise ValueError(
                f"launch_timeout_ms must be between {MIN_LAUNCH_TIMEOUT_MS} "
                f"and {MAX_LAUNCH_TIMEOUT_MS}."
            )


class BrowserSession:
    """Owns one isolated browser context and closes resources deterministically."""

    def __init__(self, browser: Any, context: Any, page: Any, manager: Any) -> None:
        self._browser = browser
        self._context = context
        self._page = page
        self._manager = manager
        self._closed = False

    @property
    def context(self) -> Any:
        if self._closed:
            raise BrowserLaunchError("Browser session is closed.")
        return self._context

    @property
    def page(self) -> Any:
        if self._closed:
            raise BrowserLaunchError("Browser session is closed.")
        return self._page

    @property
    def closed(self) -> bool:
        return self._closed

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        errors: list[Exception] = []
        for resource, method in (
            (self._context, "close"),
            (self._browser, "close"),
            (self._manager, "stop"),
        ):
            try:
                getattr(resource, method)()
            except Exception as exc:  # cleanup must continue for later resources
                errors.append(exc)
        if errors:
            raise BrowserLaunchError(
                f"Browser cleanup encountered {len(errors)} error(s)."
            ) from errors[0]

    def __enter__(self) -> "BrowserSession":
        if self._closed:
            raise BrowserLaunchError("Browser session is closed.")
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.close()


class PlaywrightBrowserLauncher:
    """Launch bundled local Chromium with an isolated, non-persistent context.

    The optional Playwright package and its browser binary must be installed
    separately by the operator. This class never installs packages or browsers.
    """

    def __init__(
        self,
        policy: BrowserLaunchPolicy | None = None,
        *,
        playwright_factory: Callable[[], Any] | None = None,
    ) -> None:
        self.policy = policy or BrowserLaunchPolicy()
        self._playwright_factory = playwright_factory

    def launch(self) -> BrowserSession:
        try:
            require_browser_runtime()
        except RuntimeError as exc:
            raise BrowserLaunchError(str(exc)) from exc

        factory = self._playwright_factory
        if factory is None:
            try:
                from playwright.sync_api import sync_playwright
            except ImportError as exc:
                raise BrowserLaunchError(
                    "Playwright is optional and is not installed. Install and "
                    "provision it manually before requesting browser launch."
                ) from exc
            factory = sync_playwright

        manager = None
        browser = None
        context = None
        try:
            manager = factory()
            playwright = manager.start()
            browser = playwright.chromium.launch(
                headless=self.policy.headless,
                timeout=self.policy.launch_timeout_ms,
            )
            # A fresh incognito-like context: no user profile or stored cookies.
            context = browser.new_context(accept_downloads=False, service_workers="block")
            page = context.new_page()
            return BrowserSession(browser, context, page, manager)
        except Exception as exc:
            for resource, method in (
                (context, "close"),
                (browser, "close"),
                (manager, "stop"),
            ):
                if resource is not None:
                    try:
                        getattr(resource, method)()
                    except Exception:
                        pass
            if isinstance(exc, BrowserLaunchError):
                raise
            raise BrowserLaunchError("Safe browser launch failed.") from exc
