import pytest

from core.identity import (
    AuthenticationRequired,
    AuthorizationDenied,
    Principal,
    require_authenticated,
    require_project_owner,
)


def test_require_authenticated_accepts_trusted_identity():
    principal = Principal(
        subject="user-123",
        issuer="https://identity.example.test",
        authenticated=True,
        roles=("user",),
    )
    assert require_authenticated(principal) is principal


@pytest.mark.parametrize(
    "principal",
    [
        None,
        {"subject": "user-123", "issuer": "issuer", "authenticated": True},
        Principal("user-123", "issuer", False),
        Principal("", "issuer", True),
        Principal("user-123", "", True),
        Principal("user-123", "issuer", True, roles=("user", 3)),
        Principal("user-123", "issuer", True, roles=["user"]),
    ],
)
def test_require_authenticated_fails_closed_for_untrusted_or_malformed_identity(principal):
    with pytest.raises(AuthenticationRequired):
        require_authenticated(principal)


def test_project_owner_check_accepts_matching_authenticated_subject():
    principal = Principal("alice", "https://issuer.example.test", True)
    assert require_project_owner(principal, "alice") is principal


@pytest.mark.parametrize(
    "principal,owner",
    [
        (None, "alice"),
        (Principal("alice", "issuer", False), "alice"),
        (Principal("bob", "issuer", True), "alice"),
        (Principal("alice", "issuer", True), None),
        (Principal("alice", "issuer", True), ""),
    ],
)
def test_project_owner_check_denies_missing_auth_or_non_owner(principal, owner):
    with pytest.raises((AuthenticationRequired, AuthorizationDenied)):
        require_project_owner(principal, owner)
