from __future__ import annotations

import pytest

from core.browser_navigation import NavigationPolicy
from core.secure_browser_adapter import (
    SecureBrowserAdapter,
    SecureBrowserAdapterError,
)


PUBLIC = "93.184.216.34"


class Request:
    def __init__(self, url="https://example.com/", method="GET", resource_type="document",
                 post_data=None, headers=None):
        self.url = url
        self.method = method
        self.resource_type = resource_type
        self.post_data = post_data
        self.headers = headers or {}


class Route:
    def __init__(self, request):
        self.request = request
        self.continued = False
        self.aborted = False

    def continue_(self):
        self.continued = True

    def abort(self, *, error_code=None):
        self.aborted = True


class WebSocketRoute:
    def __init__(self):
        self.closed = None

    def close(self, *, code, reason):
        self.closed = (code, reason)


class Context:
    def __init__(self):
        self.routes = {}
        self.ws_handler = None
        self.closed = False

    def route(self, pattern, handler):
        self.routes[pattern] = handler

    def unroute(self, pattern, handler):
        assert self.routes[pattern] is handler
        del self.routes[pattern]

    def route_web_socket(self, pattern, handler):
        self.ws_handler = handler

    def close(self):
        self.closed = True


class Page:
    def __init__(self, context):
        self.context = context
        self.handlers = {}
        self.closed = False

    def on(self, event, handler):
        self.handlers[event] = handler

    def goto(self, url, **kwargs):
        route = Route(Request(url=url))
        self.context.routes["**/*"](route)
        if route.aborted:
            raise RuntimeError("blocked")
        return "response"


class Session:
    def __init__(self):
        self.context = Context()
        self.page = Page(self.context)
        self.closed = False

    def close(self):
        self.closed = True
        self.context.close()


class Launcher:
    def __init__(self):
        self.session = Session()

    def launch(self):
        return self.session


def make_adapter(guard=lambda url, method: True):
    policy = NavigationPolicy(
        allowed_hosts=frozenset({"example.com"}),
        resolver=lambda host: (PUBLIC,),
    )
    launcher = Launcher()
    adapter = SecureBrowserAdapter(
        policy=policy, egress_guard=guard, launcher=launcher
    )
    return adapter, launcher.session


def test_adapter_requires_trusted_egress_guard():
    policy = NavigationPolicy(allowed_hosts=frozenset({"example.com"}))
    with pytest.raises(TypeError, match="egress_guard"):
        SecureBrowserAdapter(policy=policy, egress_guard=None)


@pytest.mark.parametrize("request", [
    Request(method="POST"),
    Request(method="PUT"),
    Request(post_data="payload"),
    Request(headers={"content-type": "multipart/form-data; boundary=x"}),
    Request(resource_type="media"),
    Request(resource_type="websocket"),
    Request(resource_type="eventsource"),
    Request(resource_type="other"),
])
def test_request_policy_rejects_upload_mutation_and_background_traffic(request_case):
    adapter, _ = make_adapter()
    with pytest.raises(Exception):
        adapter._validate_request(request_case)


def test_request_policy_requires_literal_true_from_egress_guard():
    adapter, _ = make_adapter(lambda url, method: 1)
    with pytest.raises(Exception, match="egress"):
        adapter._validate_request(Request())


def test_request_policy_accepts_bounded_read_only_request():
    calls = []
    adapter, _ = make_adapter(lambda url, method: calls.append((url, method)) or True)

    adapter._validate_request(Request(resource_type="document"))

    assert calls == [("https://example.com/", "GET")]


def test_websocket_policy_closes_every_socket():
    route = WebSocketRoute()
    SecureBrowserAdapter._block_websocket(route)
    assert route.closed[0] == 1008
    assert "disabled" in route.closed[1].lower()


def test_adapter_installs_persistent_context_route_and_closes_session():
    adapter, session = make_adapter()

    adapter.start()
    assert adapter.started is True
    assert "**/*" in session.context.routes
    assert session.context.ws_handler is not None
    assert "filechooser" in session.page.handlers

    assert adapter.navigate("https://example.com/") == "response"
    # Route remains active after navigation, so later subresources are covered.
    assert "**/*" in session.context.routes

    adapter.close()
    assert adapter.started is False
    assert session.closed is True
    assert session.context.routes == {}


def test_adapter_denies_request_when_egress_guard_fails_closed():
    adapter, session = make_adapter(lambda url, method: False)
    adapter.start()

    route = Route(Request())
    session.context.routes["**/*"](route)

    assert route.aborted is True
    adapter.close()


def test_adapter_start_fails_if_websocket_deny_capability_is_missing():
    adapter, session = make_adapter()
    session.context.route_web_socket = None

    with pytest.raises(SecureBrowserAdapterError, match="WebSocket"):
        adapter.start()

    assert session.closed is True
    assert adapter.started is False


def test_adapter_cannot_navigate_before_start():
    adapter, _ = make_adapter()
    with pytest.raises(SecureBrowserAdapterError, match="not started"):
        adapter.navigate("https://example.com/")
