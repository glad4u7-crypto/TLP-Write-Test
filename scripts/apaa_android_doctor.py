"""Read-only Android/Termux runtime diagnostics for APAA Personal Edition.

This command does not read user files, secrets, browser profiles or credentials.
It does not create directories, start a server, or make network connections.
"""
from __future__ import annotations

import importlib.metadata
import importlib.util
import os
import platform
import socket
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _package_version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "NOT INSTALLED"


def _git_commit() -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=3,
        )
        value = result.stdout.strip()
        return value if len(value) == 40 and all(c in "0123456789abcdef" for c in value) else "UNKNOWN"
    except (OSError, subprocess.SubprocessError):
        return "UNKNOWN"


def _loopback_socket_available() -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            return True
    except OSError:
        return False


def collect_diagnostics() -> dict[str, str | bool]:
    termux_prefix = os.environ.get("PREFIX", "").startswith("/data/data/com.termux/")
    streamlit_installed = importlib.util.find_spec("streamlit") is not None
    cryptography_installed = importlib.util.find_spec("cryptography") is not None
    aes_gcm_available = False
    scrypt_available = False

    if cryptography_installed:
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

            aes_gcm_available = AESGCM is not None
            scrypt_available = Scrypt is not None
        except (ImportError, OSError):
            pass

    return {
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "platform": sys.platform,
        "machine": platform.machine() or "UNKNOWN",
        "termux_detected": termux_prefix,
        "streamlit_version": _package_version("streamlit"),
        "cryptography_version": _package_version("cryptography"),
        "aes_256_gcm_available": aes_gcm_available,
        "scrypt_available": scrypt_available,
        "loopback_bind_available": _loopback_socket_available(),
        "git_commit": _git_commit(),
    }


def main() -> int:
    print("APAA Android Runtime Doctor — READ ONLY")
    print("Privacy: no secrets, personal files, browser data or credentials are read.")
    print("Network: no network connection is made; only a temporary 127.0.0.1 socket bind is tested.")
    print("Filesystem: no files or directories are created or changed.")
    print()
    results = collect_diagnostics()
    for key, value in results.items():
        print(f"{key}: {value}")

    required = (
        results["streamlit_version"] != "NOT INSTALLED"
        and results["aes_256_gcm_available"]
        and results["scrypt_available"]
        and results["loopback_bind_available"]
    )
    print()
    print("DIAGNOSTIC RESULT: " + ("BASIC CHECKS PASS" if required else "BLOCKED — review missing requirements"))
    print("This is a runtime diagnostic, not physical Android A01–A12 acceptance.")
    return 0 if required else 2


if __name__ == "__main__":
    raise SystemExit(main())
