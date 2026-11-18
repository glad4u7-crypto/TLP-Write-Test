"""Real Chromium browser-surface integration tests against loopback-only fixtures.

These tests exercise browser behavior (redirects, subresources, popups, iframes,
and WebSockets). They are NOT evidence of OCI, firewall, namespace, or host
network isolation. Every HTTP fixture binds to 127.0.0.1 and browser HTTP
requests to non-loopback destinations are aborted.
"""
from __future__ import annotations

import base64
import hashlib
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urljoin, urlsplit

import pytest
from playwright.sync_api import Error as PlaywrightError, sync_playwright


_PIXEL_PNG = b'<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"></svg>'


class _BrowserSurfaceHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/redirect":
            self.send_response(302)
            self.send_header("Location", "/landing")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if path == "/cross-redirect":
            self.send_response(302)
            self.send_header("Location", "https://outside.invalid/cross-target")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if path == "/pixel.png":
            self.send_response(200)
            self.send_header("Content-Type", "image/svg+xml")
            self.send_header("Content-Length", str(len(_PIXEL_PNG)))
            self.end_headers()
            self.wfile.write(_PIXEL_PNG)
            return
        if path == "/frame":
            self._html("<!doctype html><title>frame</title><body>iframe-marker</body>")
            return
        if path == "/popup":
            self._html("<!doctype html><title>popup</title><body>popup-marker</body>")
            return
        if path == "/landing":
            body = f"""<!doctype html>
<title>APAA Chromium surfaces</title>
<body>landing-marker
<img id="pixel" src="/pixel.png" alt="fixture">
<iframe id="child" src="/frame"></iframe>
<img id="blocked-pixel" src="https://outside.invalid/pixel.png" alt="must be blocked">
<iframe id="blocked-frame" src="https://outside.invalid/frame"></iframe>
<a id="popup-link" target="_blank" href="/popup">Open popup</a>
<a id="blocked-popup-link" target="_blank" href="https://outside.invalid/popup">Blocked popup</a>
</body>"""
            self._html(body)
            return
        if path == "/ws":
            self._websocket()
            return
        self.send_error(404)

    def _html(self, body: str):
        data = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _websocket(self):
        key = self.headers.get("Sec-WebSocket-Key")
        if not key or self.headers.get("Upgrade", "").lower() != "websocket":
            self.send_error(400)
            return
        accept = base64.b64encode(
            hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()
        ).decode("ascii")
        self.send_response(101, "Switching Protocols")
        self.send_header("Upgrade", "websocket")
        self.send_header("Connection", "Upgrade")
        self.send_header("Sec-WebSocket-Accept", accept)
        self.end_headers()
        self.wfile.flush()
        try:
            self.connection.settimeout(5)
            header = self.rfile.read(2)
            if len(header) != 2:
                return
            opcode = header[0] & 0x0F
            masked = bool(header[1] & 0x80)
            length = header[1] & 0x7F
            if length == 126:
                length = int.from_bytes(self.rfile.read(2), "big")
            elif length == 127:
                length = int.from_bytes(self.rfile.read(8), "big")
            if not masked or length > 4096:
                return
            mask = self.rfile.read(4)
            payload = self.rfile.read(length)
            if len(mask) != 4 or len(payload) != length or opcode != 1:
                return
            decoded = bytes(value ^ mask[index % 4] for index, value in enumerate(payload))
            if decoded != b"hello-apaa":
                return
            response = b"ws-ok"
            self.connection.sendall(bytes((0x81, len(response))) + response + bytes((0x88, 0x02, 0x03, 0xE8)))
        except (OSError, TimeoutError):
            return

    def log_message(self, *_args):
        pass


