"""Safe, bounded public-web transports for APAA read-only capabilities.

No cookies, credentials, proxy environment, browser, JavaScript, or write methods.
Every request is direct HTTPS to a DNS-resolved globally routable IP pinned for that
connection; redirects are manual and revalidated before a new connection.
"""
from __future__ import annotations

from html.parser import HTMLParser
import http.client
import ipaddress
import json
import socket
import ssl
from urllib.parse import parse_qs, quote_plus, urljoin, urlsplit

from core.capabilities import (
    CapabilityContractError,
    ReadCapability,
    ReadItem,
    ReadRequest,
    ReadResult,
    _validate_https_target,
)
from core.read_only_adapters import ReadOnlyAdapterError

MAX_RESPONSE_BYTES = 1_000_000
MAX_REDIRECTS = 3
DEFAULT_TIMEOUT = 8.0
USER_AGENT = "APAA-Personal-Edition-ReadOnly/1.0"


class SafeNetworkError(ReadOnlyAdapterError):
    """Public network request failed a safety or transport check."""


def _public_addresses(host: str, resolver=socket.getaddrinfo):
    try:
        answers = resolver(host, 443, type=socket.SOCK_STREAM)
    except OSError:
        raise SafeNetworkError("Public host could not be resolved.") from None
    addresses = []
    for family, socktype, proto, _canonname, sockaddr in answers:
        try:
            address = ipaddress.ip_address(sockaddr[0].split("%", 1)[0])
        except ValueError:
            raise SafeNetworkError("DNS returned an invalid address.") from None
        if not address.is_global:
            raise SafeNetworkError("Private, local, or reserved network destinations are blocked.")
        candidate = (family, socktype, proto, sockaddr)
        if candidate not in addresses:
            addresses.append(candidate)
    if not addresses:
        raise SafeNetworkError("Host has no globally routable address.")
    return addresses


class SafeHTTPSClient:
    """Minimal direct HTTPS client with DNS pinning and strict redirect handling."""

    def __init__(self, *, timeout: float = DEFAULT_TIMEOUT, max_bytes: int = MAX_RESPONSE_BYTES,
                 resolver=socket.getaddrinfo):
        if not 0.5 <= timeout <= 20:
            raise ValueError("timeout must be between 0.5 and 20 seconds")
        if not 1024 <= max_bytes <= MAX_RESPONSE_BYTES:
            raise ValueError("max_bytes exceeds the hard response limit")
        self.timeout = timeout
        self.max_bytes = max_bytes
        self._resolver = resolver
        self._tls = ssl.create_default_context()

    def _once(self, url: str):
        parsed = urlsplit(url)
        host = parsed.hostname
        if not host:
            raise SafeNetworkError("HTTPS host is missing.")
        addresses = _public_addresses(host, self._resolver)
        last_error = None
        for family, socktype, proto, sockaddr in addresses:
            raw = socket.socket(family, socktype, proto)
            try:
                raw.settimeout(self.timeout)
                raw.connect(sockaddr)  # connect to the validated, pinned IP
                tls_sock = self._tls.wrap_socket(raw, server_hostname=host)
                raw = None
                path = parsed.path or "/"
                if parsed.query:
                    path += "?" + parsed.query
                request = (
                    f"GET {path} HTTP/1.1\r\n"
                    f"Host: {host}\r\n"
                    f"User-Agent: {USER_AGENT}\r\n"
                    "Accept: text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.1\r\n"
                    "Accept-Encoding: identity\r\n"
                    "Connection: close\r\n\r\n"
                ).encode("ascii")
                tls_sock.sendall(request)
                response = http.client.HTTPResponse(tls_sock)
                response.begin()
                status = response.status
                headers = response.headers
                if status in (301, 302, 303, 307, 308):
                    location = headers.get("Location")
                    response.close()
                    tls_sock.close()
                    return status, location, "", ""
                if status != 200:
                    response.close()
                    tls_sock.close()
                    raise SafeNetworkError(f"Remote server returned HTTP {status}.")
                content_type = headers.get_content_type().lower()
                encoding = headers.get("Content-Encoding", "identity").lower()
                if encoding not in ("", "identity"):
                    response.close()
                    tls_sock.close()
                    raise SafeNetworkError("Compressed or encoded responses are not accepted.")
                length = headers.get("Content-Length")
                if length:
                    try:
                        if int(length) > self.max_bytes:
                            raise SafeNetworkError("Remote response exceeds the size limit.")
                    except ValueError:
                        raise SafeNetworkError("Remote response length is invalid.") from None
                body = response.read(self.max_bytes + 1)
                response.close()
                tls_sock.close()
                if len(body) > self.max_bytes:
                    raise SafeNetworkError("Remote response exceeds the size limit.")
                return status, None, content_type, body.decode("utf-8", errors="replace")
            except (OSError, ssl.SSLError, http.client.HTTPException) as exc:
                last_error = exc
                if raw is not None:
                    raw.close()
        raise SafeNetworkError("Secure connection to public host failed.") from None

    def get_text(self, url: str, *, allowed_hosts: set[str] | None = None):
        current = _validate_https_target(url)
        for _ in range(MAX_REDIRECTS + 1):
            parsed = urlsplit(current)
            host = (parsed.hostname or "").rstrip(".").lower()
            if allowed_hosts is not None and host not in allowed_hosts:
                raise SafeNetworkError("Redirect left the provider's approved host list.")
            status, location, content_type, body = self._once(current)
            if status in (301, 302, 303, 307, 308):
                if not location:
                    raise SafeNetworkError("Redirect response has no destination.")
                current = _validate_https_target(urljoin(current, location))
                continue
            return current, content_type, body
        raise SafeNetworkError("Too many redirects.")


