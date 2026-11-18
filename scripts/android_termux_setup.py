"""Interactive first-run setup for the APAA Android/Termux Owner console.

This script writes private local Streamlit OIDC settings. It never installs
packages, starts APAA, enables browser automation, or prints entered secrets.
"""
from __future__ import annotations

import argparse
import getpass
import json
import os
from pathlib import Path
import secrets
import sys
from urllib.parse import urlsplit

from core.android_owner_config import (
    AndroidOwnerConfigError,
    validate_android_owner_secrets,
)


REDIRECT_URI = "http://localhost:8501/oauth2callback"


def _is_termux(environ: dict[str, str]) -> bool:
    android = sys.platform == "android" or any(
        key in environ for key in ("ANDROID_ROOT", "ANDROID_DATA")
    )
    markers = (
        "com.termux" in environ.get("PREFIX", "").lower()
        or "com.termux" in environ.get("HOME", "").lower()
    )
    return android and markers


def _prompt_required(label: str, *, secret: bool = False) -> str:
    value = (getpass.getpass(label + ": ") if secret else input(label + ": ")).strip()
    if not value:
        raise ValueError(label + " is required.")
    return value


def _validate_metadata_url(value: str) -> None:
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
    ):
        raise ValueError("OIDC metadata URL must be HTTPS and contain no credentials or fragment.")


def build_secrets_text(
    *, client_id: str, client_secret: str, metadata_url: str,
    cookie_secret: str | None = None, approval_signing_secret_hex: str | None = None,
) -> str:
    for value, label in ((client_id, "OIDC client ID"), (client_secret, "OIDC client secret")):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(label + " is required.")
    _validate_metadata_url(metadata_url)
    cookie = cookie_secret or secrets.token_urlsafe(48)
    signing = approval_signing_secret_hex or secrets.token_hex(32)
    if len(cookie) < 32:
        raise ValueError("Cookie secret must contain at least 32 characters.")
    try:
        signing_bytes = bytes.fromhex(signing)
    except ValueError as exc:
        raise ValueError("Approval signing secret must be hexadecimal.") from exc
    if len(signing_bytes) < 32:
        raise ValueError("Approval signing secret must decode to at least 32 bytes.")

    q = json.dumps
    return (
        "[apaa]\n"
        "require_auth = true\n"
        f"approval_signing_secret_hex = {q(signing)}\n"
        'security_db_path = ".apaa_security/security.sqlite3"\n'
        'project_db_path = ".apaa_projects/projects.sqlite3"\n'
        'memory_db_path = ".apaa_memory/memory.sqlite3"\n\n'
        "[auth]\n"
        f"redirect_uri = {q(REDIRECT_URI)}\n"
        f"cookie_secret = {q(cookie)}\n"
        f"client_id = {q(client_id.strip())}\n"
        f"client_secret = {q(client_secret)}\n"
        f"server_metadata_url = {q(metadata_url.strip())}\n"
    )


def write_private_secrets(root: Path, content: str) -> Path:
    if not isinstance(root, Path) or not root.is_dir():
        raise ValueError("Repository root directory is required.")
    directory = root / ".streamlit"
    if directory.is_symlink():
        raise ValueError(".streamlit must not be a symlink.")
    directory.mkdir(mode=0o700, exist_ok=True)
    os.chmod(directory, 0o700)
    path = directory / "secrets.toml"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        try:
            path.unlink()
        except OSError:
            pass
        raise
    os.chmod(path, 0o600)
    validate_android_owner_secrets(path)
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Configure APAA Owner authentication for Termux.")
    parser.add_argument("--allow-non-termux-test", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if not args.allow_non_termux_test and not _is_termux(dict(os.environ)):
        print("This setup is restricted to Android/Termux.", file=sys.stderr)
        return 2

    root = Path(__file__).resolve().parents[1]
    target = root / ".streamlit" / "secrets.toml"
    if target.exists():
        print("Owner secrets already exist; refusing to overwrite them.", file=sys.stderr)
        return 2
    try:
        print("Register this exact redirect URI in your OIDC provider:")
        print(REDIRECT_URI)
        client_id = _prompt_required("OIDC client ID")
        client_secret = _prompt_required("OIDC client secret", secret=True)
        metadata_url = _prompt_required("OIDC HTTPS discovery URL")
        content = build_secrets_text(
            client_id=client_id, client_secret=client_secret, metadata_url=metadata_url
        )
        path = write_private_secrets(root, content)
    except (ValueError, OSError, AndroidOwnerConfigError) as exc:
        print("Setup failed: " + str(exc), file=sys.stderr)
        return 1
    print("Private Owner configuration created at " + str(path.relative_to(root)))
    print("Permissions: .streamlit=0700, secrets.toml=0600")
    print("Next: run python scripts/android_device_acceptance.py")
    print("No server or browser worker was started.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
