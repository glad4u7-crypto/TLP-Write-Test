"""Fail-closed preflight for the Android Termux launcher."""
from __future__ import annotations

import argparse
import importlib.util
import os
from pathlib import Path
import stat
import sys


class PreflightError(ValueError):
    """A local launcher prerequisite is unsafe or unavailable."""


def validate_port(raw: str) -> int:
    if not raw or not raw.isascii() or not raw.isdecimal():
        raise PreflightError("APAA_PORT must contain decimal digits only.")
    port = int(raw, 10)
    if not 1024 <= port <= 65535:
        raise PreflightError("APAA_PORT must be between 1024 and 65535.")
    return port


def prepare_private_data_dir(raw_path: str | Path) -> Path:
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        raise PreflightError("APAA_PERSONAL_DATA_DIR must be an absolute path.")

    try:
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
        if os.name == "posix":
            nofollow = getattr(os, "O_NOFOLLOW", None)
            directory = getattr(os, "O_DIRECTORY", None)
            if nofollow is None or directory is None:
                raise PreflightError("This platform cannot safely verify the private data directory.")
            fd = os.open(path, os.O_RDONLY | directory | nofollow)
            try:
                metadata = os.fstat(fd)
                if not stat.S_ISDIR(metadata.st_mode):
                    raise PreflightError("Personal data path is not a directory.")
                if metadata.st_uid != os.getuid():
                    raise PreflightError("Personal data directory is not owned by the current user.")
                os.fchmod(fd, 0o700)
                verified = os.fstat(fd)
                if verified.st_mode & 0o077:
                    raise PreflightError("Personal data directory permissions are not private.")
            finally:
                os.close(fd)
        else:
            metadata = path.lstat()
            if not stat.S_ISDIR(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode):
                raise PreflightError("Personal data path is not a real directory.")
    except PreflightError:
        raise
    except OSError as exc:
        raise PreflightError("Could not safely prepare the private Personal Edition data directory.") from exc
    return path


def check_streamlit() -> None:
    try:
        available = importlib.util.find_spec("streamlit") is not None
    except (ImportError, ValueError):
        available = False
    if not available:
        raise PreflightError(
            "Streamlit is not installed in this Python environment. "
            "Install the repository requirements in Termux, then retry."
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--port", required=True)
    args = parser.parse_args()
    try:
        validate_port(args.port)
        prepare_private_data_dir(args.data_dir)
        check_streamlit()
    except PreflightError as exc:
        print(f"APAA preflight BLOCKED: {exc}", file=sys.stderr)
        return 2
    print("APAA preflight PASS: private data directory, Streamlit dependency and port verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
