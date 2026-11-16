from __future__ import annotations

import pytest

from core.global_owner import (
    GlobalOwnerConfigurationError,
    GlobalOwnerConfig,
    is_global_owner,
    load_global_owner_config,
    require_global_owner,
)
from core.identity import AuthorizationDenied, Principal


ISSUER = "https://identity.example/tenant"
OWNER = Principal("owner-opaque-subject", ISSUER, True)
OTHER_SUBJECT = Principal("another-subject", ISSUER, True)
OTHER_ISSUER = Principal("owner-opaque-subject", "https://other.example", True)


def test_loads_exact_server_config_from_trusted_issuer():
    config = load_global_owner_config(
        {"issuer": ISSUER, "subject": OWNER.subject},
        trusted_issuers=(ISSUER,),
    )
    assert config == GlobalOwnerConfig(ISSUER, OWNER.subject)
    assert len(config.generation) == 64


@pytest.mark.parametrize(
    "source",
    [
        None,
        {},
        {"issuer": ISSUER},
        {"issuer": ISSUER, "subject": "owner", "role": "admin"},
        {"issuer": "http://identity.example", "subject": "owner"},
        {"issuer": "https://user:pass@identity.example", "subject": "owner"},
        {"issuer": "https://identity.example?x=1", "subject": "owner"},
        {"issuer": "https://identity.example", "subject": ""},
        {"issuer": "https://identity.example", "subject": " owner "},
        {"issuer": "https://identity.example", "subject": "x" * 256},
        {"issuer": "https://identity.example", "subject": "ownér"},
    ],
)
def test_invalid_or_missing_config_fails_closed(source):
    with pytest.raises(GlobalOwnerConfigurationError):
        load_global_owner_config(source, trusted_issuers=(ISSUER,))


def test_untrusted_issuer_is_rejected_even_if_https():
    with pytest.raises(GlobalOwnerConfigurationError, match="trusted issuer"):
        load_global_owner_config(
            {"issuer": "https://untrusted.example", "subject": "owner"},
            trusted_issuers=(ISSUER,),
        )


def test_exact_issuer_and_subject_pair_is_required():
    config = load_global_owner_config(
        {"issuer": ISSUER, "subject": OWNER.subject},
        trusted_issuers=(ISSUER,),
    )
    assert is_global_owner(OWNER, config)
    assert not is_global_owner(OTHER_SUBJECT, config)
    assert not is_global_owner(OTHER_ISSUER, config)


def test_missing_config_and_unauthenticated_principal_fail_closed():
    config = load_global_owner_config(
        {"issuer": ISSUER, "subject": OWNER.subject},
        trusted_issuers=(ISSUER,),
    )
    assert not is_global_owner(OWNER, None)
    assert not is_global_owner(Principal(OWNER.subject, ISSUER, False), config)
    assert not is_global_owner(OWNER, None)
    with pytest.raises(AuthorizationDenied):
        require_global_owner(OWNER, None)


def test_global_owner_guard_returns_validated_principal():
    config = load_global_owner_config(
        {"issuer": ISSUER, "subject": OWNER.subject},
        trusted_issuers=(ISSUER,),
    )
    assert require_global_owner(OWNER, config) is OWNER
    with pytest.raises(AuthorizationDenied):
        require_global_owner(OTHER_SUBJECT, config)


def test_project_owner_or_grantee_is_not_global_owner_by_default():
    config = load_global_owner_config(
        {"issuer": ISSUER, "subject": OWNER.subject},
        trusted_issuers=(ISSUER,),
    )
    # A project relationship is not an input to this guard; identity must match
    # the separately provisioned global owner pair.
    project_owner = Principal("project-creator", ISSUER, True)
    read_grantee = Principal("project-reader", ISSUER, True)
    assert not is_global_owner(project_owner, config)
    assert not is_global_owner(read_grantee, config)
