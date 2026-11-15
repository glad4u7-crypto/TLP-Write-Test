import pytest

from core.browser_launch import (
    BrowserLaunchError,
    BrowserLaunchPolicy,
    PlaywrightBrowserLauncher,
)


class FakePage:
    pass


class FakeContext:
    def __init__(self):
        self.closed = False
        self.page = FakePage()
        self.options = None

    def new_page(self):
        return self.page

    def close(self):
        self.closed = True


class FakeBrowser:
    def __init__(self):
        self.closed = False
        self.context = FakeContext()
        self.context_options = None
        self.launch_options = None

    def new_context(self, **kwargs):
        self.context_options = kwargs
        return self.context

    def close(self):
        self.closed = True


class FakeChromium:
    def __init__(self, browser):
        self.browser = browser
        self.options = None

    def launch(self, **kwargs):
        self.options = kwargs
        return self.browser


class FakePlaywright:
    def __init__(self, browser):
        self.chromium = FakeChromium(browser)


class FakeManager:
    def __init__(self, playwright):
        self.playwright = playwright
        self.stopped = False
        self.started = False

    def start(self):
        self.started = True
        return self.playwright

    def stop(self):
        self.stopped = True


def make_launcher():
    browser = FakeBrowser()
    playwright = FakePlaywright(browser)
    manager = FakeManager(playwright)
    launcher = PlaywrightBrowserLauncher(
        BrowserLaunchPolicy(),
        playwright_factory=lambda: manager,
    )
    return launcher, manager, browser, playwright


def test_policy_rejects_unsafe_types_and_unbounded_timeout():
    with pytest.raises(TypeError):
        BrowserLaunchPolicy(headless=1)
    with pytest.raises(TypeError):
        BrowserLaunchPolicy(launch_timeout_ms=True)
    with pytest.raises(ValueError):
        BrowserLaunchPolicy(launch_timeout_ms=999)
    with pytest.raises(ValueError):
        BrowserLaunchPolicy(launch_timeout_ms=60_001)


def test_launch_uses_headless_browser_and_fresh_non_download_context():
    launcher, manager, browser, playwright = make_launcher()

    session = launcher.launch()

    assert manager.started is True
    assert playwright.chromium.options == {"headless": True, "timeout": 15_000}
    assert browser.context_options == {"accept_downloads": False}
    assert session.page is browser.context.page
    assert session.closed is False


def test_session_close_is_idempotent_and_closes_all_owned_resources():
    launcher, manager, browser, _ = make_launcher()
    session = launcher.launch()

    session.close()
    session.close()

    assert session.closed is True
    assert browser.context.closed is True
    assert browser.closed is True
    assert manager.stopped is True
    with pytest.raises(BrowserLaunchError, match="closed"):
        _ = session.page


def test_context_manager_closes_session():
    launcher, manager, browser, _ = make_launcher()

    with launcher.launch() as session:
        assert session.page is browser.context.page

    assert session.closed is True
    assert manager.stopped is True


def test_launch_failure_cleans_up_started_resources():
    browser = FakeBrowser()
    manager = FakeManager(FakePlaywright(browser))

    class BrokenChromium:
        def launch(self, **kwargs):
            raise RuntimeError("simulated launch failure")

    manager.playwright.chromium = BrokenChromium()
    launcher = PlaywrightBrowserLauncher(playwright_factory=lambda: manager)

    with pytest.raises(BrowserLaunchError, match="launch failed"):
        launcher.launch()

    assert browser.closed is False  # launch failed before a Browser existed
    assert manager.stopped is True


def test_context_creation_failure_closes_browser_and_manager():
    browser = FakeBrowser()

    def broken_context(**kwargs):
        raise RuntimeError("context failure")

    browser.new_context = broken_context
    manager = FakeManager(FakePlaywright(browser))
    launcher = PlaywrightBrowserLauncher(playwright_factory=lambda: manager)

    with pytest.raises(BrowserLaunchError):
        launcher.launch()

    assert browser.closed is True
    assert manager.stopped is True


def test_manager_start_failure_is_reported_and_manager_is_stopped():
    class BrokenManager(FakeManager):
        def start(self):
            raise RuntimeError("startup failure")

    manager = BrokenManager(FakePlaywright(FakeBrowser()))
    launcher = PlaywrightBrowserLauncher(playwright_factory=lambda: manager)

    with pytest.raises(BrowserLaunchError, match="launch failed"):
        launcher.launch()

    assert manager.stopped is True


def test_cleanup_continues_when_one_resource_close_fails():
    launcher, manager, browser, _ = make_launcher()
    session = launcher.launch()

    def broken_context_close():
        raise RuntimeError("context close failure")

    browser.context.close = broken_context_close

    with pytest.raises(BrowserLaunchError, match="cleanup"):
        session.close()

    assert session.closed is True
    assert browser.closed is True
    assert manager.stopped is True