@pytest.fixture
def loopback_site():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _BrowserSurfaceHandler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def test_real_chromium_redirect_subresource_popup_iframe_and_websocket(loopback_site):
    """Exercise five browser surfaces; no production isolation claim is made."""
    observed_requests: list[str] = []
    blocked_requests: list[str] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            context = browser.new_context(service_workers="block", accept_downloads=False)
            page = context.new_page()

            def guard_loopback(route):
                url = route.request.url
                parsed = urlsplit(url)
                if parsed.path == "/cross-redirect":
                    # Route.fetch(max_redirects=0) exposes the 302 response
                    # without following it. Inspect Location before Chromium
                    # can issue the cross-origin follow-up request.
                    response = route.fetch(max_redirects=0)
                    location = response.headers.get("location", "")
                    destination = urljoin(url, location)
                    destination_host = urlsplit(destination).hostname
                    if destination_host not in ("127.0.0.1", "localhost"):
                        blocked_requests.append(destination)
                        route.abort("blockedbyclient")
                        return
                    route.fulfill(response=response)
                    return
                if parsed.scheme in ("http", "https") and parsed.hostname not in ("127.0.0.1", "localhost"):
                    blocked_requests.append(url)
                    route.abort("blockedbyclient")
                    return
                observed_requests.append(url)
                route.continue_()

            context.route("**/*", guard_loopback)
            websocket_urls: list[str] = []
            page.on("websocket", lambda ws: websocket_urls.append(ws.url))
            response = page.goto(loopback_site + "/redirect", wait_until="domcontentloaded")
            assert response is not None and response.status == 200
            assert page.url == loopback_site + "/landing"
            assert page.locator("body").inner_text().startswith("landing-marker")

            page.locator("#pixel").evaluate(
                "(img) => new Promise((resolve) => { if (img.complete) resolve(); else img.onload = resolve; })"
            )
            assert page.locator("#pixel").evaluate("(img) => img.naturalWidth") == 1
            assert page.frame_locator("#child").locator("body").inner_text() == "iframe-marker"

            with page.expect_popup() as popup_info:
                page.locator("#popup-link").click()
            popup = popup_info.value
            popup.wait_for_load_state("domcontentloaded")
            assert popup.locator("body").inner_text() == "popup-marker"

            page.evaluate("""() => {
              const socket = new WebSocket("ws://127.0.0.1:" + location.port + "/ws");
              socket.onopen = () => socket.send("hello-apaa");
              socket.onmessage = event => document.body.dataset.websocket = event.data;
              socket.onerror = () => document.body.dataset.websocket = "error";
            }""")
            page.wait_for_function("document.body.dataset.websocket === 'ws-ok'", timeout=10000)

            redirect_page = context.new_page()
            with pytest.raises(PlaywrightError):
                redirect_page.goto(loopback_site + "/cross-redirect", wait_until="domcontentloaded")
            redirect_page.close()

            with page.expect_popup():
                page.locator("#blocked-popup-link").click()
            page.evaluate("""() => {
              const socket = new WebSocket("ws://outside.invalid:8765/blocked");
              socket.onopen = () => document.body.dataset.blockedWebsocket = "opened";
              socket.onclose = () => {
                if (document.body.dataset.blockedWebsocket !== "opened") document.body.dataset.blockedWebsocket = "blocked";
              };
              socket.onerror = () => {
                if (document.body.dataset.blockedWebsocket !== "opened") document.body.dataset.blockedWebsocket = "blocked";
              };
            }""")
            page.wait_for_function("document.body.dataset.blockedWebsocket === 'blocked'", timeout=5000)

            paths = {urlsplit(url).path for url in observed_requests}
            # Playwright's route hook records the original navigation request;
            # the redirect target is independently verified via page.url/body above.
            assert {"/redirect", "/pixel.png", "/frame", "/popup"}.issubset(paths)
            assert any("outside.invalid/cross-target" in url for url in blocked_requests)
            assert any("outside.invalid/pixel.png" in url for url in blocked_requests)
            assert any("outside.invalid/frame" in url for url in blocked_requests)
            assert any("outside.invalid/popup" in url for url in blocked_requests)
            # Playwright emits a WebSocket event for a connection attempt, even
            # when DNS/connection setup fails. Assert the attempt was observed,
            # while the browser-side handlers prove it never reached onopen.
            assert any(url.startswith("ws://outside.invalid:") for url in websocket_urls)
            assert page.locator("body").evaluate("(body) => body.dataset.blockedWebsocket") == "blocked"
            assert websocket_urls == [
                f"ws://127.0.0.1:{urlsplit(loopback_site).port}/ws",
                "ws://outside.invalid:8765/blocked",
            ]
        finally:
            browser.close()
