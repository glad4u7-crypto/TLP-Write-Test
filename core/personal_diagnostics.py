"""Read-only health checks for APAA Personal Edition local runtime.

The diagnostics never create databases, initialize an Owner, rotate keys, or
modify application state. They report metadata only and never print secrets.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import sqlite3
import stat

from core.personal_runtime import PersonalRuntimePaths, personal_runtime_paths


@dataclass(frozen=True)
class Diagnostic:
    code: str
    status: str
    detail: str


_DATABASE_FIELDS = ("projects_db", "security_db", "owner_auth_db", "memory_db")


def _path_exists(path: Path) -> bool:
    try:
        path.lstat()
        return True
    except FileNotFoundError:
        return False


def _contains_symlink_component(path: Path) -> bool:
    for component in (path, *path.parents):
        try:
            metadata = component.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(metadata.st_mode):
            return True
    return False


def _is_safe_regular_file(path: Path) -> bool:
    if _contains_symlink_component(path):
        return False
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return False
    return stat.S_ISREG(metadata.st_mode)


def _directory_is_private(path: Path) -> bool:
    if _contains_symlink_component(path):
        return False
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return False
    if not stat.S_ISDIR(metadata.st_mode):
        return False
    return os.name != "posix" or not (metadata.st_mode & 0o077)


def _sqlite_integrity(path: Path) -> bool:
    # Open read-only: a health check must never create or repair a database.
    try:
        with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=2) as db:
            rows = db.execute("PRAGMA quick_check").fetchall()
        return len(rows) == 1 and rows[0][0] == "ok"
    except (OSError, sqlite3.Error, ValueError):
        return False


def inspect_personal_runtime(data_dir: str | Path) -> list[Diagnostic]:
    """Inspect a Personal Edition data directory without changing it."""
    paths: PersonalRuntimePaths = personal_runtime_paths(data_dir)
    results: list[Diagnostic] = []

    if not _path_exists(paths.data_dir):
        results.append(Diagnostic(
            "data_dir", "INFO", "Personal data directory is not initialized yet."
        ))
        return results

    if not _directory_is_private(paths.data_dir):
        results.append(Diagnostic(
            "data_dir", "FAIL",
            "Data directory is not a real owner-private directory; expected POSIX mode 0700."
        ))
        return results

    results.append(Diagnostic(
        "data_dir", "PASS", "Personal data directory exists and has owner-only access."
    ))

    for field in _DATABASE_FIELDS:
        db_path = getattr(paths, field)
        if not _path_exists(db_path):
            results.append(Diagnostic(
                field, "INFO", "Database has not been created yet."
            ))
        elif not _is_safe_regular_file(db_path):
            results.append(Diagnostic(
                field, "FAIL", "Database path is not a regular non-symlink file."
            ))
        elif _sqlite_integrity(db_path):
            results.append(Diagnostic(
                field, "PASS", "SQLite quick_check passed (read-only)."
            ))
        else:
            results.append(Diagnostic(
                field, "FAIL", "SQLite quick_check failed or database could not be opened read-only."
            ))

    key_path = paths.signing_key
    if not _path_exists(key_path):
        results.append(Diagnostic(
            "signing_key", "INFO", "Approval signing key has not been initialized yet."
        ))
    elif not _is_safe_regular_file(key_path):
        results.append(Diagnostic(
            "signing_key", "FAIL", "Signing key is not a regular non-symlink file."
        ))
    else:
        try:
            metadata = key_path.lstat()
            valid_permissions = os.name != "posix" or not (metadata.st_mode & 0o077)
            with key_path.open("rb") as stream:
                valid_length = len(stream.read(33)) == 32
        except OSError:
            valid_permissions = False
            valid_length = False
        if valid_permissions and valid_length:
            results.append(Diagnostic(
                "signing_key", "PASS", "Signing key permissions and length are valid; key material was not displayed."
            ))
        else:
            results.append(Diagnostic(
                "signing_key", "FAIL", "Signing key permissions or length are invalid; key was not modified."
            ))

    if _path_exists(paths.audit_log):
        if _is_safe_regular_file(paths.audit_log):
            results.append(Diagnostic(
                "audit_log", "PASS", "Audit log path is a regular non-symlink file."
            ))
        else:
            results.append(Diagnostic(
                "audit_log", "FAIL", "Audit log path is not a regular non-symlink file."
            ))
    else:
        results.append(Diagnostic(
            "audit_log", "INFO", "Audit log has not been created yet."
        ))

    return results


def diagnostics_summary(results: list[Diagnostic]) -> tuple[int, int, int]:
    """Return (pass, fail, info) counts without changing the supplied results."""
    return tuple(
        sum(item.status == status for item in results)
        for status in ("PASS", "FAIL", "INFO")
    )
