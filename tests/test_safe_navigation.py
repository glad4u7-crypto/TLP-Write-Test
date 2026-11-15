import pytest

from core.browser_navigation import NavigationPolicy, NavigationPolicyError
from core.safe_navigation import SafeNavigationController, SafeNavigationError


PUBLIC = "93.184.216.34"


class FakeRequest:
    def __init__(self, url):
        self.url = url


class FakeRoute:
    def __init__(self, url):
        self.request = FakeRequest(url)
        self.continued = False
        self.aborted = False
        self.abort_code = None

    def continue_(self):
        self.continued = True

    def abort(self, *, error_code=None):
        self.aborted = True
        self.abort_code = error_code


class FakePage:
    def __init__(self, *, redirect_urls=(), goto_error=None):
        self.handlers = {}
        self.redirect_urls = redirect_urls
        self.goto_error = goto_error
        self.routes_seen = []
        self.goto_options = None
        self.unrouted = []

    def route(self, pattern, handler):
        self.handlers[pattern] = handler

    def unroute(self, pattern, handler):
        assert self.handlers.get(pattern) is handler
        del self.handlers[pattern]
        self.unrouted.append(pattern)

    def goto(self, url, **kwargs):
        self.goto_options = (url, kwargs)
        handler = self.handlers["**/*"]
        for target in (url, *self.redirect_urls):
            route = FakeRoute(target)
            self.routes_seen.append(route)
            handler(route)
            if route.aborted:
                raise RuntimeError("request blocked")
        if self.goto_error:
            raise self.goto_error
        return "response"


def make_policy(*, hosts=("example.com",), resolver=None):
    return NavigationPolicy(
        allowed_hosts=frozenset(hosts),
        resolver=resolver or (lambda host: (PUBLIC,)),
    )


def test_navigate_validates_and_routes_initial_request():
    page = FakePage()
    controller = SafeNavigationController(page, make_policy())

    result = controller.navigate("https://example.com/start")

    assert result == "response"
    assert page.routes_seen[0].continued is True
    assert page.goto_options[1] == {
        "wait_until": "domcontentloaded",
        "timeout": 15_000,
    }
    assert page.handlers == {}
    assert page.unrouted == ["**/*"]


def test_initial_disallowed_url_is_rejected_before_route_installation():
    page = FakePage()
    controller = SafeNavigationController(page, make_policy())

    with pytest.raises(NavigationPolicyError):
        controller.navigate("https://evil.test/")

    assert page.handlers == {}
    assert page.routes_seen == []


def test_redirect_to_disallowed_host_is_aborted_and_reported():
    page = FakePage(redirect_urls=("https://evil.test/landing",))
    controller = SafeNavigationController(page, make_policy())

    with pytest.raises(SafeNavigationError, match="blocked"):
        controller.navigate("https://example.com/start")

    assert page.routes_seen[0].continued is True
    assert page.routes_seen[1].aborted is True
    assert page.routes_seen[1].abort_code == "blockedbyclient"
    assert page.handlers == {}


def test_redirect_to_private_address_is_blocked():
    page = FakePage(redirect_urls=("http://10.0.0.8/admin",))
    controller = SafeNavigationController(page, make_policy())

    with pytest.raises(SafeNavigationError, match="blocked"):
        controller.navigate("https://example.com/start")

    assert page.routes_seen[-1].aborted is True


def test_timeout_bounds_are_enforced_before_navigation():
    page = FakePage()
    controller = SafeNavigationController(page, make_policy())

    with pytest.raises(ValueError):
        controller.navigate("https://example.com/", timeout_ms=999)

    assert page.handlers == {}


def test_browser_failure_still_removes_temporary_route():
    page = FakePage(goto_error=RuntimeError("browser crashed"))
    controller = SafeNavigationController(page, make_policy())

    with pytest.raises(SafeNavigationError, match="failed"):
        controller.navigate("https://example.com/")

    assert page.handlers == {}
    assert page.unrouted == ["**/*"]


def test_invalid_constructor_arguments_are_rejected():
    with pytest.raises(TypeError):
        SafeNavigationController(None, make_policy())
    with pytest.raises(TypeError):
        SafeNavigationController(FakePage(), object())


def test_concurrent_navigation_is_rejected():
    page = FakePage()
    controller = SafeNavigationController(page, make_policy())
    controller._navigating = True

    with pytest.raises(SafeNavigationError, match="Concurrent"):
        controller.navigate("https://example.com/")

    assert page.handlers == {}
