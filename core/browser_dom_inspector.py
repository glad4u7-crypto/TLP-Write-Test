"""Read-only, bounded visible-DOM text inspection for an injected Playwright page.

This adapter never clicks, fills, submits, navigates, evaluates page JavaScript,
or dispatches a browser job. Its observations are untrusted and cannot authorize
an interaction or replace Owner approval.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import re
from typing import Any, Sequence

from core.browser_security import BrowserPolicyError, validate_destination


class DOMInspectionError(ValueError):
    """Visible DOM inspection failed closed."""


@dataclass(frozen=True)
class VisibleDOMSnapshot:
    page_id: str
    origin: str
    text: str


def _redact_visible_text(value: str) -> str:
    value = re.sub(r"(?i)\\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\\.[A-Z]{2,}\\b", "[redacted-email]", value)
    value = re.sub(r"(?<!\\w)\\+?\\d[\\d\\s().-]{7,}\\d(?!\\w)", "[redacted-phone]", value)
    value = re.sub(r"(?i)\\bBearer\\s+[A-Za-z0-9._~+/=-]{8,}", "Bearer [redacted]", value)
    value = re.sub(
        r"(?i)\\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token|secret|password)\\s*[:=]\\s*[^\\s,;]{6,}",
        "[redacted-secret]",
        value,
    )
    return value


async def extract_visible_dom_text(
    page: Any,
    *,
    page_id: str,
    allowed_origins: Sequence[str],
    max_chars: int = 20_000,
    timeout_seconds: float = 3.0,
) -> VisibleDOMSnapshot:
    """Extract bounded rendered body text from the current page only.

    The caller must supply an already-authorized page object. The returned
    snapshot is observational data, not cryptographic evidence: page_id is a
    caller correlation label and this function does not attest process identity.
    """
    if type(page_id) is not str or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{7,63}", page_id):
        raise DOMInspectionError("page_id is malformed.")
    if type(max_chars) is not int or not 1 <= max_chars <= 50_000:
        raise DOMInspectionError("max_chars must be between 1 and 50000.")
    if type(timeout_seconds) not in (int, float) or isinstance(timeout_seconds, bool) or not 0.05 <= timeout_seconds <= 10:
        raise DOMInspectionError("timeout_seconds must be between 0.05 and 10.")
    try:
        destination = validate_destination(page.url, allowed_origins)
    except (BrowserPolicyError, TypeError, AttributeError) as exc:
        raise DOMInspectionError("Current page is not on an approved HTTPS origin.") from exc

    async def read_body() -> str:
        body = page.locator("body")
        if await body.count() != 1 or not await body.is_visible():
            raise DOMInspectionError("A unique visible body element is required.")
        return await body.inner_text(timeout=max(1, int(timeout_seconds * 1000)))

    try:
        raw_text = await asyncio.wait_for(read_body(), timeout=float(timeout_seconds))
    except asyncio.TimeoutError as exc:
        raise DOMInspectionError("Visible DOM inspection exceeded its deadline.") from exc
    except DOMInspectionError:
        raise
    except Exception as exc:
        raise DOMInspectionError("Visible DOM inspection failed closed.") from exc

    if type(raw_text) is not str:
        raise DOMInspectionError("Browser adapter returned non-text content.")
    if len(raw_text) > max_chars:
        raise DOMInspectionError("Visible DOM text exceeded the configured bound.")
    return VisibleDOMSnapshot(
        page_id=page_id,
        origin=destination.origin,
        text=_redact_visible_text(raw_text),
    )
