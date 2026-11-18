"""Strict local configuration validation for Android Owner UI startup."""
from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
import tomllib


class AndroidOwnerConfigError(ValueError):
    """Raised when Android Owner authentication or durable signing config is unsafe."""


_REQUIRED_OIDC_FIELDS = (
    "redirect_uri",
    "cookie_secret",
    "client_id",
    "client_secret",
    "server_metadata_url",
)


def load_android_owner_config(secrets_path: Path) -> dict:
    """Load and validate Streamlit OIDC and APAA signing configuration.

    Values are never returned in errors or logged. Streamlit reads this same
    secrets.toml file, so the launcher must reject incomplete configuration
    before starting a process that would immediately stop or run insecurely.
    """
    if not isinstance(secrets_path, Path) or not secrets_path.is_file():
        raise AndroidOwnerConfigError("Owner secrets.toml is required.")
    try:
        config = tomllib.loads(secrets_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
        raise AndroidOwnerConfigError("Owner secrets.toml is invalid or unreadable.") from exc

    apaa = config.get("apaa")
    auth = config.get("auth")
    if not isinstance(apaa, dict) or apaa.get("require_auth") is not True:
        raise AndroidOwnerConfigError("Set [apaa].require_auth = true.")
    if not isinstance(auth, dict):
        raise AndroidOwnerConfigError("Complete Streamlit [auth] OIDC configuration is required.")
    missing = [key for key in _REQUIRED_OIDC_FIELDS if not isinstance(auth.get(key), str) or not auth[key].strip()]
    if missing:
        raise AndroidOwnerConfigError("Streamlit [auth] OIDC configuration is incomplete.")

    cookie_secret = auth["cookie_secret"]
    if len(cookie_secret) < 32:
        raise AndroidOwnerConfigError("Streamlit OIDC cookie_secret must contain at least 32 characters.")
    signing_secret_hex = apaa.get("approval_signing_secret_hex")
    if not isinstance(signing_secret_hex, str):
        raise AndroidOwnerConfigError("APAA approval signing secret is required.")
    try:
        signing_secret = bytes.fromhex(signing_secret_hex)
    except ValueError as exc:
        raise AndroidOwnerConfigError("APAA approval signing secret must be valid hexadecimal.") from exc
    if len(signing_secret) < 32:
        raise AndroidOwnerConfigError("APAA approval signing secret must decode to at least 32 bytes.")

    for key in ("security_db_path", "project_db_path", "memory_db_path"):
        value = apaa.get(key)
        if value is not None and (not isinstance(value, str) or not value.strip()):
            raise AndroidOwnerConfigError("APAA durable storage paths must be non-empty strings.")
    return config
