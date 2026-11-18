"""Read-only, bounded visible-DOM text inspection for an injected Playwright page.

This adapter never clicks, fills, submits, navigates, evaluates page JavaScript,
or dispatches a browser job. Its observations are untrusted and cannot authorize
an interaction or replace Owner approval.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import re
import time
from typing import Any, Sequence
from urllib.parse import urljoin

from core.browser_security import BrowserPolicyError, validate_destination
from core.browser_interaction import (
    ClickIntent,
    FillIntent,
    InteractionPolicyError,
    TargetEvidence,
    _redact_result_text,
    validate_target_evidence,
)


class DOMInspectionError(ValueError):
    """Visible DOM inspection failed closed."""


@dataclass(frozen=True)
class VisibleDOMSnapshot:
    page_id: str
    origin: str
    text: str


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
        text=_redact_result_text(raw_text),
    )



async def inspect_interaction_target(
    page: Any,
    intent: ClickIntent | FillIntent,
    *,
    allowed_origins: Sequence[str],
    max_scan: int = 200,
    timeout_seconds: float = 3.0,
) -> TargetEvidence:
    """Build fresh, read-only target evidence for a validated interaction intent.

    This function only inspects links or a single labelled form control. It
    never performs the proposed click/fill. Evidence remains untrusted because
    the injected Playwright page is not cryptographically attested here.
    """
    if type(intent) not in (ClickIntent, FillIntent):
        raise DOMInspectionError("A validated click or fill intent is required.")
    if type(max_scan) is not int or not 1 <= max_scan <= 500:
        raise DOMInspectionError("max_scan must be an integer from 1 to 500.")
    if type(timeout_seconds) not in (int, float) or isinstance(timeout_seconds, bool) or not 0.05 <= timeout_seconds <= 10:
        raise DOMInspectionError("timeout_seconds must be between 0.05 and 10.")

    try:
        initial_url = page.url
        current = validate_destination(initial_url, allowed_origins)
        intended = validate_destination(intent.origin, allowed_origins)
        if current.origin != intended.origin:
            raise DOMInspectionError("Current page does not match the intent origin.")
    except (BrowserPolicyError, InteractionPolicyError, TypeError, AttributeError) as exc:
        if isinstance(exc, DOMInspectionError):
            raise
        raise DOMInspectionError("Current page or intent origin is not approved.") from exc

    async def inspect() -> TargetEvidence:
        if isinstance(intent, ClickIntent):
            links = page.locator("a[href]")
            link_count = await links.count()
            if link_count > max_scan:
                raise DOMInspectionError("Link scan exceeded its configured bound.")
            matches = []
            for index in range(link_count):
                link = links.nth(index)
                if not await link.is_visible() or not await link.is_enabled():
                    continue
                raw_href = await link.get_attribute("href")
                if not raw_href:
                    continue
                try:
                    candidate = validate_destination(
                        urljoin(initial_url, raw_href), allowed_origins
                    )
                except BrowserPolicyError:
                    continue
                if candidate.url == intent.destination_url:
                    matches.append(candidate.url)
                    if len(matches) > 1:
                        break
            if len(matches) != 1:
                raise DOMInspectionError(
                    "The intended link must resolve to exactly one visible, enabled target."
                )
            element_type, href = "link", matches[0]
        else:
            methods = {
                "label": "get_by_label",
                "placeholder": "get_by_placeholder",
                "test_id": "get_by_test_id",
            }
            method = getattr(page, methods[intent.locator_kind], None)
            if not callable(method):
                raise DOMInspectionError("The page does not support the required safe locator.")
            locator = (
                method(intent.locator_value, exact=True)
                if intent.locator_kind in {"label", "placeholder"}
                else method(intent.locator_value)
            )
            if await locator.count() != 1:
                raise DOMInspectionError("The form target must resolve to exactly one control.")
            if not await locator.is_visible() or not await locator.is_enabled():
                raise DOMInspectionError("The form target must be visible and enabled.")

            textarea_count = await locator.locator("xpath=self::textarea").count()
            select_count = await locator.locator("xpath=self::select").count()
            input_count = await locator.locator("xpath=self::input").count()
            if textarea_count == 1 and select_count == 0 and input_count == 0:
                element_type = "textarea"
            elif select_count == 1 and textarea_count == 0 and input_count == 0:
                element_type = "select"
            elif input_count == 1 and textarea_count == 0 and select_count == 0:
                input_type = (await locator.get_attribute("type") or "text").lower()
                type_map = {
                    "text": "input_text",
                    "email": "input_email",
                    "number": "input_number",
                    "date": "input_date",
                }
                element_type = type_map.get(input_type)
                if element_type is None:
                    raise DOMInspectionError("Secret or unsupported input types are blocked.")
            else:
                raise DOMInspectionError("The target is not a supported native form control.")
            href = None

        if page.url != initial_url:
            raise DOMInspectionError("Page URL changed while target evidence was collected.")
        observed_at = int(time.time())
        raw_evidence = {
            "interaction_id": intent.interaction_id,
            "page_id": intent.page_id,
            "origin": initial_url,
            "locator": {"kind": intent.locator_kind, "value": intent.locator_value},
            "match_count": 1,
            "visible": True,
            "enabled": True,
            "element_type": element_type,
            "href": href,
            "observed_at": observed_at,
        }
        try:
            return validate_target_evidence(
                raw_evidence,
                intent=intent,
                allowed_origins=allowed_origins,
                now_epoch=observed_at,
            )
        except InteractionPolicyError as exc:
            raise DOMInspectionError("Target evidence did not satisfy the interaction policy.") from exc

    try:
        return await asyncio.wait_for(inspect(), timeout=float(timeout_seconds))
    except asyncio.TimeoutError as exc:
        raise DOMInspectionError("Target inspection exceeded its deadline.") from exc
    except DOMInspectionError:
        raise
    except Exception as exc:
        raise DOMInspectionError("Target inspection failed closed.") from exc
