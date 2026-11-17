import time

import pytest

import core.live_browsing as live
from core.live_browsing import LiveBrowsingController, LiveBrowsingError


PUBLIC = "93.184.216.34"


def valid_job(**overrides):
    raw = {
        "job_id": "job_live_1234",
        "url": "https://example.com/start",
        "allowed_origins": ["https://example.com"],
        "action": "read_visible_text",
        "expires_at": 1120,
        "max_response_bytes": 100_000,
        "max_runtime_seconds": 10,
    }
    raw.update(overrides)
    return raw


class FakeRequest:
    def __init__(self, url, method="GET"):
        self.url = url
        self.method = method


class FakeRoute:
    def __init__(self, url, method="GET"):
        self.request = FakeRequest(url, method)
        self.action = None

    def continue_(self):
        self.action = "continue"

    def abort(self, reason=None):
        self.action = "abort"
        self.reason = reason


class FakeLocator:
    def inner_text(self):
        return "visible page text"


class FakePage:
    def __init__(self, context, *, requests=()):
        self.context = context
        self.url = "https://example.com/final"
        self.requests = list(requests) or [(self.url, "GET")]
        self.default_timeout = None

    def set_default_timeout(self, value):
        self.default_timeout = value

    def goto(self, url, **kwargs):
        self.goto_url = url
        self.goto_options = kwargs
        for request_url, method in self.requests:
            route = FakeRoute(request_url, method)
            self.context.route_handler(route)
            if route.action != "continue":
                raise RuntimeError("browser request blocked by route policy")
        return type("Response", (), {"ok": True})()

    def locator(self, selector):
        return FakeLocator()

    def title(self):
        return "Example title"

    def screenshot(self, **kwargs):
        return b"PNG"

    def close(self):
        pass


class FakeContext:
    def __init__(self, *, requests=()):
        self.requests = requests
        self.route_handler = None
        self.page_callback = None
        self.page = FakePage(self, requests=requests)
        self.closed = 0

    def new_page(self):
        return self.page

    def route(self, pattern, handler):
        self.route_pattern = pattern
        self.route_handler = handler

    def on(self, event, callback):
        self.page_callback = callback

    def close(self):
        self.closed += 1


class FakeSession:
    def __init__(self, context):
        self.context = context
        self.closed = 0

    def close(self):
        self.closed += 1
        self.context.close()


def setup_controller(monkeypatch, *, requests=(), audit=None):
    context = FakeContext(requests=requests)
    session = FakeSession(context)
    launches = []

    def launch(*args, **kwargs):
        launches.append((args, kwargs))
        return session

    monkeypatch.setattr(live, "launch_chromium", launch)
    events = [] if audit is None else audit
    controller = LiveBrowsingController(object(), audit=events.append)
    return controller, context, session, launches, events


def test_live_browsing_reads_visible_text_in_fresh_attested_session(monkeypatch):
    controller, context, session, launches, events = setup_controller(monkeypatch)
    result = controller.execute(
        valid_job(), signed_evidence={"signed": True}, challenge="c" * 64,
        now=1000, resolver=lambda host: (PUBLIC,),
    )
    assert result.text == "visible page text"
    assert result.final_url == "https://example.com/final"
    assert len(launches) == 1
    assert session.closed == 1
    assert context.route_pattern == "**/*"
    assert [event["event"] for event in events] == ["job_accepted", "job_completed"]
    assert all("url" not in event and "text" not in event for event in events)


def test_cross_origin_redirect_is_blocked_by_browser_request_guard(monkeypatch):
    controller, context, session, launches, events = setup_controller(
        monkeypatch,
        requests=[
            ("https://example.com/start", "GET"),
            ("https://evil.example.net/steal", "GET"),
        ],
    )
    with pytest.raises(LiveBrowsingError, match="failed or was blocked"):
        controller.execute(
            valid_job(), signed_evidence={}, challenge="c" * 64,
            now=1000, resolver=lambda host: (PUBLIC,),
        )
    assert session.closed == 1
    assert [event["event"] for event in events] == ["job_accepted", "job_failed"]


def test_mutating_http_method_is_blocked(monkeypatch):
    controller, context, session, launches, events = setup_controller(
        monkeypatch, requests=[("https://example.com/start", "POST")]
    )
    with pytest.raises(LiveBrowsingError):
        controller.execute(
            valid_job(), signed_evidence={}, challenge="c" * 64,
            now=1000, resolver=lambda host: (PUBLIC,),
        )
    assert session.closed == 1
    assert launches


def test_missing_or_failed_dns_resolver_blocks_before_browser_launch(monkeypatch):
    controller, context, session, launches, events = setup_controller(monkeypatch)
    with pytest.raises(LiveBrowsingError):
        controller.execute(
            valid_job(), signed_evidence={}, challenge="c" * 64,
            now=1000, resolver=None,
        )
    assert launches == []


def test_audit_acceptance_failure_blocks_browser_launch(monkeypatch):
    def broken_audit(event):
        raise OSError("audit unavailable")

    controller, context, session, launches, events = setup_controller(
        monkeypatch, audit=broken_audit
    )
    with pytest.raises(LiveBrowsingError, match="audit persistence"):
        controller.execute(
            valid_job(), signed_evidence={}, challenge="c" * 64,
            now=1000, resolver=lambda host: (PUBLIC,),
        )
    assert launches == []


def test_response_byte_limit_is_enforced_and_session_is_closed(monkeypatch):
    controller, context, session, launches, events = setup_controller(monkeypatch)
    with pytest.raises(LiveBrowsingError, match="byte limit"):
        controller.execute(
            valid_job(max_response_bytes=3), signed_evidence={}, challenge="c" * 64,
            now=1000, resolver=lambda host: (PUBLIC,),
        )
    assert session.closed == 1


def test_job_schema_and_expiry_are_validated_before_browser_launch(monkeypatch):
    controller, context, session, launches, events = setup_controller(monkeypatch)
    with pytest.raises(LiveBrowsingError, match="validation"):
        controller.execute(
            valid_job(expires_at=999), signed_evidence={}, challenge="c" * 64,
            now=1000, resolver=lambda host: (PUBLIC,),
        )
    assert launches == []


def test_read_title_and_transient_screenshot_actions(monkeypatch):
    controller, context, session, launches, events = setup_controller(monkeypatch)
    title = controller.execute(
        valid_job(action="read_page_title"), signed_evidence={}, challenge="c" * 64,
        now=1000, resolver=lambda host: (PUBLIC,),
    )
    assert title.title == "Example title"

    controller, context, session, launches, events = setup_controller(monkeypatch)
    shot = controller.execute(
        valid_job(action="capture_transient_screenshot"), signed_evidence={}, challenge="c" * 64,
        now=1000, resolver=lambda host: (PUBLIC,),
    )
    assert shot.screenshot_png == b"PNG"
