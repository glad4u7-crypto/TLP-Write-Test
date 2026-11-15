"""Fail-closed identity primitives for the APAA authorization boundary.

These helpers validate an identity asserted by a trusted authentication adapter.
They do not authenticate users, validate OIDC tokens, or secure Streamlit cookies.
Do not construct Principal objects from task text, query parameters, or client input.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Principal:
    """Identity asserted by a trusted authentication middleware/adapter."""

    subject: str
    issuer: str
    authenticated: bool
    roles: tuple[str, ...] = ()


class AuthenticationRequired(PermissionError):
    """Raised when an action has no trusted authenticated principal."""


class AuthorizationDenied(PermissionError):
    """Raised when a principal lacks permission for a resource."""


def require_authenticated(principal: Principal | None) -> Principal:
    """Return a validated principal or fail closed."""
    if not isinstance(principal, Principal):
        raise AuthenticationRequired("An authenticated identity is required.")
    if principal.authenticated is not True:
        raise AuthenticationRequired("The identity is not authenticated.")
    if (
        not isinstance(principal.subject, str)
        or not principal.subject.strip()
        or not isinstance(principal.issuer, str)
        or not principal.issuer.strip()
    ):
        raise AuthenticationRequired("The identity is missing a trusted subject or issuer.")
    if not isinstance(principal.roles, tuple) or any(
        not isinstance(role, str) or not role.strip()
        for role in principal.roles
    ):
        raise AuthenticationRequired("The identity roles are malformed.")
    return principal


def require_project_owner(
    principal: Principal | None,
    owner_subject: str | None,
    owner_issuer: str | None = None,
) -> Principal:
    """Require an authenticated principal to own a project."""
    verified = require_authenticated(principal)
    if owner_issuer is not None and verified.issuer != owner_issuer:
        raise AuthorizationDenied("The authenticated issuer does not own this project.")
    if (
        not isinstance(owner_subject, str
        or not owner_subject.strip()
        or verified.subject != owner_subject
    ):
        raise AuthorizationDenied("The authenticated user does not own this project.")
    return verified
