"""Offline, fail-closed policy primitives for a future isolated browser worker.

This module performs no DNS lookups, network requests, browser startup, or I/O.
A deployment must still enforce destination policy at connection time (egress
proxy/firewall) to prevent DNS rebinding and time-of-check/time-of-use attacks.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import ipaddress
import re
from collections.abc import Callable, Mapping, Sequence
from urllib.parse import urljoin, urlsplit, urlunsplit


class BrowserPolicyError(ValueError):
    """Raised when an untrusted browser job or destination violates policy."""


_ALLOWED_ACTIONS = frozenset({
    "navigate_exact_origin",
    "read_visible_text",
    "read_page_title",
    "read_link_metadata",
    "capture_transient_screenshot",
})
_JOB_FIELDS = frozenset({
    "job_id", "url", "allowed_origins", "action", "expires_at",
    "max_response_bytes", "max_runtime_seconds",
})
_JOB_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{7,127}$")
_DNS_LABEL = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
_MAX_URL_LENGTH = 2048
_MAX_ORIGINS = 20
_MAX_RESPONSE_BYTES = 2_000_000
_MAX_RUNTIME_SECONDS = 60


@dataclass(frozen=True)
class CanonicalURL:
    """Normalized HTTPS URL and its exact origin."""

    url: str
    origin: str
    hostname: str
    port: int


@dataclass(frozen=True)
class BrowserJob:
    """Validated immutable read-only browser job envelope."""

    job_id: str
    url: str
    allowed_origins: tuple[str, ...]
    action: str
    expires_at: int
    max_response_bytes: int
    max_runtime_seconds: int


Resolver = Callable[[str], Sequence[str]]


def _canonical_host(host: str) -> tuple[str, int | None]:
    if not host or "%" in host or "\\" in host:
        raise BrowserPolicyError("Destination host is malformed.")
    if host.endswith(".."):
        raise BrowserPolicyError("Destination host is malformed.")
    candidate = host[:-1] if host.endswith(".") else host

    # IP literals are parsed before IDNA; zone identifiers are never accepted.
    try:
        address = ipaddress.ip_address(candidate)
    except ValueError:
        address = None
    if address is not None:
        if not address.is_global:
            raise BrowserPolicyError("Private, reserved, or special-use IP destinations are blocked.")
        return address.compressed.lower(), address.version

    try:
        ascii_host = candidate.encode("idna").decode("ascii").lower()
    except UnicodeError as exc:
        raise BrowserPolicyError("Destination hostname is not valid IDNA.") from exc
    if len(ascii_host) > 253 or not ascii_host:
        raise BrowserPolicyError("Destination hostname is too long or empty.")
    labels = ascii_host.split(".")
    if len(labels) < 2 or any(not _DNS_LABEL.fullmatch(label) for label in labels):
        raise BrowserPolicyError("Destination must be a fully-qualified DNS hostname.")
    return ascii_host, None


def canonicalize_https_url(value: object) -> CanonicalURL:
    """Canonicalize an HTTPS URL without resolving its hostname."""
    if type(value) is not str or not value or len(value) > _MAX_URL_LENGTH:
        raise BrowserPolicyError("URL must be a non-empty string within the length limit.")
    if value != value.strip() or any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise BrowserPolicyError("Whitespace or control characters are not allowed in URLs.")
    if "\\" in value:
        raise BrowserPolicyError("Backslashes are not allowed in URLs.")

    try:
        parsed = urlsplit(value)
        if parsed.scheme.lower() != "https":
            raise BrowserPolicyError("Only HTTPS destinations are permitted.")
        if not parsed.netloc or parsed.username is not None or parsed.password is not None:
            raise BrowserPolicyError("URL authority is missing or contains user information.")
        host, ip_version = _canonical_host(parsed.hostname or "")
        port = parsed.port or 443
    except (ValueError, UnicodeError) as exc:
        if isinstance(exc, BrowserPolicyError):
            raise
        raise BrowserPolicyError("URL authority or port is malformed.") from exc

    if not 1 <= port <= 65535:
        raise BrowserPolicyError("Destination port is invalid.")
    if ip_version is not None:
        # _canonical_host already rejects non-global literals.
        host_for_netloc = f"[{host}]" if ip_version == 6 else host
    else:
        host_for_netloc = host
    origin = f"https://{host_for_netloc}" + (f":{port}" if port != 443 else "")
    path = parsed.path or "/"
    canonical_url = urlunsplit(("https", host_for_netloc + (f":{port}" if port != 443 else ""),
                                path, parsed.query, ""))
    return CanonicalURL(canonical_url, origin, host, port)


def validate_dns_answers(hostname: str, answers: Sequence[str]) -> tuple[str, ...]:
    """Validate injected DNS answers; performs no resolver/network operation.

    Every answer must be a globally routable unicast address. Mixed public and
    private answer sets are rejected rather than partially accepted.
    """
    if not isinstance(answers, Sequence) or isinstance(answers, (str, bytes)) or not answers:
        raise BrowserPolicyError("DNS returned no usable addresses.")
    normalized: list[str] = []
    for answer in answers:
        if type(answer) is not str:
            raise BrowserPolicyError("DNS answer has an invalid type.")
        try:
            address = ipaddress.ip_address(answer)
        except ValueError as exc:
            raise BrowserPolicyError("DNS answer is not an IP address.") from exc
        if not address.is_global:
            raise BrowserPolicyError("DNS answer includes a private or special-use address.")
        normalized.append(address.compressed.lower())
    return tuple(sorted(set(normalized)))


def validate_destination(
    value: object,
    allowed_origins: Sequence[str],
    *,
    resolver: Resolver | None = None,
) -> CanonicalURL:
    """Validate URL against an exact-origin allowlist and optional test resolver."""
    target = canonicalize_https_url(value)
    if not isinstance(allowed_origins, Sequence) or isinstance(allowed_origins, (str, bytes)):
        raise BrowserPolicyError("Allowed origins must be a sequence.")
    if not 1 <= len(allowed_origins) <= _MAX_ORIGINS:
        raise BrowserPolicyError("Origin allowlist is empty or exceeds its limit.")

    canonical_origins: set[str] = set()
    for item in allowed_origins:
        origin = canonicalize_https_url(item)
        if origin.url != origin.origin + "/" and origin.url != origin.origin:
            raise BrowserPolicyError("Allowlist entries must be origins, not paths or queries.")
        canonical_origins.add(origin.origin)
    if target.origin not in canonical_origins:
        raise BrowserPolicyError("Destination is not an exact approved origin.")

    try:
        literal = ipaddress.ip_address(target.hostname)
    except ValueError:
        literal = None
    if resolver is not None and literal is None:
        try:
            answers = resolver(target.hostname)
        except Exception as exc:
            raise BrowserPolicyError("DNS resolution failed closed.") from exc
        validate_dns_answers(target.hostname, answers)
    return target


def validate_redirect(
    current_url: str,
    location: str,
    allowed_origins: Sequence[str],
    *,
    resolver: Resolver | None = None,
) -> CanonicalURL:
    """Resolve one redirect and re-apply the full URL/origin/DNS policy."""
    if type(location) is not str or not location or len(location) > _MAX_URL_LENGTH:
        raise BrowserPolicyError("Redirect location is invalid.")
    try:
        next_url = urljoin(current_url, location)
    except ValueError as exc:
        raise BrowserPolicyError("Redirect location is malformed.") from exc
    return validate_destination(next_url, allowed_origins, resolver=resolver)


def validate_browser_job(
    raw: object,
    *,
    now: int | None = None,
    resolver: Resolver | None = None,
) -> BrowserJob:
    """Validate a closed-schema, read-only job. Unknown keys always fail."""
    if not isinstance(raw, Mapping):
        raise BrowserPolicyError("Browser job must be a mapping.")
    if set(raw.keys()) != _JOB_FIELDS:
        missing = sorted(_JOB_FIELDS - set(raw.keys()))
        unknown = sorted(set(raw.keys()) - _JOB_FIELDS)
        raise BrowserPolicyError(f"Job schema mismatch (missing={missing}, unknown={unknown}).")

    job_id = raw["job_id"]
    if type(job_id) is not str or not _JOB_ID.fullmatch(job_id):
        raise BrowserPolicyError("Job ID is invalid.")
    action = raw["action"]
    if type(action) is not str or action not in _ALLOWED_ACTIONS:
        raise BrowserPolicyError("Unknown or prohibited browser action.")
    expires_at = raw["expires_at"]
    current_time = int(datetime.now(timezone.utc).timestamp()) if now is None else now
    if type(expires_at) is not int or expires_at <= current_time or expires_at > current_time + 300:
        raise BrowserPolicyError("Job expiry must be in the next five minutes.")
    max_bytes = raw["max_response_bytes"]
    max_runtime = raw["max_runtime_seconds"]
    if type(max_bytes) is not int or not 1 <= max_bytes <= _MAX_RESPONSE_BYTES:
        raise BrowserPolicyError("Response byte limit is outside the permitted range.")
    if type(max_runtime) is not int or not 1 <= max_runtime <= _MAX_RUNTIME_SECONDS:
        raise BrowserPolicyError("Runtime limit is outside the permitted range.")

    origins = raw["allowed_origins"]
    if not isinstance(origins, list) or not 1 <= len(origins) <= _MAX_ORIGINS:
        raise BrowserPolicyError("Allowed origins must be a bounded list.")
    canonical_origins: list[str] = []
    for origin_value in origins:
        parsed_origin = canonicalize_https_url(origin_value)
        if parsed_origin.url not in (parsed_origin.origin, parsed_origin.origin + "/"):
            raise BrowserPolicyError("Allowed origins cannot contain paths or queries.")
        canonical_origins.append(parsed_origin.origin)
    if len(set(canonical_origins)) != len(canonical_origins):
        raise BrowserPolicyError("Duplicate origins are not permitted.")

    target = validate_destination(raw["url"], canonical_origins, resolver=resolver)
    return BrowserJob(
        job_id=job_id,
        url=target.url,
        allowed_origins=tuple(canonical_origins),
        action=action,
        expires_at=expires_at,
        max_response_bytes=max_bytes,
        max_runtime_seconds=max_runtime,
    )
