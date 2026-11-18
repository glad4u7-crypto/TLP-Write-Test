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

    def evaluate_all(self, _script):
        return [
            {"tag": "button", "role": "button", "label": "Continue",
             "text": "Continue", "disabled": False, "visible": True, "href": ""},
            {"tag": "input", "role": "", "label": "Email",
             "text": "", "disabled": True, "visible": True, "href": ""},
            {"tag": "div", "role": "status", "label": "",
             "text": "", "disabled": False, "visible": False, "href": ""},
        ]


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


class FakeWebSocket:
    def __init__(self):
        self.closed = None

    def close(self, **kwargs):
        self.closed = kwargs


class FakeContext:
    def __init__(self, *, requests=(), websocket_support=True):
        self.requests = requests
        self.route_handler = None
        self.page_callback = None
        self.page = FakePage(self, requests=requests)
        self.closed = 0
        self.web_socket_handler = None
        if not websocket_support:
            self.route_web_socket = None

    def new_page(self):
        return self.page

    def route(self, pattern, handler):
        self.route_pattern = pattern
        self.route_handler = handler

    def on(self, event, callback):
        self.page_callback = callback

    def route_web_socket(self, pattern, handler):
        self.websocket_pattern = pattern
        self.web_socket_handler = handler

    def close(self):
        self.closed += 1


class FakeSession:
    def __init__(self, context):
        self.context = context
        self.closed = 0

    def close(self):
        self.closed += 1
        self.context.close()


def setup_controller(monkeypatch, *, requests=(), audit=None, websocket_support=True):
    context = FakeContext(requests=requests, websocket_support=websocket_support)
    session = FakeSession(context)
    launches = []

    def launch(*args, **kwargs):
        launches.append((args, kwargs))
        return session

    monkeypatch.setattr(live, "launch_chromium", launch)
    events = [] if audit is None else audit
    audit_sink = events.append if callable(getattr(events, "append", None)) else events
    controller = LiveBrowsingController(object(), audit=audit_sink)
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
    assert context.websocket_pattern == "**/*"
    web_socket = FakeWebSocket()
    context.web_socket_handler(web_socket)
    assert web_socket.closed["code"] == 1008
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



def test_missing_websocket_blocking_support_fails_closed(monkeypatch):
    controller, context, session, launches, events = setup_controller(
        monkeypatch, websocket_support=False
    )
    with pytest.raises(LiveBrowsingError, match="WebSocket deny policy"):
        controller.execute(
            valid_job(), signed_evidence={}, challenge="c" * 64,
            now=1000, resolver=lambda host: (PUBLIC,),
        )
    assert session.closed == 1


def test_inspect_elements_returns_bounded_read_only_metadata(monkeypatch):
    controller, context, session, launches, events = setup_controller(monkeypatch)
    result = controller.execute(
        valid_job(action="inspect_elements"),
        signed_evidence={}, challenge="c" * 64,
        now=1000, resolver=lambda host: (PUBLIC,),
    )
    assert len(result.elements) == 3
    assert result.elements[0]["tag"] == "button"
    assert result.elements[0]["label"] == "Continue"
    assert result.elements[1]["disabled"] is True
    assert result.elements[2]["visible"] is False
    assert result.elements[2]["text"] == ""
    assert all("value" not in item and "html" not in item for item in result.elements)
    assert session.closed == 1
    assert [event["event"] for event in events] == ["job_accepted", "job_completed"]


def test_element_inspection_obeys_response_byte_limit(monkeypatch):
    controller, context, session, launches, events = setup_controller(monkeypatch)
    with pytest.raises(LiveBrowsingError, match="(?i)element inspection metadata"):
        controller.execute(
            valid_job(action="inspect_elements", max_response_bytes=1),
            signed_evidence={}, challenge="c" * 64,
            now=1000, resolver=lambda host: (PUBLIC,),
        )
    assert session.closed == 1


def test_element_inspection_discards_malformed_metadata_without_boolean_coercion(monkeypatch):
    controller, context, session, launches, events = setup_controller(monkeypatch)

    class MalformedLocator:
        def evaluate_all(self, _script):
            return [
                {"tag": "button", "role": "button", "label": "Safe",
                 "text": "Safe", "disabled": False, "visible": True, "href": ""},
                {"tag": "input", "role": "", "label": "Hidden",
                 "text": "", "disabled": "false", "visible": "false", "href": ""},
                {"tag": "div", "role": None, "label": "Bad",
                 "text": "", "disabled": False, "visible": True, "href": ""},
            ]

    monkeypatch.setattr(context.page, "locator", lambda _selector: MalformedLocator())
    result = controller.execute(
        valid_job(action="inspect_elements"),
        signed_evidence={}, challenge="c" * 64,
        now=1000, resolver=lambda host: (PUBLIC,),
    )
    assert len(result.elements) == 1
    assert result.elements[0]["label"] == "Safe"
    assert result.elements[0]["disabled"] is False
    assert result.elements[0]["visible"] is True
    assert session.closed == 1


