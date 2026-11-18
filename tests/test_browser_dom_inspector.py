import asyncio

import pytest

from core.browser_dom_inspector import DOMInspectionError, extract_visible_dom_text


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
