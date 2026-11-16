"""Fail-closed global APAA owner identity guard.

The caller must supply server-side deployment configuration and a trusted
OIDC issuer allowlist. Never pass browser, task, query-string or model data.
This module does not authenticate users or implement recovery/re-key.
"""
from __future__ import annotations

from collections.abc import Collection, Mapping
from dataclasses import dataclass
from hashlib import sha256
from urllib.parse import urlsplit

from core.identity import (
    AuthorizationDenied,
    Principal,
    require_authenticated,
)


class GlobalOwnerConfigurationError(ValueError):
    """Raised when global-owner configuration is absent or invalid."""


@dataclass(frozen=True)
class GlobalOwnerConfig:
    """Immutable exact OIDC issuer + subject binding for the APAA owner."""

    issuer: str
    subject: str

    @property
    def generation(self) -> str:
        """Opaque stable identifier for invalidating owner-bound cached state."""
        material = (self.issuer + "\0" + self.subject).encode("utf-8")
        return sha256(material).hexdigest()

    @property
    def owner_fingerprint(self) -> str:
        """Opaque audit identifier; never use it as an authorization key."""
        return self.generation


def _valid_https_issuer(value: str) -> bool:
    if not value or value != value.strip() or any(ch.isspace() for ch in value):
        return False
    try:
        parsed = urlsplit(value)
        return (
            parsed.scheme == "https"
            and bool(parsed.netloc)
            and parsed.hostname is not None
            and parsed.username is None
            and parsed.password is None
            and parsed.query == ""
            and parsed.fragment == ""
        )
    except ValueError:
        return False


def load_global_owner_config(
    source: Mapping[str, object] | None,
    *,
    trusted_issuers: Collection[str],
) -> GlobalOwnerConfig:
    """Validate a server-supplied config mapping against trusted OIDC issuers.

    There is deliberately no first-login fallback and no environment/browser
    lookup here. The deployment adapter owns secure loading and strict parsing.
    """
    if not isinstance(source, Mapping):
        raise GlobalOwnerConfigurationError("Global owner is not provisioned.")
    if set(source.keys()) != {"issuer", "subject"}:
        raise GlobalOwnerConfigurationError("Global owner configuration fields are invalid.")
    issuer = source.get("issuer")
    subject = source.get("subject")
    if type(issuer) is not str or not _valid_https_issuer(issuer):
        raise GlobalOwnerConfigurationError("Global owner issuer must be a valid HTTPS issuer.")
    if not isinstance(trusted_issuers, Collection) or issuer not in trusted_issuers:
        raise GlobalOwnerConfigurationError("Global owner issuer is not in the trusted issuer allowlist.")
    if (
        type(subject) is not str
        or not subject
        or subject != subject.strip()
        or len(subject) > 255
        or not subject.isascii()
        or any(ord(ch) < 0x21 or ord(ch) > 0x7E for ch in subject)
    ):
        raise GlobalOwnerConfigurationError("Global owner subject is invalid.")
    return GlobalOwnerConfig(issuer=issuer, subject=subject)


def is_global_owner(
    principal: Principal | None,
    config: GlobalOwnerConfig | None,
) -> bool:
    """Return true only for an authenticated exact issuer + subject match."""
    if not isinstance(config, GlobalOwnerConfig):
        return False
    try:
        verified = require_authenticated(principal)
    except (PermissionError, TypeError, ValueError):
        return False
    return verified.issuer == config.issuer and verified.subject == config.subject


def require_global_owner(
    principal: Principal | None,
    config: GlobalOwnerConfig | None,
) -> Principal:
    """Fail-closed server-side guard for every global-owner-only operation."""
    if not is_global_owner(principal, config):
        raise AuthorizationDenied("The configured APAA global owner is required.")
    return require_authenticated(principal)
