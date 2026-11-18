"""Strict local configuration validation for Android Owner UI startup."""
from __future__ import annotations

import os
from pathlib import Path
import stat
import tomllib
from urllib.parse import urlsplit


class AndroidOwnerConfigError(ValueError):
    """Raised when Android Owner authentication or durable signing config is unsafe."""


_REQUIRED_OIDC_FIELDS = (
    "redirect_uri",
    "cookie_secret",
    "client_id",
    "client_secret",
    "server_metadata_url",
)


def _open_private_secret_file(secrets_path: Path) -> int:
    """Open the secret via a pinned directory FD; reject symlinks and unsafe modes."""
    if not isinstance(secrets_path, Path) or not secrets_path.name:
        raise AndroidOwnerConfigError("Owner secrets.toml path is invalid.")
    directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    file_flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    directory_fd = None
    file_fd = None
    try:
        directory_fd = os.open(secrets_path.parent, directory_flags)
        directory_info = os.fstat(directory_fd)
        if not stat.S_ISDIR(directory_info.st_mode):
            raise AndroidOwnerConfigError("Owner secrets storage must be a real directory.")
        if directory_info.st_mode & 0o077:
            raise AndroidOwnerConfigError("Owner secrets directory must be private (mode 0700).")

        file_fd = os.open(secrets_path.name, file_flags, dir_fd=directory_fd)
        file_info = os.fstat(file_fd)
        if not stat.S_ISREG(file_info.st_mode):
            raise AndroidOwnerConfigError("Owner secrets file must be a regular file.")
        if file_info.st_mode & 0o077:
            raise AndroidOwnerConfigError("Owner secrets file must be private (mode 0600).")
        result = file_fd
        file_fd = None
        return result
    except AndroidOwnerConfigError:
        raise
    except OSError as exc:
        raise AndroidOwnerConfigError(
            "Owner secrets storage is missing, unreadable, or contains a symlink."
        ) from exc
    finally:
        if file_fd is not None:
            os.close(file_fd)
        if directory_fd is not None:
            os.close(directory_fd)


def validate_private_secret_storage(secrets_path: Path) -> None:
    """Require non-symlink private storage and verify permissions on opened FDs."""
    fd = _open_private_secret_file(secrets_path)
    os.close(fd)


def load_owner_secrets(secrets_path: Path) -> dict:
    """Read TOML through a no-follow file descriptor without exposing secret values."""
    fd = _open_private_secret_file(secrets_path)
    try:
        with os.fdopen(fd, "r", encoding="utf-8") as handle:
            return tomllib.loads(handle.read())
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
        raise AndroidOwnerConfigError("Owner secrets.toml is invalid or unreadable.") from exc


def validate_oidc_config(config: dict) -> None:
    apaa = config.get("apaa") if isinstance(config, dict) else None
    auth = config.get("auth") if isinstance(config, dict) else None
    if not isinstance(apaa, dict) or apaa.get("require_auth") is not True:
        raise AndroidOwnerConfigError("Set [apaa].require_auth = true.")
    if not isinstance(auth, dict):
        raise AndroidOwnerConfigError("Complete Streamlit [auth] OIDC configuration is required.")
    missing = [key for key in _REQUIRED_OIDC_FIELDS if not isinstance(auth.get(key), str) or not auth[key].strip()]
    if missing:
        raise AndroidOwnerConfigError("Streamlit [auth] OIDC configuration is incomplete.")
    if len(auth["cookie_secret"]) < 32:
        raise AndroidOwnerConfigError("Streamlit OIDC cookie_secret must contain at least 32 characters.")
    try:
        redirect = urlsplit(auth["redirect_uri"])
        redirect_port = redirect.port
    except ValueError as exc:
        raise AndroidOwnerConfigError("OIDC redirect_uri is malformed.") from exc
    if (
        redirect.scheme != "http"
        or redirect.hostname not in {"localhost", "127.0.0.1"}
        or redirect_port != 8501
        or redirect.path != "/oauth2callback"
        or redirect.username is not None
        or redirect.password is not None
        or redirect.query
        or redirect.fragment
    ):
        raise AndroidOwnerConfigError(
            "OIDC redirect_uri must be the local loopback callback on port 8501."
        )
    try:
        metadata = urlsplit(auth["server_metadata_url"])
        _ = metadata.port
    except ValueError as exc:
        raise AndroidOwnerConfigError("OIDC server_metadata_url is malformed.") from exc
    if (
        metadata.scheme != "https"
        or not metadata.hostname
        or metadata.username is not None
        or metadata.password is not None
        or metadata.fragment
    ):
        raise AndroidOwnerConfigError(
            "OIDC server_metadata_url must be an HTTPS URL without credentials."
        )


def validate_approval_signing_config(config: dict) -> None:
    apaa = config.get("apaa") if isinstance(config, dict) else None
    signing_secret_hex = apaa.get("approval_signing_secret_hex") if isinstance(apaa, dict) else None
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


def validate_android_owner_secrets(secrets_path: Path) -> None:
    config = load_owner_secrets(secrets_path)
    validate_oidc_config(config)
    validate_approval_signing_config(config)
