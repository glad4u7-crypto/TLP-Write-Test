import json
import socket

import pytest

from core.capabilities import ReadCapability, ReadRequest
from core.read_only_adapters import ReadOnlyAdapterRegistry
from core.safe_network_providers import (
    DuckDuckGoSearchProvider,
    PublicWebPageReadProvider,
    SafeHTTPSClient,
    SafeNetworkError,
    YouTubePublicSearchProvider,
)


class FakeClient:
    max_bytes = 100000

    def __init__(self, url, content_type, body):
        self.response = (url, content_type, body)
        self.allowed = None

    def get_text(self, url, *, allowed_hosts=None):
        self.allowed = allowed_hosts
        return self.response


def test_dns_rejects_private_or_mixed_public_private_answers():
    public = (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))
    private = (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))
    client = SafeHTTPSClient(resolver=lambda *a, **k: [public, private])
    with pytest.raises(SafeNetworkError):
        client._once("https://example.org/")


def test_dns_rejects_empty_and_private_answers():
    private = (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.8", 443))
    client = SafeHTTPSClient(resolver=lambda *a, **k: [private])
    with pytest.raises(SafeNetworkError):
        client._once("https://example.org/")


def test_redirect_revalidation_rejects_http_and_local_redirects():
    class RedirectClient(SafeHTTPSClient):
        def __init__(self, location):
            super().__init__()
            self.location = location
        def _once(self, url):
            return 302, self.location, "", ""

    with pytest.raises(Exception):
        RedirectClient("http://127.0.0.1/admin").get_text("https://example.org")
    with pytest.raises(Exception):
        RedirectClient("https://localhost/admin").get_text("https://example.org")


def test_redirects_cannot_leave_fixed_search_provider_hosts():
    class RedirectClient(SafeHTTPSClient):
        def _once(self, url):
            return 302, "https://attacker.example/collect", "", ""

    with pytest.raises(SafeNetworkError):
        RedirectClient().get_text(
            "https://html.duckduckgo.com/html/?q=x",
            allowed_hosts={"html.duckduckgo.com"},
        )


def test_duckduckgo_search_extracts_only_https_external_links():
    body = '''
    <a class="result__a" href="https://example.org/a">Example result</a>
    <a class="result__a" href="http://bad.example/">HTTP blocked</a>
    <a class="result__a" href="https://localhost/private">Local blocked</a>
    '''
    client = FakeClient("https://html.duckduckgo.com/html/", "text/html", body)
    result = DuckDuckGoSearchProvider(client).read(
        ReadRequest(ReadCapability.WEB_SEARCH, query="safe search", max_results=5)
    )
    assert len(result.items) == 1
    assert result.items[0].locator == "https://example.org/a"
    assert client.allowed == {"html.duckduckgo.com"}


def test_public_page_reader_strips_scripts_forms_and_bounds_excerpt():
    html = """<html><head><title>Public Page</title><script>secret()</script></head>
    <body><p>Visible text</p><form><p>Do not include</p></form></body></html>"""
    client = FakeClient("https://example.org/", "text/html", html)
    result = PublicWebPageReadProvider(client).read(
        ReadRequest(ReadCapability.WEB_PAGE_READ, target="https://example.org/")
    )
    assert result.items[0].title == "Public Page"
    assert "Visible text" in result.items[0].excerpt
    assert "secret" not in result.items[0].excerpt
    assert "Do not include" not in result.items[0].excerpt


def test_youtube_search_extracts_video_ids_and_never_playlist_actions():
    data = {
        "contents": {
            "videoRenderer": {
                "videoId": "abcdefghijk",
                "title": {"runs": [{"text": "Public video title"}]},
            }
        }
    }
    html = "var ytInitialData = " + json.dumps(data) + ";"
    client = FakeClient("https://www.youtube.com/results", "text/html", html)
    result = YouTubePublicSearchProvider(client).read(
        ReadRequest(ReadCapability.YOUTUBE_SEARCH, query="APAA", max_results=3)
    )
    assert result.items[0].title == "Public video title"
    assert result.items[0].locator == "https://www.youtube.com/watch?v=abcdefghijk"
    assert client.allowed == {"www.youtube.com"}
    assert not hasattr(YouTubePublicSearchProvider, "save_to_playlist")


def test_real_providers_are_read_only_and_capability_scoped():
    registry = ReadOnlyAdapterRegistry((
        DuckDuckGoSearchProvider(FakeClient("https://html.duckduckgo.com", "text/html", "")),
        PublicWebPageReadProvider(FakeClient("https://example.org", "text/html", "<title>x</title>")),
        YouTubePublicSearchProvider(FakeClient("https://www.youtube.com/results", "text/html",
            "var ytInitialData = {}")),
    ))
    assert registry.read(ReadRequest(ReadCapability.WEB_SEARCH, query="x")).items == ()
    assert not hasattr(registry, "write")
    assert not hasattr(registry, "execute")