class _VisibleHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title_parts = []
        self.text_parts = []
        self._in_title = False
        self._blocked = 0

    def handle_starttag(self, tag, attrs):
        if tag.lower() in {"script", "style", "noscript", "svg", "iframe", "form"}:
            self._blocked += 1
        if tag.lower() == "title":
            self._in_title = True

    def handle_endtag(self, tag):
        if tag.lower() in {"script", "style", "noscript", "svg", "iframe", "form"}:
            self._blocked = max(0, self._blocked - 1)
        if tag.lower() == "title":
            self._in_title = False
        if tag.lower() in {"p", "div", "br", "li", "h1", "h2", "h3"}:
            self.text_parts.append(" ")

    def handle_data(self, data):
        clean = " ".join(data.split())
        if not clean:
            return
        if self._in_title:
            self.title_parts.append(clean)
        if not self._blocked:
            self.text_parts.append(clean)


class _SearchLinks(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.results = []
        self._current = None
        self._in_result = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = set((attrs.get("class") or "").split())
        if tag == "a" and "result__a" in classes:
            href = attrs.get("href", "")
            self._current = {"href": href, "title": []}
            self._in_result = True

    def handle_data(self, data):
        if self._current is not None and self._in_result:
            self._current["title"].append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._current is not None:
            self.results.append(self._current)
            self._current = None
            self._in_result = False


def _external_result_url(href: str) -> str | None:
    if href.startswith("//"):
        href = "https:" + href
    parsed = urlsplit(href)
    if (parsed.hostname or "").lower().endswith("duckduckgo.com"):
        target = parse_qs(parsed.query).get("uddg", [""])[0]
        href = target
    try:
        return _validate_https_target(href)
    except CapabilityContractError:
        return None


class DuckDuckGoSearchProvider:
    """Public DuckDuckGo HTML search; no API key, cookies, or account required."""

    capability = ReadCapability.WEB_SEARCH

    def __init__(self, client: SafeHTTPSClient | None = None):
        self.client = client or SafeHTTPSClient()

    def read(self, request: ReadRequest) -> ReadResult:
        if not isinstance(request, ReadRequest) or request.capability is not self.capability:
            raise CapabilityContractError("DuckDuckGo provider accepts WEB_SEARCH only.")
        endpoint = "https://html.duckduckgo.com/html/?q=" + quote_plus(request.query)
        _url, content_type, body = self.client.get_text(
            endpoint, allowed_hosts={"html.duckduckgo.com"}
        )
        if "html" not in content_type:
            raise SafeNetworkError("Search provider did not return HTML.")
        parser = _SearchLinks()
        parser.feed(body)
        items = []
        seen = set()
        for entry in parser.results:
            locator = _external_result_url(entry["href"])
            title = " ".join(" ".join(entry["title"]).split())
            if not locator or not title or locator in seen:
                continue
            seen.add(locator)
            items.append(ReadItem(title[:300], locator))
            if len(items) >= request.max_results:
                break
        return ReadResult(self.capability, tuple(items), "DuckDuckGo public search",
                          truncated=len(items) >= request.max_results)


class PublicWebPageReadProvider:
    """Read visible text from one public HTTPS HTML page; no scripts or forms run."""

    capability = ReadCapability.WEB_PAGE_READ

    def __init__(self, client: SafeHTTPSClient | None = None):
        self.client = client or SafeHTTPSClient(max_bytes=MAX_RESPONSE_BYTES)

    def read(self, request: ReadRequest) -> ReadResult:
        if not isinstance(request, ReadRequest) or request.capability is not self.capability:
            raise CapabilityContractError("Page provider accepts WEB_PAGE_READ only.")
        final_url, content_type, body = self.client.get_text(request.target)
        if content_type not in {"text/html", "application/xhtml+xml", "text/plain"}:
            raise SafeNetworkError("Only HTML, XHTML, and plain-text pages are supported.")
        if content_type == "text/plain":
            title, excerpt = final_url, " ".join(body.split())[:2000]
        else:
            parser = _VisibleHTML()
            parser.feed(body)
            title = " ".join(parser.title_parts).strip() or final_url
            excerpt = " ".join(" ".join(parser.text_parts).split())[:2000]
        return ReadResult(self.capability, (ReadItem(title[:300], final_url, excerpt),),
                          "Public HTTPS page", truncated=len(body) >= self.client.max_bytes)


class YouTubePublicSearchProvider:
    """Search public YouTube results HTML; does not authenticate or touch playlists."""

    capability = ReadCapability.YOUTUBE_SEARCH
    _HOSTS = {"www.youtube.com"}

    def __init__(self, client: SafeHTTPSClient | None = None):
        self.client = client or SafeHTTPSClient()

    def read(self, request: ReadRequest) -> ReadResult:
        if not isinstance(request, ReadRequest) or request.capability is not self.capability:
            raise CapabilityContractError("YouTube provider accepts YOUTUBE_SEARCH only.")
        endpoint = "https://www.youtube.com/results?search_query=" + quote_plus(request.query)
        _url, content_type, body = self.client.get_text(endpoint, allowed_hosts=self._HOSTS)
        if "html" not in content_type:
            raise SafeNetworkError("YouTube search did not return HTML.")
        marker = "var ytInitialData = "
        start = body.find(marker)
        if start < 0:
            marker = "ytInitialData = "
            start = body.find(marker)
        if start < 0:
            raise SafeNetworkError("YouTube search response format was not recognized.")
        start += len(marker)
        try:
            data, _end = json.JSONDecoder().raw_decode(body[start:].lstrip())
        except (json.JSONDecodeError, ValueError):
            raise SafeNetworkError("YouTube search data could not be parsed.") from None
        items = []
        seen = set()

        def walk(node):
            if isinstance(node, dict):
                renderer = node.get("videoRenderer")
                if isinstance(renderer, dict):
                    video_id = renderer.get("videoId")
                    title_obj = renderer.get("title", {})
                    runs = title_obj.get("runs", []) if isinstance(title_obj, dict) else []
                    title = " ".join(
                        part.get("text", "") for part in runs if isinstance(part, dict)
                    ).strip()
                    if video_id and len(video_id) <= 32 and video_id not in seen and title:
                        seen.add(video_id)
                        items.append(ReadItem(
                            title[:300], "https://www.youtube.com/watch?v=" + video_id
                        ))
                for value in node.values():
                    walk(value)
            elif isinstance(node, list):
                for value in node:
                    walk(value)

        walk(data)
        return ReadResult(self.capability, tuple(items[:request.max_results]),
                          "YouTube public search", truncated=len(items) > request.max_results)
