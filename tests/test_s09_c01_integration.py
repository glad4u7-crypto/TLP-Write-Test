"""Cross-module regression tests for APAA S09 C01.

All DNS is injected and all browser surfaces are fakes. These tests never open
network connections, launch a real browser, or visit a live website.
"""
import pytest

from core.browser_navigation import NavigationPolicy, NavigationPolicyError
from core.egress_policy import (
    EgressAuthorizationError,
    EgressDestinationAuthorizer,
    validate_connector_result,
)
from core.runtime_support import assess_runtime, require_browser_runtime
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

    def continue_(self):
        self.continued = True

    def abort(self, *, error_code=None):
        self.aborted = True


class FakeContext:
    def __init__(self, request_urls=()):
        self.handlers = {}
        self.request_urls = request_urls
        self.seen = []
        self.unrouted = []

    def route(self, pattern, handler):
        self.handlers[pattern] = handler

    def unroute(self, pattern, handler):
        assert self.handlers.get(pattern) is handler
        del self.handlers[pattern]
        self.unrouted.append(pattern)


class FakePage:
    def __init__(self, context, *, fail=False):
        self.context = context
        self.fail = fail

    def goto(self, url, **kwargs):
        handler = self.context.handlers["**/*"]
        for request_url in (url, *self.context.request_urls):
            route = FakeRoute(request_url)
            self.context.seen.append(route)
            handler(route)
            if route.aborted:
                raise RuntimeError("blocked by route")
        if self.fail:
            raise RuntimeError("simulated page failure")
        return {"url": url, "status": 200}


def make_policy(*, hosts=("example.com",), resolver=None):
    return NavigationPolicy(
        allowed_hosts=frozenset(hosts),
        resolver=resolver or (lambda host: (PUBLIC,)),
    )


def test_integration_authorize_destination_then_verify_connector_pin():
    calls = []

    def resolver(host):
        calls.append(host)
        return (PUBLIC,)

    target = EgressDestinationAuthorizer(make_policy(resolver=resolver)).authorize(
        "https://example.com/resource"
    )
    assert target.hostname == "example.com"
    assert target.pinned_addresses == (PUBLIC,)
    assert validate_connector_result(target, PUBLIC) == PUBLIC
    assert calls == ["example.com"]


def test_integration_connector_cannot_escape_authorized_ip_set():
    target = EgressDestinationAuthorizer(make_policy()).authorize(
        "https://example.com/"
    )
    with pytest.raises(EgressAuthorizationError, match="escaped"):
        validate_connector_result(target, "1.1.1.1")


def test_integration_context_route_blocks_disallowed_subresource_and_cleans_up():
    context = FakeContext(request_urls=("https://evil.test/tracker.js",))
    page = FakePage(context)
    controller = SafeNavigationController(page, make_policy(), context=context)

    with pytest.raises(SafeNavigationError, match="blocked"):
        controller.navigate("https://example.com/")

    assert context.seen[0].continued is True
    assert context.seen[1].aborted is True
    assert context.handlers == {}
    assert context.unrouted == ["**/*"]


def test_integration_context_route_is_removed_after_browser_failure():
    context = FakeContext()
    page = FakePage(context, fail=True)
    controller = SafeNavigationController(page, make_policy(), context=context)

    with pytest.raises(SafeNavigationError, match="failed"):
        controller.navigate("https://example.com/")

    assert context.handlers == {}
    assert context.unrouted == ["**/*"]


def test_integration_initial_allowlist_failure_happens_before_route_install():
    context = FakeContext()
    page = FakePage(context)
    controller = SafeNavigationController(page, make_policy(), context=context)

    with pytest.raises(NavigationPolicyError):
        controller.navigate("https://untrusted.invalid/")

    assert context.handlers == {}
    assert context.seen == []


def test_integration_android_runtime_denies_browser_capability():
    result = assess_runtime(
        platform="linux",
        environ={
            "ANDROID_ROOT": "/system",
            "PREFIX": "/data/data/com.termux/files/usr",
            "HOME": "/data/data/com.termux/files/home",
        },
    )
    assert result.is_android and result.is_termux
    assert result.browser_launch_allowed is False
    with pytest.raises(RuntimeError, match="Termux"):
        require_browser_runtime(
            environ={
                "ANDROID_ROOT": "/system",
                "PREFIX": "/data/data/com.termux/files/usr",
            }
        )


def test_integration_non_android_runtime_is_not_claimed_as_fully_qualified():
    result = assess_runtime(platform="linux", environ={"HOME": "/home/test"})
    assert result.browser_launch_allowed is True
    assert "require local validation" in result.reason