def test_element_inspection_evaluation_timeout_fails_closed_and_closes_session(monkeypatch):
    controller, context, session, launches, events = setup_controller(monkeypatch)

    class TimedOutLocator:
        def evaluate_all(self, _script):
            raise TimeoutError("stale element inspection timed out")

    monkeypatch.setattr(context.page, "locator", lambda _selector: TimedOutLocator())
    with pytest.raises(LiveBrowsingError, match="failed or was blocked"):
        controller.execute(
            valid_job(action="inspect_elements"),
            signed_evidence={}, challenge="c" * 64,
            now=1000, resolver=lambda host: (PUBLIC,),
        )
    assert session.closed == 1
    assert [event["event"] for event in events] == ["job_accepted", "job_failed"]



def test_element_inspection_caps_duplicate_matches_and_returns_metadata_only(monkeypatch):
    controller, context, session, launches, events = setup_controller(monkeypatch)

    class DuplicateLocator:
        def evaluate_all(self, _script):
            item = {
                "tag": "button", "role": "button", "label": "Continue",
                "text": "Continue", "disabled": False, "visible": True,
                "href": "", "value": "secret-value", "outerHTML": "<button>secret</button>",
                "cookies": "secret-cookie", "storage": "secret-storage",
            }
            return [dict(item) for _ in range(125)]

    monkeypatch.setattr(context.page, "locator", lambda _selector: DuplicateLocator())
    result = controller.execute(
        valid_job(action="inspect_elements"), signed_evidence={},
        challenge="c" * 64, now=1000, resolver=lambda host: (PUBLIC,),
    )
    assert len(result.elements) == 100
    assert all(set(item) == {"tag", "role", "label", "text", "disabled", "visible"} for item in result.elements)
    assert all("secret" not in repr(item) for item in result.elements)
    assert session.closed == 1


def test_element_inspection_omits_disallowed_link_targets(monkeypatch):
    controller, context, session, launches, events = setup_controller(monkeypatch)

    class LinkLocator:
        def evaluate_all(self, _script):
            return [
                {"tag": "a", "role": "link", "label": "Safe", "text": "Safe",
                 "disabled": False, "visible": True, "href": "https://example.com/ok"},
                {"tag": "a", "role": "link", "label": "External", "text": "External",
                 "disabled": False, "visible": True, "href": "https://evil.example.net/"},
            ]

    monkeypatch.setattr(context.page, "locator", lambda _selector: LinkLocator())
    result = controller.execute(
        valid_job(action="inspect_elements"), signed_evidence={},
        challenge="c" * 64, now=1000, resolver=lambda host: (PUBLIC,),
    )
    assert len(result.elements) == 2
    assert result.elements[0]["href"] == "https://example.com/ok"
    assert "href" not in result.elements[1]
    assert "evil.example.net" not in repr(result.elements)
    assert session.closed == 1


def test_element_inspection_stale_locator_handle_fails_closed(monkeypatch):
    controller, context, session, launches, events = setup_controller(monkeypatch)

    class StaleLocator:
        def evaluate_all(self, _script):
            raise RuntimeError("stale element handle")

    monkeypatch.setattr(context.page, "locator", lambda _selector: StaleLocator())
    with pytest.raises(LiveBrowsingError, match="failed or was blocked"):
        controller.execute(
            valid_job(action="inspect_elements"), signed_evidence={},
            challenge="c" * 64, now=1000, resolver=lambda host: (PUBLIC,),
        )
    assert session.closed == 1
    assert [event["event"] for event in events] == ["job_accepted", "job_failed"]


def test_element_inspection_selector_creation_failure_fails_closed(monkeypatch):
    controller, context, session, launches, events = setup_controller(monkeypatch)

    def broken_locator(_selector):
        raise TimeoutError("selector resolution timed out")

    monkeypatch.setattr(context.page, "locator", broken_locator)
    with pytest.raises(LiveBrowsingError, match="failed or was blocked"):
        controller.execute(
            valid_job(action="inspect_elements"), signed_evidence={},
            challenge="c" * 64, now=1000, resolver=lambda host: (PUBLIC,),
        )
    assert session.closed == 1
    assert [event["event"] for event in events] == ["job_accepted", "job_failed"]
