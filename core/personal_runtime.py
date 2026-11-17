"""Single-owner local runtime primitives for APAA Personal Edition.

The local owner is the operating-system user running the app, not an identity
supplied by a browser, task, or model. This module is not authentication for a
network-exposed server; bind local mode to loopback and use a reviewed HTTPS
authentication boundary for remote access.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import secrets
import stat

from core.storage import TenantKey


PERSONAL_OWNER_TENANT = TenantKey("local://apaa-personal", "local-owner")
SIGNING_KEY_FILENAME = "approval-signing.key"
SIGNING_KEY_BYTES = 32


@dataclass(frozen=True)
class PersonalRuntimePaths:
    """Owner-private paths for the single-user local runtime."""

    data_dir: Path
    projects_db: Path
    security_db: Path
    memory_db: Path
    audit_log: Path
    signing_key: Path


def personal_runtime_paths(data_dir: str | Path) -> PersonalRuntimePaths:
    root = Path(data_dir).expanduser().absolute()
    return PersonalRuntimePaths(
        data_dir=root,
        projects_db=root / "projects.sqlite3",
        security_db=root / "security.sqlite3",
        memory_db=root / "memory.sqlite3",
        audit_log=root / "execution-audit.jsonl",
        signing_key=root / SIGNING_KEY_FILENAME,
    )


def _reject_symlink_components(path: Path) -> None:
    for component in (path, *path.parents):
        try:
            metadata = component.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(metadata.st_mode):
            raise ValueError("Personal data path must not contain symlinks.")


def ensure_private_data_dir(data_dir: str | Path) -> Path:
    """Create or validate a private owner-only directory (0700 on POSIX)."""
    root = Path(data_dir).expanduser().absolute()
    _reject_symlink_components(root)
    try:
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
    except OSError as exc:
        raise ValueError("Could not create the personal data directory.") from exc
    _reject_symlink_components(root)
    metadata = root.lstat()
    if not stat.S_ISDIR(metadata.st_mode):
        raise ValueError("Personal data path must be a real directory.")
    if os.name == "posix" and metadata.st_mode & 0o077:
        raise ValueError("Personal data directory must be owner-only (0700).")
    return root


def load_or_create_approval_signing_key(data_dir: str | Path) -> bytes:
    """Load a stable 32-byte local signing key, creating it atomically if absent.

    The key is protected by OS file permissions, not by hardware. Anyone who
    can read files as the same OS account can potentially use or copy it.
    """
    root = ensure_private_data_dir(data_dir)
    key_path = root / SIGNING_KEY_FILENAME
    _reject_symlink_components(key_path)

    try:
        metadata = key_path.lstat()
    except FileNotFoundError:
        candidate = secrets.token_bytes(SIGNING_KEY_BYTES)
        flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(key_path, flags, 0o600)
        except FileExistsError:
            pass
        except OSError as exc:
            raise ValueError("Could not safely create the local approval key.") from exc
        else:
            try:
                with os.fdopen(descriptor, "wb") as stream:
                    stream.write(candidate)
                    stream.flush()
                    os.fsync(stream.fileno())
            except Exception:
                try:
                    key_path.unlink()
                except OSError:
                    pass
                raise
            metadata = key_path.lstat()
            if not stat.S_ISREG(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode):
                raise ValueError("Local approval key is not a regular file.")
            if os.name == "posix" and metadata.st_mode & 0o077:
                raise ValueError("Local approval key permissions are not private.")
            return candidate

    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise ValueError("Local approval key must be a regular non-symlink file.")
    if os.name == "posix" and metadata.st_mode & 0o077:
        raise ValueError("Local approval key must be owner-only (0600).")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(key_path, flags)
        with os.fdopen(descriptor, "rb") as stream:
            key = stream.read(SIGNING_KEY_BYTES + 1)
    except OSError as exc:
        raise ValueError("Could not safely read the local approval key.") from exc
    if len(key) != SIGNING_KEY_BYTES:
        raise ValueError("Local approval key has an invalid length; refusing to replace it.")
    return key
