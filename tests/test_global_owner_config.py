from types import SimpleNamespace

import pytest

from core.global_owner import GlobalOwnerConfigurationError
from core.global_owner_config import (
    invalidate_owner_bound_session_state,
    load_global_owner_from_settings,
)


ISSUER = "https://accounts.example.test"
VALID = {
    "trusted_identity_issuers": [ISSUER],
    "global_owner": {"issuer": ISSUER, "subject": "opaque-owner-subject"},
}


def test_missing_owner_config_is_unprovisioned_not_first_login_bootstrap():
    assert load_global_owner_from_settings(
        {"trusted_identity_issuers": [ISSUER]}
    ) is None


def test_exact_server_config_loads_from_trusted_issuer():
    config = load_global_owner_from_settings(VALID)
    assert config is not None
    assert config.issuer == ISSUER
    assert config.subject == "opaque-owner-subject"


@pytest.mark.parametrize(
    "settings",
    [
        None,
        [],
        {"global_owner": {"issuer": ISSUER, "subject": "owner"}},
        {"trusted_identity_issuers": ISSUER, "global_owner": {"issuer": ISSUER, "subject": "owner"}},
        {"trusted_identity_issuers": [], "global_owner": {"issuer": ISSUER, "subject": "owner"}},
        {"trusted_identity_issuers": [ISSUER, ISSUER], "global_owner": {"issuer": ISSUER, "subject": "owner"}},
        {"trusted_identity_issuers": [" " + ISSUER], "global_owner": {"issuer": ISSUER, "subject": "owner"}},
        {"trusted_identity_issuers": [ISSUER], "global_owner": {"issuer": "https://untrusted.example", "subject": "owner"}},
        {"trusted_identity_issuers": [ISSUER], "global_owner": {"issuer": ISSUER, "subject": "owner", "role": "admin"}},
        {"trusted_identity_issuers": [ISSUER], "global_owner": "owner"},
    ],
)
def test_malformed_or_untrusted_settings_fail_closed(settings):
    with pytest.raises(GlobalOwnerConfigurationError):
        load_global_owner_from_settings(settings)


def test_owner_cache_invalidation_removes_only_owner_capabilities():
    state = {
        "global_owner_principal": object(),
        "global_owner_authorized": True,
        "global_owner_admin_context": object(),
        "global_owner_pending_action": {"action": "unsafe"},
        "global_owner_approval_receipt": object(),
        "project_registry": object(),
        "selected_project_id": "project-1",
    }
    invalidate_owner_bound_session_state(state)
    assert not any(key.startswith("global_owner_") for key in state)
    assert "project_registry" in state
    assert state["selected_project_id"] == "project-1"


def test_invalidation_accepts_streamlit_like_session_state():
    state = SimpleNamespace(values={"global_owner_authorized": True})
    state.pop = lambda key, default=None: state.values.pop(key, default)
    invalidate_owner_bound_session_state(state)
    assert state.values == {}
