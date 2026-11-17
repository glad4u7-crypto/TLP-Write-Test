"""Safe local launcher for APAA Owner UI on Android/Termux.

This launches only the Streamlit control UI on loopback. It does not start or
enable the browser worker. OIDC authentication must be explicitly configured.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Mapping, Sequence


def validate_android_owner_config(
    *, environ: Mapping[str, str], secrets_path: Path
) -> None:
    android = sys.platform == "android" or any(
        key in environ for key in ("ANDROID_ROOT", "ANDROID_DATA")
    )
    prefix = environ.get("PREFIX", "").lower()
    home = environ.get("HOME", "").lower()
    termux = "com.termux" in prefix or "com.termux" in home
    if not (android and termux):
        raise RuntimeError("This launcher is restricted to Android/Termux.")
    if not secrets_path.is_file():
        raise RuntimeError("Owner OIDC secrets.toml is required; local prototype mode is unsafe.")
    try:
        config = tomllib.loads(secrets_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise RuntimeError("Owner secrets.toml could not be read safely.") from exc
    apaa = config.get("apaa")
    auth = config.get("auth")
    if not isinstance(apaa, dict) or apaa.get("require_auth") is not True:
        raise RuntimeError("Set [apaa].require_auth = true before starting the Owner UI.")
    if not isinstance(auth, dict) or not auth:
        raise RuntimeError("Configure Streamlit [auth] OIDC settings before starting.")


def owner_ui_command(
    *, python_executable: str, app_path: Path, port: int = 8501
) -> list[str]:
    if not 1024 <= port <= 65535:
        raise ValueError("Port must be between 1024 and 65535.")
    return [
        python_executable, "-m", "streamlit", "run", str(app_path),
        "--server.address=127.0.0.1",
        f"--server.port={port}",
        "--server.headless=true",
        "--browser.gatherUsageStats=false",
    ]


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    validate_android_owner_config(
        environ=os.environ, secrets_path=root / ".streamlit" / "secrets.toml"
    )
    command = owner_ui_command(
        python_executable=sys.executable, app_path=root / "app.py"
    )
    print("APAA Owner UI: http://127.0.0.1:8501")
    print("Loopback only. Browser/Worker dispatch remains disabled.")
    return subprocess.call(command, cwd=root)


if __name__ == "__main__":
    raise SystemExit(main())
