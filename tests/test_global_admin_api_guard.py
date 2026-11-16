from __future__ import annotations

import pytest

from core.global_admin_api_guard import GlobalAdminRequestAuthorizer
from core.global_owner import GlobalOwnerConfig, GlobalOwnerConfigurationError
from core.identity import AuthorizationDenied, Principal


ISSUER = "https://accounts.example.test"
OWNER = Principal("owner-subject", ISSUER, True)
OTHER = Principal("other-subject", ISSUER, True)
UNAUTHENTICATED = Principal("owner-subject", ISSUER, False)


def make_guard(config_loader):
    config = config_loader()
    generation = {"value": config.generation if isinstance(config, GlobalOwnerConfig) else None}
    return (
        GlobalAdminRequestAuthorizer(config_loader, lambda: generation["value"]),
        generation,
    )


def test_each_request_uses_fresh_server_side_owner_configuration_and_durable_generation():
    current = {"config": GlobalOwnerConfig(ISSUER, OWNER.subject)}
    guard, durable = make_guard(lambda: current["config"])
    assert guard.authorize(OWNER) is OWNER

    current["config"] = GlobalOwnerConfig(ISSUER, OTHER.subject)
    # Config alone is insufficient: until the durable high-water mark is
    # changed by the operator CAS workflow, all privileged requests fail closed.
    with pytest.raises(AuthorizationDenied):
        guard.authorize(OTHER)

    durable["value"] = current["config"].generation
    assert guard.authorize(OTHER) is OTHER
    with pytest.raises(AuthorizationDenied):
        guard.authorize(OWNER)


@pytest.mark.parametrize("config", [None, object()])
def test_unprovisioned_or_invalid_config_denies(config):
    guard = GlobalAdminRequestAuthorizer(lambda: config, lambda: None)
    with pytest.raises(AuthorizationDenied):
        guard.authorize(OWNER)


def test_config_loader_failure_denies_without_leaking_details():
    def broken_loader():
        raise GlobalOwnerConfigurationError("secret config detail")

    guard = GlobalAdminRequestAuthorizer(broken_loader, lambda: None)
    with pytest.raises(AuthorizationDenied) as exc:
        guard.authorize(OWNER)
    assert "secret config detail" not in str(exc.value)


def test_generation_reader_failure_or_stale_value_denies():
    config = GlobalOwnerConfig(ISSUER, OWNER.subject)
    def broken_reader():
        raise RuntimeError("private database detail")

    with pytest.raises(AuthorizationDenied):
        GlobalAdminRequestAuthorizer(lambda: config, broken_reader).authorize(OWNER)
    with pytest.raises(AuthorizationDenied):
        GlobalAdminRequestAuthorizer(lambda: config, lambda: "0" * 64).authorize(OWNER)


@pytest.mark.parametrize("principal", [None, OTHER, UNAUTHENTICATED])
def test_non_owner_and_unauthenticated_requests_are_denied(principal):
    config = GlobalOwnerConfig(ISSUER, OWNER.subject)
    guard = GlobalAdminRequestAuthorizer(lambda: config, lambda: config.generation)
    with pytest.raises(AuthorizationDenied):
        guard.authorize(principal)


def test_constructor_rejects_missing_trusted_readers():
    with pytest.raises(TypeError):
        GlobalAdminRequestAuthorizer(None, lambda: None)
    with pytest.raises(TypeError):
        GlobalAdminRequestAuthorizer(lambda: None, None)
