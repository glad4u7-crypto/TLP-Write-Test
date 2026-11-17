"""On-device, non-invasive Android/Termux acceptance diagnostics.

Run on the physical handset with:
    python scripts/android_device_acceptance.py

Only reports environment and loopback checks. It never prints secrets, changes
Android settings, installs packages, touches firewall/VPN configuration, or
claims Chrome/Owner-flow acceptance.
"""
from __future__ import annotations

import json
import os
import socket
import sys
import tomllib
from pathlib import Path
from typing import Mapping


def _check(name: str, passed: bool, detail: str) -> dict[str, object]:
    return {"id": name, "status": "PASS" if passed else "FAIL", "detail": detail}


def run_diagnostics(*, environ: Mapping[str, str], secrets_path: Path) -> list[dict[str, object]]:
    android = sys.platform == "android" or any(
        key in environ for key in ("ANDROID_ROOT", "ANDROID_DATA")
    )
    prefix = environ.get("PREFIX", "").lower()
    home = environ.get("HOME", "").lower()
    termux = android and ("com.termux" in prefix or "com.termux" in home)

    results = [
        _check("D01", android, "Android environment detected" if android else "Not running on Android"),
        _check("D02", termux, "Termux environment detected" if termux else "Termux markers missing"),
        _check("D03", sys.version_info >= (3, 11), f"Python {sys.version_info.major}.{sys.version_info.minor}"),
        _check("D04", hasattr(os, "geteuid") and os.geteuid() != 0, "Non-root process" if hasattr(os, "geteuid") and os.geteuid() != 0 else "Root or effective UID unavailable"),
    ]

    auth_ok = False
    if secrets_path.is_file():
        try:
            config = tomllib.loads(secrets_path.read_text(encoding="utf-8"))
            apaa = config.get("apaa")
            auth = config.get("auth")
            auth_ok = isinstance(apaa, dict) and apaa.get("require_auth") is True and isinstance(auth, dict) and bool(auth)
        except (OSError, tomllib.TOMLDecodeError):
            auth_ok = False
    results.append(_check("D05", auth_ok, "OIDC-required Owner configuration present" if auth_ok else "Missing/invalid OIDC-required Owner configuration; secret values not displayed"))

    loopback_ok = False
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            server.settimeout(2)
            server.bind(("127.0.0.1", 0))
            server.listen(1)
            port = server.getsockname()[1]
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client:
                client.settimeout(2)
                client.connect(("127.0.0.1", port))
                conn, _ = server.accept()
                conn.close()
                loopback_ok = True
    except OSError:
        loopback_ok = False
    results.append(_check("D06", loopback_ok, "Loopback TCP bind/connect/accept succeeded" if loopback_ok else "Loopback TCP self-test failed"))

    return results


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    results = run_diagnostics(
        environ=os.environ, secrets_path=root / ".streamlit" / "secrets.toml"
    )
    print(json.dumps(results, indent=2))
    passed = sum(item["status"] == "PASS" for item in results)
    print(f"Automated handset diagnostics: {passed}/{len(results)} passed")
    print("Manual Chrome login, approvals, session expiry, audit, and restart tests remain required.")
    return 0 if all(item["status"] == "PASS" for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
