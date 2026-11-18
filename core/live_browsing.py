"""Controlled, read-only live browsing through the attested Chromium worker.

This is an integration layer, not a sandbox or firewall. It launches Chromium
only through the signed runtime gate, restricts every browser request to the
job's exact HTTPS origins, permits only GET/HEAD, and exposes read-only results.
The host proxy/firewall must independently enforce DNS/IP pinning and proxy-only
egress before this module is enabled for public websites.
"""
from __future__ import annotations

from dataclasses import dataclass
import time
from collections.abc import Callable, Mapping
from typing import Any

from core.browser_launcher import BrowserLaunchError, BrowserSession, launch_chromium
from core.browser_security import BrowserPolicyError, validate_browser_job, validate_destination


class LiveBrowsingError(RuntimeError):
    """Raised when a controlled live-browsing job cannot complete safely."""


@dataclass(frozen=True)
class LiveBrowsingResult:
    job_id: str
    action: str
    final_url: str
    title: str | None = None
    text: str | None = None
    links: tuple[dict[str, str], ...] = ()
    elements: tuple[dict[str, Any], ...] = ()
    screenshot_png: bytes | None = None
    elapsed_ms: int = 0


class LiveBrowsingController:
    """Execute short-lived, exact-origin, read-only jobs in attested Chromium.

    The audit callback must persist events durably. Acceptance-audit failure
    blocks browser launch; completion-audit failure suppresses the result.
    URLs and page content are deliberately excluded from audit records.
    """

    def __init__(
        self,
        runtime_gate: Any,
        *,
        audit: Callable[[Mapping[str, Any]], None],
    ) -> None:
        if audit is None or not callable(audit):
            raise TypeError("A durable audit callback is required.")
        self._runtime_gate = runtime_gate
        self._audit = audit

    def _emit(self, event: str, job_id: str, action: str, **extra: Any) -> None:
        record = {
            "component": "apaa_live_browsing",
            "event": event,
            "job_id": job_id,
            "action": action,
            "timestamp": int(time.time()),
            **extra,
        }
        try:
            self._audit(record)
        except Exception as exc:
            raise LiveBrowsingError("Required browser audit persistence failed; operation is blocked.") from exc

    def execute(
        self,
        raw_job: object,
        *,
        signed_evidence: object,
        challenge: str,
        now: int,
        resolver: Callable[[str], Any],
    ) -> LiveBrowsingResult:
        started = time.monotonic()
        if not callable(resolver):
            raise LiveBrowsingError("A trusted live DNS resolver is required.")
        try:
            job = validate_browser_job(raw_job, now=now, resolver=resolver)
        except (BrowserPolicyError, TypeError, ValueError) as exc:
            raise LiveBrowsingError("Browser job failed closed validation.") from exc

        # Require the live resolver at admission and for every browser request.
        self._emit("job_accepted", job.job_id, job.action)

        session: BrowserSession | None = None
        result: LiveBrowsingResult | None = None
        failure: Exception | None = None
        try:
            session = launch_chromium(
                self._runtime_gate,
                signed_evidence,
                challenge=challenge,
                now=now,
            )
            context = session.context
            page = context.new_page()
            deadline = time.monotonic() + job.max_runtime_seconds
            request_count = 0

            def guard_request(route: Any) -> None:
                nonlocal request_count
                request = route.request
                try:
                    if time.monotonic() >= deadline:
                        route.abort("timedout")
                        return
                    if request.method not in ("GET", "HEAD"):
                        route.abort("blockedbyclient")
                        return
                    validate_destination(
                        request.url,
                        job.allowed_origins,
                        resolver=resolver,
                    )
                    request_count += 1
                    if request_count > 250:
                        route.abort("blockedbyclient")
                        return
                    route.continue_()
                except Exception:
                    # Any malformed URL, origin escape, DNS failure or route
                    # policy error blocks that request; there is no direct path.
                    try:
                        route.abort("blockedbyclient")
                    except Exception:
                        pass

            context.route("**/*", guard_request)
            route_web_socket = getattr(context, "route_web_socket", None)
            if not callable(route_web_socket):
                raise LiveBrowsingError(
                    "This Playwright runtime cannot enforce the WebSocket deny policy; browsing is blocked."
                )

            def deny_web_socket(web_socket: Any) -> None:
                web_socket.close(
                    code=1008,
                    reason="WebSocket is disabled by the read-only browsing policy",
                )

            route_web_socket("**/*", deny_web_socket)

            def close_unexpected_page(unexpected: Any) -> None:
                if unexpected is not page:
                    try:
                        unexpected.close()
                    except Exception:
                        pass

            context.on("page", close_unexpected_page)
            page.set_default_timeout(job.max_runtime_seconds * 1000)
            response = page.goto(
                job.url,
                wait_until="domcontentloaded",
                timeout=job.max_runtime_seconds * 1000,
            )
            if response is None or not response.ok:
                raise LiveBrowsingError("Navigation did not return a successful HTTP response.")
            if time.monotonic() >= deadline:
                raise LiveBrowsingError("Live-browsing job exceeded its runtime deadline.")

            final_url = page.url
            validate_destination(final_url, job.allowed_origins, resolver=resolver)
            title: str | None = None
            text: str | None = None
            links: tuple[dict[str, str], ...] = ()
            elements: tuple[dict[str, Any], ...] = ()
            screenshot: bytes | None = None

            if job.action == "navigate_exact_origin":
                pass
            elif job.action == "read_page_title":
                title = page.title()
                if len(title.encode("utf-8")) > job.max_response_bytes:
                    raise LiveBrowsingError("Page title exceeds the response byte limit.")
            elif job.action == "read_visible_text":
                text = page.locator("body").inner_text()
                if len(text.encode("utf-8")) > job.max_response_bytes:
                    raise LiveBrowsingError("Visible page text exceeds the response byte limit.")
            elif job.action == "read_link_metadata":
                raw_links = page.locator("a[href]").evaluate_all(
                    "(nodes) => nodes.slice(0, 200).map((node) => ({"
                    "text: (node.innerText || node.getAttribute('aria-label') || '').trim(), "
                    "href: node.href"
                    "}))"
                )
                approved: list[dict[str, str]] = []
                total = 0
                for item in raw_links:
                    try:
                        target = validate_destination(item.get("href", ""), job.allowed_origins, resolver=resolver)
                    except Exception:
                        continue
                    record = {"text": str(item.get("text", ""))[:500], "url": target.url}
                    total += len(record["text"].encode("utf-8")) + len(record["url"].encode("utf-8"))
                    if total > job.max_response_bytes:
                        raise LiveBrowsingError("Link metadata exceeds the response byte limit.")
                    approved.append(record)
                links = tuple(approved)
            elif job.action == "inspect_elements":
                # Read-only, bounded DOM metadata only: never return input values,
                # HTML, cookies, storage, hidden text, or executable handles.
                raw_elements = page.locator(
                    "button,a[href],input,select,textarea,[role],[tabindex]"
                ).evaluate_all(
                    """nodes => nodes.slice(0, 100).map(node => {
                      const style = window.getComputedStyle(node);
                      const rect = node.getBoundingClientRect();
                      const visible = style.visibility !== "hidden" &&
                        style.display !== "none" && rect.width > 0 && rect.height > 0;
                      return {
                        tag: node.tagName.toLowerCase(),
                        role: node.getAttribute("role") || "",
                        label: node.getAttribute("aria-label") || "",
                        text: visible ? (node.innerText || "").trim() : "",
                        disabled: Boolean(node.disabled) ||
                          node.getAttribute("aria-disabled") === "true",
                        visible,
                        href: node instanceof HTMLAnchorElement ? node.href : ""
                      };
                    })"""
                )
                approved_elements: list[dict[str, Any]] = []
                total = 0
                for item in raw_elements:
                    if not isinstance(item, Mapping):
                        continue
                    tag = str(item.get("tag", ""))[:20]
                    if not tag.isalpha():
                        continue
                    record: dict[str, Any] = {
                        "tag": tag,
                        "role": str(item.get("role", ""))[:64],
                        "label": str(item.get("label", ""))[:200],
                        "text": str(item.get("text", ""))[:300],
                        "disabled": bool(item.get("disabled", False)),
                        "visible": bool(item.get("visible", False)),
                    }
                    href = item.get("href", "")
                    if href:
                        try:
                            target = validate_destination(
                                href, job.allowed_origins, resolver=resolver
                            )
                            record["href"] = target.url
                        except Exception:
                            # Do not disclose or return links outside the approved origin.
                            pass
                    import json
                    total += len(json.dumps(record, ensure_ascii=False).encode("utf-8"))
                    if total > job.max_response_bytes:
                        raise LiveBrowsingError(
                            "Element inspection metadata exceeds the response byte limit."
                        )
                    approved_elements.append(record)
                elements = tuple(approved_elements)
            elif job.action == "capture_transient_screenshot":
                screenshot = page.screenshot(
                    type="png",
                    full_page=False,
                    animations="disabled",
                    timeout=job.max_runtime_seconds * 1000,
                )
                if len(screenshot) > job.max_response_bytes:
                    raise LiveBrowsingError("Screenshot exceeds the response byte limit.")
            else:
                raise LiveBrowsingError("Browser action is not supported by the live controller.")

            result = LiveBrowsingResult(
                job_id=job.job_id,
                action=job.action,
                final_url=final_url,
                title=title,
                text=text,
                links=links,
                elements=elements,
                screenshot_png=screenshot,
                elapsed_ms=int((time.monotonic() - started) * 1000),
            )
        except Exception as exc:
            failure = exc
        finally:
            if session is not None:
                try:
                    session.close()
                except Exception as exc:
                    if failure is None:
                        failure = BrowserLaunchError("Browser session cleanup failed.")
                        failure.__cause__ = exc

        elapsed = int((time.monotonic() - started) * 1000)
        if failure is not None:
            self._emit("job_failed", job.job_id, job.action, elapsed_ms=elapsed,
                       error_type=type(failure).__name__)
            if isinstance(failure, LiveBrowsingError):
                raise failure
            raise LiveBrowsingError("Live-browsing job failed or was blocked.") from failure

        self._emit("job_completed", job.job_id, job.action, elapsed_ms=elapsed)
        if result is None:
            raise LiveBrowsingError("Live-browsing worker returned no result.")
        return result
