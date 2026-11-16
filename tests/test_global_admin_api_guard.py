from __future__ import annotations

import pytest

from core.global_admin_api_guard import GlobalAdminRequestAuthorizer
from core.global_owner import GlobalOwnerConfig, GlobalOwnerConfigurationError
from core.identity import AuthorizationDenied, Principal


ISSUER = "https://accounts.example.test"
OWNER = Principal("owner-subject", ISSUER, True)
OTHER = Principal("other-subject", ISSUER, True)
UNAUTHENTICATED = Principal("owner-subject", ISSUER, False)


def test_each_request_uses_fresh_server_side_owner_configuration():
    current = {"config": GlobalOwnerConfig(ISSUER, OWNER.subject)}
    guard = GlobalAdminRequestAuthorizer(lambda: current["config"])

    assert guard.authorize(OWNER) is OWNER
    current["config"] = GlobalOwnerConfig(ISSUER, OTHER.subject)

    # Re-key is effective on the next request; no cached owner decision.
    assert guard.authorize(OTHER) is OTHER
    with pytest.raises(AuthorizationDenied):
        guard.authorize(OWNER)


@pytest.mark.parametrize("config", [None, object()])
def test_unprovisioned_or_invalid_config_denies(config):
    guard = GlobalAdminRequestAuthorizer(lambda: config)
    with pytest.raises(AuthorizationDenied):
        guard.authorize(OWNER)


def test_config_loader_failure_denies_without_leaking_details():
    def broken_loader():
        raise GlobalOwnerConfigurationError("secret config detail")

    guard = GlobalAdminRequestAuthorizer(broken_loader)
    with pytest.raises(AuthorizationDenied) as exc:
        guard.authorize(OWNER)
    assert "secret config detail" not in str(exc.value)


def test_unexpected_config_loader_runtime_failure_denies():
    def broken_loader():
        raise RuntimeError("private backend detail")

    guard = GlobalAdminRequestAuthorizer(broken_loader)
    with pytest.raises(AuthorizationDenied):
        guard.authorize(OWNER)


@pytest.mark.parametrize("principal", [None, OTHER, UNAUTHENTICATED])
def test_non_owner_and_unauthenticated_requests_are_denied(principal):
    guard = GlobalAdminRequestAuthorizer(
        lambda: GlobalOwnerConfig(ISSUER, OWNER.subject)
    )
    with pytest.raises(AuthorizationDenied):
        guard.authorize(principal)


def test_constructor_rejects_untrusted_loader_shape():
    with pytest.raises(TypeError):
        GlobalAdminRequestAuthorizer(None)
