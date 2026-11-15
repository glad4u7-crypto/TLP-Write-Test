"""Strict adapter for Streamlit's verified OIDC user claims.

Streamlit validates the OIDC flow and exposes the parsed ID-token claims through
st.user. This module validates required claims and expiry before constructing a
Principal. It does not replace identity-provider configuration or authorization.
"""
import math
import time
from typing import Any, Mapping

from core.identity import AuthenticationRequired, Principal, require_authenticated


class OIDCIdentityError(ValueError):
    """Raised when Streamlit's OIDC identity claims are missing or invalid."""


def _is_finite_number(value: Any) -> bool:
    """Return False for non-finite values and integers too large for float conversion."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def principal_from_oidc_claims(
    claims: Mapping[str, Any] | None,
    *,
    now: float | None = None,
    clock_skew_seconds: int = 60,
) -> Principal:
    """Convert trusted Streamlit OIDC claims to a validated principal."""
    if not isinstance(clock_skew_seconds, int) or isinstance(clock_skew_seconds, bool) or clock_skew_seconds < 0:
        raise OIDCIdentityError("OIDC clock skew must be a non-negative integer.")
    if now is not None and not _is_finite_number(now):
        raise OIDCIdentityError("OIDC validation time is invalid.")
    if not isinstance(claims, Mapping):
        raise AuthenticationRequired("OIDC identity claims are unavailable.")
    if claims.get("is_logged_in") is not True:
        raise AuthenticationRequired("Log in through the configured OIDC provider.")
    issuer = claims.get("iss")
    subject = claims.get("sub")
    expires_at = claims.get("exp")
    issued_at = claims.get("iat")
    if not isinstance(issuer, str) or not issuer.strip():
        raise OIDCIdentityError("OIDC issuer claim is missing.")
    if not isinstance(subject, str) or not subject.strip():
        raise OIDCIdentityError("OIDC subject claim is missing.")
    if not _is_finite_number(expires_at):
        raise OIDCIdentityError("OIDC expiration claim is invalid.")
    if not _is_finite_number(issued_at):
        raise OIDCIdentityError("OIDC issued-at claim is invalid.")
    current_time = time.time() if now is None else now
    if expires_at <= current_time - clock_skew_seconds:
        raise AuthenticationRequired("OIDC identity has expired; log in again.")
    if issued_at > current_time + clock_skew_seconds:
        raise AuthenticationRequired("OIDC identity was issued in the future.")
    principal = Principal(
        subject=subject.strip(),
        issuer=issuer.strip(),
        authenticated=True,
        roles=(),
    )
    return require_authenticated(principal)
