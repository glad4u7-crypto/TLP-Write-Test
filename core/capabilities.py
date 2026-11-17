"""Typed, fail-closed contracts for Personal Edition read-only capabilities.

This module defines data boundaries only. It performs no network, browser,
filesystem, YouTube, or external-provider operations and registers no handlers.
"""
from dataclasses import dataclass
from enum import Enum
from ipaddress import ip_address
import re
from urllib.parse import urlsplit


MAX_QUERY_LENGTH = 1000
MAX_RESULT_ITEMS = 20
MAX_TITLE_LENGTH = 300
MAX_EXCERPT_LENGTH = 2000
MAX_SOURCE_LABEL_LENGTH = 120


class CapabilityContractError(ValueError):
    """Raised when a read-only capability request/result violates its contract."""


class ReadCapability(str, Enum):
    WEB_SEARCH = "web_search"
    WEB_PAGE_READ = "web_page_read"
    FILE_INSPECT = "file_inspect"
    YOUTUBE_SEARCH = "youtube_search"


def _validate_https_target(value: object, *, youtube_only: bool = False) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise CapabilityContractError("A trimmed HTTPS target is required.")
    if len(value) > 2048 or any(ord(ch) < 32 for ch in value):
        raise CapabilityContractError("Target URL is invalid or too long.")
    try:
        parsed = urlsplit(value)
        port = parsed.port
        host = parsed.hostname
    except ValueError as exc:
        raise CapabilityContractError("Target URL is malformed.") from exc
    if parsed.scheme.lower() != "https" or not host or parsed.username or parsed.password:
        raise CapabilityContractError("Only credential-free HTTPS URLs are allowed.")
    if port not in (None, 443):
        raise CapabilityContractError("Only the default HTTPS port is allowed.")
    host = host.rstrip(".").lower()
    if host in {"localhost", "localhost.localdomain"} or host.endswith(
        (".localhost", ".local", ".internal", ".test", ".invalid", ".onion")
    ):
        raise CapabilityContractError("Local and reserved hostnames are not allowed.")
    try:
        ip_address(host)
    except ValueError:
        pass
    else:
        raise CapabilityContractError("IP-literal URLs are not allowed.")
    if youtube_only and host not in {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"}:
        raise CapabilityContractError("YouTube search results must use an approved YouTube host.")
    return value


def _validate_project_relative_path(value: object) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise CapabilityContractError("A project-relative file path is required.")
    if len(value) > 1024 or "\x00" in value or "\\" in value:
        raise CapabilityContractError("File path is invalid.")
    parts = value.split("/")
    if value.startswith("/") or re.match(r"^[A-Za-z]:", value) or any(
        part in {"", ".", ".."} for part in parts
    ):
        raise CapabilityContractError("File path must stay within the selected project.")
    return value


@dataclass(frozen=True)
class ReadRequest:
    """A request for a bounded read-only capability; never an execution command."""

    capability: ReadCapability
    query: str = ""
    target: str = ""
    project_id: str = ""
    max_results: int = 10

    def __post_init__(self) -> None:
        if not isinstance(self.capability, ReadCapability):
            raise CapabilityContractError("Capability must be an exact ReadCapability value.")
        if type(self.max_results) is not int or not 1 <= self.max_results <= MAX_RESULT_ITEMS:
            raise CapabilityContractError("max_results must be an integer from 1 to 20.")
        if not isinstance(self.query, str) or len(self.query) > MAX_QUERY_LENGTH:
            raise CapabilityContractError("Query must be text of at most 1000 characters.")
        if self.query != self.query.strip():
            raise CapabilityContractError("Query must be trimmed.")
        if not isinstance(self.target, str) or not isinstance(self.project_id, str):
            raise CapabilityContractError("Target and project_id must be text.")

        if self.capability in {ReadCapability.WEB_SEARCH, ReadCapability.YOUTUBE_SEARCH}:
            if not self.query:
                raise CapabilityContractError("Search capabilities require a non-empty query.")
            if self.target or self.project_id:
                raise CapabilityContractError("Search requests cannot select a URL or project.")
        elif self.capability is ReadCapability.WEB_PAGE_READ:
            if self.query or self.project_id:
                raise CapabilityContractError("Page-read requests accept only a target URL.")
            _validate_https_target(self.target)
        elif self.capability is ReadCapability.FILE_INSPECT:
            if (
                self.query
                or not self.project_id
                or self.project_id != self.project_id.strip()
                or len(self.project_id) > 128
                or any(ord(ch) < 32 for ch in self.project_id)
            ):
                raise CapabilityContractError("File inspection requires a bounded project_id and no query.")
            _validate_project_relative_path(self.target)


@dataclass(frozen=True)
class ReadItem:
    """A bounded text result; raw HTML, scripts, and executable payloads are excluded."""

    title: str
    locator: str
    excerpt: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.title, str) or not self.title.strip() or len(self.title) > MAX_TITLE_LENGTH:
            raise CapabilityContractError("Result title must be non-empty text within the size limit.")
        if not isinstance(self.locator, str) or not self.locator or len(self.locator) > 2048:
            raise CapabilityContractError("Result locator is invalid.")
        if not isinstance(self.excerpt, str) or len(self.excerpt) > MAX_EXCERPT_LENGTH:
            raise CapabilityContractError("Result excerpt exceeds the text limit.")


@dataclass(frozen=True)
class ReadResult:
    """A bounded, display-safe result set tied to one read-only capability."""

    capability: ReadCapability
    items: tuple[ReadItem, ...]
    source_label: str
    truncated: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.capability, ReadCapability):
            raise CapabilityContractError("Result capability must be exact.")
        if not isinstance(self.items, tuple) or len(self.items) > MAX_RESULT_ITEMS:
            raise CapabilityContractError("Result items must be a bounded tuple.")
        if any(not isinstance(item, ReadItem) for item in self.items):
            raise CapabilityContractError("Every result item must be a ReadItem.")
        if not isinstance(self.source_label, str) or not self.source_label.strip() or len(self.source_label) > MAX_SOURCE_LABEL_LENGTH:
            raise CapabilityContractError("A bounded source label is required.")
        if type(self.truncated) is not bool:
            raise CapabilityContractError("truncated must be a boolean.")
        for item in self.items:
            if self.capability is ReadCapability.FILE_INSPECT:
                _validate_project_relative_path(item.locator)
            else:
                _validate_https_target(
                    item.locator,
                    youtube_only=self.capability is ReadCapability.YOUTUBE_SEARCH,
                )
