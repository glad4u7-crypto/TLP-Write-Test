"""Server-side adapter for optional, fail-closed global-owner provisioning.

The adapter accepts only a mapping supplied by the deployment secret/config
provider. It never reads browser/session/task/model input and never bootstraps
an owner from the first authenticated user. Secret-store custody and access
permissions remain deployment responsibilities.
"""
from __future__ import annotations

from collections.abc import Collection, Mapping

from core.global_owner import (
    GlobalOwnerConfig,
    GlobalOwnerConfigurationError,
    load_global_owner_config,
)


def load_global_owner_from_settings(
    apaa_settings: Mapping[str, object],
) -> GlobalOwnerConfig | None:
    """Load one optional owner pair from trusted server-side settings.

    Absence means owner administration is unprovisioned and disabled. A
    present-but-invalid value raises a sanitized configuration exception for
    the caller to report without enabling any owner capability.
    """
    if not isinstance(apaa_settings, Mapping):
        raise GlobalOwnerConfigurationError("APAA server settings are invalid.")

    source = apaa_settings.get("global_owner")
    if source is None:
        return None
    if not isinstance(source, Mapping):
        raise GlobalOwnerConfigurationError("Global owner configuration is invalid.")

    trusted = apaa_settings.get("trusted_identity_issuers")
    if (
        not isinstance(trusted, Collection)
        or isinstance(trusted, (str, bytes))
        or not trusted
        or any(type(item) is not str or not item or item != item.strip() for item in trusted)
        or len(set(trusted)) != len(trusted)
    ):
        raise GlobalOwnerConfigurationError("Trusted issuer configuration is invalid.")

    return load_global_owner_config(source, trusted_issuers=trusted)


OWNER_BOUND_SESSION_KEYS = (
    "global_owner_principal",
    "global_owner_authorized",
    "global_owner_admin_context",
    "global_owner_pending_action",
    "global_owner_approval_receipt",
)


def invalidate_owner_bound_session_state(session_state: object) -> None:
    """Remove cached owner capabilities when provisioning changes.

    This deliberately does not clear unrelated project state or infer identity.
    """
    if not isinstance(session_state, Mapping) and not hasattr(session_state, "pop"):
        raise TypeError("A mutable server session-state mapping is required.")
    for key in OWNER_BOUND_SESSION_KEYS:
        session_state.pop(key, None)
