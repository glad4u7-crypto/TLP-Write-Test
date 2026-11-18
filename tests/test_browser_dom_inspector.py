import asyncio

import pytest

from core.browser_interaction import ClickIntent, FillIntent
from core.browser_dom_inspector import (
    DOMInspectionError, extract_visible_dom_text, inspect_interaction_target,
)


class FakeBody:
    def __init__(self, text="Hello world", *, visible=True, count=1, delay=0):
        self.text, self.visible, self.matches, self.delay = text, visible, count, delay

    async def count(self):
        return self.matches

    async def is_visible(self):
        return self.visible

    async def inner_text(self, timeout):
        if self.delay:
            try:
                await asyncio.sleep(self.delay)
            except asyncio.CancelledError:
                self.cancelled = True
                raise
        return self.text


class FakePage:
    def __init__(self, url="https://example.com/docs", body=None):
        self.url = url
        self.body = body or FakeBody()

    def locator(self, selector):
        assert selector == "body"
        return self.body


def run(page, **kwargs):
    return asyncio.run(extract_visible_dom_text(
        page, page_id="page_0000001", allowed_origins=["https://example.com"], **kwargs
    ))


def test_extracts_only_bounded_visible_body_text_and_redacts_sensitive_values():
    snapshot = run(FakePage(body=FakeBody("Contact user@example.com. Bearer abcdefghijklmnop")))
    assert snapshot.origin == "https://example.com"
    assert "[redacted-email]" in snapshot.text
    assert "Bearer [redacted]" in snapshot.text


@pytest.mark.parametrize("body", [
    FakeBody(visible=False),
    FakeBody(count=0),
    FakeBody(count=2),
])
def test_rejects_hidden_or_ambiguous_body(body):
    with pytest.raises(DOMInspectionError):
        run(FakePage(body=body))


def test_rejects_cross_origin_and_unbounded_text():
    with pytest.raises(DOMInspectionError):
        run(FakePage(url="https://evil.example/"))
    with pytest.raises(DOMInspectionError):
        run(FakePage(body=FakeBody("x" * 101)), max_chars=100)


def test_enforces_deadline_and_rejects_bad_bounds():
    with pytest.raises(DOMInspectionError):
        run(FakePage(body=FakeBody(delay=0.1)), timeout_seconds=0.05)
    with pytest.raises(DOMInspectionError):
        run(FakePage(), max_chars=True)


def test_rejects_malformed_page_id_and_invalid_timeout():
    with pytest.raises(DOMInspectionError):
        asyncio.run(extract_visible_dom_text(
            FakePage(), page_id="short", allowed_origins=["https://example.com"]
        ))
    with pytest.raises(DOMInspectionError):
        run(FakePage(), timeout_seconds=True)


def test_timeout_cancels_pending_dom_read():
    body = FakeBody(delay=0.2)
    with pytest.raises(DOMInspectionError):
        run(FakePage(body=body), timeout_seconds=0.05)
    assert body.cancelled is True


def test_reuses_sensitive_value_redaction_for_tokens_and_labelled_secrets():
    snapshot = run(FakePage(body=FakeBody(
        "api_key=abcdef0123456789 Bearer abcdefghijklmnop"
    )))
    assert "[redacted-secret]" in snapshot.text
    assert "Bearer [redacted]" in snapshot.text
    assert "abcdef0123456789" not in snapshot.text



class FakeLink:
    def __init__(self, href, *, visible=True, enabled=True):
        self.href, self.visible, self.enabled = href, visible, enabled

    async def is_visible(self):
        return self.visible

    async def is_enabled(self):
        return self.enabled

    async def get_attribute(self, name):
        assert name == "href"
        return self.href


class FakeLinkCollection:
    def __init__(self, links):
        self.links = links

    async def count(self):
        return len(self.links)

    def nth(self, index):
        return self.links[index]


class FakeControl:
    def __init__(self, tag, *, input_type=None, visible=True, enabled=True, count=1):
        self.tag, self.input_type = tag, input_type
        self.visible, self.enabled, self.matches = visible, enabled, count

    async def count(self):
        return self.matches

    async def is_visible(self):
        return self.visible

    async def is_enabled(self):
        return self.enabled

    def locator(self, selector):
        selected = selector == f"xpath=self::{self.tag}"
        return FakeCount(1 if selected else 0)

    async def get_attribute(self, name):
        assert name == "type"
        return self.input_type


class FakeCount:
    def __init__(self, value):
        self.value = value

    async def count(self):
        return self.value


class TargetPage:
    def __init__(self, *, url="https://example.com/start", links=None, control=None):
        self.url = url
        self.links = links or []
        self.control = control

    def locator(self, selector):
        assert selector == "a[href]"
        return FakeLinkCollection(self.links)

    def get_by_label(self, value, *, exact):
        assert exact is True
        return self.control


def test_previews_unique_visible_link_without_clicking():
    intent = ClickIntent(
        "interaction_0001", "page_0000001", "https://example.com/start",
        "role", "link", "https://example.com/next",
    )
    evidence = asyncio.run(inspect_interaction_target(
        TargetPage(links=[
            FakeLink("https://offsite.example/"),
            FakeLink("/next"),
            FakeLink("/hidden", visible=False),
        ]),
        intent,
        allowed_origins=["https://example.com"],
    ))
    assert evidence.element_type == "link"
    assert evidence.href == "https://example.com/next"


def test_rejects_duplicate_or_unbounded_link_targets():
    intent = ClickIntent(
        "interaction_0001", "page_0000001", "https://example.com/start",
        "role", "link", "https://example.com/next",
    )
    with pytest.raises(DOMInspectionError):
        asyncio.run(inspect_interaction_target(
            TargetPage(links=[FakeLink("/next"), FakeLink("/next")]),
            intent, allowed_origins=["https://example.com"],
        ))
    with pytest.raises(DOMInspectionError):
        asyncio.run(inspect_interaction_target(
            TargetPage(links=[FakeLink("/next")]),
            intent, allowed_origins=["https://example.com"], max_scan=0,
        ))


def test_previews_supported_form_control_without_reading_or_filling_value():
    intent = FillIntent(
        "interaction_0002", "page_0000001", "https://example.com/start",
        "label", "Contact email", "email", "person@example.com",
    )
    evidence = asyncio.run(inspect_interaction_target(
        TargetPage(control=FakeControl("input", input_type="email")),
        intent,
        allowed_origins=["https://example.com"],
    ))
    assert evidence.element_type == "input_email"
    assert evidence.href is None


def test_blocks_secret_form_controls_and_hidden_targets():
    password_intent = FillIntent(
        "interaction_0003", "page_0000001", "https://example.com/start",
        "label", "Password", "text", "not-a-secret",
    )
    with pytest.raises(DOMInspectionError):
        asyncio.run(inspect_interaction_target(
            TargetPage(control=FakeControl("input", input_type="password")),
            password_intent,
            allowed_origins=["https://example.com"],
        ))
    hidden_intent = FillIntent(
        "interaction_0004", "page_0000001", "https://example.com/start",
        "label", "Name", "text", "Alice",
    )
    with pytest.raises(DOMInspectionError):
        asyncio.run(inspect_interaction_target(
            TargetPage(control=FakeControl("input", input_type="text", visible=False)),
            hidden_intent,
            allowed_origins=["https://example.com"],
        ))
