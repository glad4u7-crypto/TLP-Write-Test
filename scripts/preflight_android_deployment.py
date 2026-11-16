"""Fail-closed preflight for an owner-controlled APAA test deployment.

This checks configuration shape only. It cannot prove HTTPS termination,
OIDC provider correctness, volume durability, network isolation or host security.
It never prints secret values.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit

try:  # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib


class PreflightError(ValueError):
    """Raised when deployment configuration is unsafe or incomplete."""


def _https_url(value: object, label: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise PreflightError(f"{label} must be a non-empty HTTPS URL.")
    try:
        parsed = urlsplit(value)
        parsed.port
    except ValueError as exc:
        raise PreflightError(f"{label} is malformed.") from exc
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
        or any(ch.isspace() or ord(ch) < 32 for ch in value)
    ):
        raise PreflightError(f"{label} must be an unambiguous HTTPS URL.")


def validate_settings(settings: dict, *, cwd: Path | None = None) -> list[str]:
    """Validate mandatory settings without exposing secret material."""
    cwd = (cwd or Path.cwd()).resolve()
    auth = settings.get("auth")
    apaa = settings.get("apaa")
    if not isinstance(auth, dict):
        raise PreflightError("Missing [auth] OIDC configuration.")
    if not isinstance(apaa, dict):
        raise PreflightError("Missing [apaa] configuration.")
    if apaa.get("require_auth") is not True:
        raise PreflightError("[apaa].require_auth must be the boolean true.")

    for key in ("client_id", "client_secret", "cookie_secret"):
        value = auth.get(key)
        if not isinstance(value, str) or not value.strip():
            raise PreflightError(f"[auth].{key} must be configured.")

    _https_url(auth.get("redirect_uri"), "[auth].redirect_uri")
    _https_url(auth.get("server_metadata_url"), "[auth].server_metadata_url")

    signing_hex = apaa.get("approval_signing_secret_hex")
    if not isinstance(signing_hex, str):
        raise PreflightError("[apaa].approval_signing_secret_hex must be configured.")
    try:
        signing_key = bytes.fromhex(signing_hex)
    except ValueError as exc:
        raise PreflightError("[apaa].approval_signing_secret_hex must be valid hex.") from exc
    if len(signing_key) < 32:
        raise PreflightError("[apaa].approval_signing_secret_hex must decode to at least 32 bytes.")

    db_paths = []
    for key in ("security_db_path", "project_db_path", "memory_db_path"):
        raw = apaa.get(key)
        if not isinstance(raw, str) or not raw.strip():
            raise PreflightError(f"[apaa].{key} must be explicitly configured.")
        path = Path(raw).expanduser()
        if not path.is_absolute():
            raise PreflightError(f"[apaa].{key} must be an absolute path on the deployment host.")
        resolved = path.resolve()
        if resolved == cwd or cwd in resolved.parents:
            raise PreflightError(f"[apaa].{key} must be outside the application checkout.")
        if not resolved.parent.is_dir():
            raise PreflightError(f"Parent directory for [apaa].{key} must already exist.")
        if not os.access(resolved.parent, os.W_OK):
            raise PreflightError(f"Parent directory for [apaa].{key} is not writable.")
        db_paths.append(resolved)

    if len(set(db_paths)) != len(db_paths):
        raise PreflightError("Security, project and memory databases must use distinct paths.")

    return [
        "OIDC configuration shape: PASS",
        "HTTPS redirect and metadata URLs: PASS",
        "Authentication required: PASS",
        "Approval signing key length/format: PASS",
        "Database paths: absolute, outside checkout, distinct and writable: PASS",
        "Operator must separately verify these paths are on private persistent storage.",
        "Operator must separately verify TLS, OIDC login, session revocation and host controls.",
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--secrets", required=True, type=Path,
                        help="Path to the private Streamlit secrets TOML file.")
    args = parser.parse_args(argv)
    try:
        with args.secrets.open("rb") as handle:
            settings = tomllib.load(handle)
        results = validate_settings(settings)
    except (OSError, tomllib.TOMLDecodeError, PreflightError) as exc:
        print(f"APAA DEPLOYMENT PREFLIGHT: BLOCKED — {exc}", file=sys.stderr)
        return 2
    print("APAA DEPLOYMENT PREFLIGHT: CONFIGURATION PASS")
    for item in results:
        print(f"- {item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
