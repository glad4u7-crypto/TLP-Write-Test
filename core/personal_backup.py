"""Owner-private SQLite snapshot export and safe restore for APAA Personal Edition.

Backups deliberately exclude the local approval signing key. Restore creates a
fresh key, invalidating all outstanding approval receipts while preserving the
owner's projects, memory, consumed nonces and durable audit chain.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
import shutil
import sqlite3
import stat
import tempfile
from typing import Any
import zipfile

from core.personal_auth import LocalOwnerAuthStore
from core.personal_runtime import (
    ensure_private_data_dir,
    load_or_create_approval_signing_key,
    personal_runtime_paths,
)
from core.sqlite_security_store import SQLiteSecurityStore


_FORMAT = "APAA_PERSONAL_BACKUP"
_VERSION = 2
_DATABASES_V1 = ("projects.sqlite3", "security.sqlite3", "memory.sqlite3")
_DATABASES = ("projects.sqlite3", "security.sqlite3", "owner-auth.sqlite3", "memory.sqlite3")
_MANIFEST = "manifest.json"
_MAX_DATABASE_BYTES = 256 * 1024 * 1024
_MAX_ARCHIVE_BYTES = 512 * 1024 * 1024
_MAX_MANIFEST_BYTES = 64 * 1024
_CHUNK = 1024 * 1024


class PersonalBackupError(ValueError):
    """Raised when a Personal Edition backup cannot be safely created/restored."""


def _reject_symlink_components(path: Path) -> None:
    for component in (path, *path.parents):
        try:
            if stat.S_ISLNK(component.lstat().st_mode):
                raise PersonalBackupError("Backup path must not contain symlinks.")
        except FileNotFoundError:
            continue


def _regular_private_file(path: Path, *, label: str, maximum: int) -> os.stat_result:
    _reject_symlink_components(path)
    try:
        metadata = path.lstat()
    except FileNotFoundError as exc:
        raise PersonalBackupError(f"Required {label} is missing.") from exc
    if not stat.S_ISREG(metadata.st_mode):
        raise PersonalBackupError(f"{label} must be a regular file.")
    if os.name == "posix" and metadata.st_mode & 0o077:
        raise PersonalBackupError(f"{label} must be owner-only (0600).")
    if metadata.st_size > maximum:
        raise PersonalBackupError(f"{label} exceeds the configured size limit.")
    return metadata


def _sqlite_integrity(path: Path) -> None:
    try:
        connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
        try:
            row = connection.execute("PRAGMA integrity_check").fetchone()
        finally:
            connection.close()
    except sqlite3.Error as exc:
        raise PersonalBackupError("A SQLite backup database could not be opened safely.") from exc
    if row is None or row[0] != "ok":
        raise PersonalBackupError("A SQLite backup database failed its integrity check.")


def _snapshot_database(source: Path, destination: Path) -> None:
    _regular_private_file(source, label=source.name, maximum=_MAX_DATABASE_BYTES)
    try:
        source_connection = sqlite3.connect(
            source.as_uri() + "?mode=ro", uri=True, timeout=10
        )
        destination_connection = sqlite3.connect(destination, timeout=10)
        try:
            source_connection.backup(destination_connection)
            destination_connection.commit()
        finally:
            destination_connection.close()
            source_connection.close()
        os.chmod(destination, 0o600)
        _sqlite_integrity(destination)
    except (OSError, sqlite3.Error) as exc:
        raise PersonalBackupError(f"Could not snapshot {source.name} consistently.") from exc


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while True:
            chunk = stream.read(_CHUNK)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def create_personal_backup(data_dir: str | Path, backup_path: str | Path) -> Path:
    """Create an atomic owner-only backup containing consistent SQLite snapshots."""
    paths = personal_runtime_paths(data_dir)
    ensure_private_data_dir(paths.data_dir)
    destination = Path(backup_path).expanduser().absolute()
    _reject_symlink_components(destination)
    ensure_private_data_dir(destination.parent)
    if destination == paths.data_dir or paths.data_dir in destination.parents:
        raise PersonalBackupError("Store backups outside the live Personal Edition data directory.")
    if destination.exists() and not destination.is_file():
        raise PersonalBackupError("Backup destination must be a regular file.")
    if destination.exists() and destination.is_symlink():
        raise PersonalBackupError("Backup destination must not be a symlink.")

    temporary_dir = Path(tempfile.mkdtemp(prefix=".apaa-backup-stage-", dir=destination.parent))
    temporary_archive: Path | None = None
    try:
        manifest_files: dict[str, dict[str, Any]] = {}
        for filename in _DATABASES:
            source = paths.data_dir / filename
            snapshot = temporary_dir / filename
            _snapshot_database(source, snapshot)
            manifest_files[filename] = {
                "size": snapshot.stat().st_size,
                "sha256": _sha256(snapshot),
            }

        # Verify the security database's append-only audit chain before export.
        security_snapshot = SQLiteSecurityStore(temporary_dir / "security.sqlite3")
        if not security_snapshot.verify_audit_chain():
            raise PersonalBackupError("The durable audit chain is invalid; backup was refused.")

        manifest = {
            "format": _FORMAT,
            "version": _VERSION,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "files": manifest_files,
            "approval_signing_key_included": False,
            "restore_behavior": "Owner authentication is preserved; a fresh local approval signing key is generated on restore.",
        }
        manifest_path = temporary_dir / _MANIFEST
        manifest_path.write_text(
            json.dumps(manifest, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )
        os.chmod(manifest_path, 0o600)

        fd, temporary_name = tempfile.mkstemp(
            prefix=".apaa-backup-", suffix=".tmp", dir=destination.parent
        )
        os.close(fd)
        temporary_archive = Path(temporary_name)
        os.chmod(temporary_archive, 0o600)
        with zipfile.ZipFile(
            temporary_archive, mode="w", compression=zipfile.ZIP_DEFLATED,
            compresslevel=6,
        ) as archive:
            for filename in (*_DATABASES, _MANIFEST):
                archive.write(temporary_dir / filename, arcname=filename)
        if temporary_archive.stat().st_size > _MAX_ARCHIVE_BYTES:
            raise PersonalBackupError("The resulting backup exceeds the archive size limit.")
        with temporary_archive.open("rb") as stream:
            os.fsync(stream.fileno())
        os.replace(temporary_archive, destination)
        temporary_archive = None
        os.chmod(destination, 0o600)
        return destination
    except PersonalBackupError:
        raise
    except (OSError, sqlite3.Error, zipfile.BadZipFile, ValueError, RecursionError) as exc:
        raise PersonalBackupError("Personal backup creation failed safely.") from exc
    finally:
        if temporary_archive is not None:
            try:
                temporary_archive.unlink()
            except OSError:
                pass
        shutil.rmtree(temporary_dir, ignore_errors=True)


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise PersonalBackupError("Backup manifest contains duplicate keys.")
        result[key] = value
    return result


def restore_personal_backup(
    backup_path: str | Path, destination_data_dir: str | Path
) -> Path:
    """Restore into a new private directory; never overwrite a live data directory."""
    backup = Path(backup_path).expanduser().absolute()
    _regular_private_file(backup, label="Backup archive", maximum=_MAX_ARCHIVE_BYTES)
    destination = Path(destination_data_dir).expanduser().absolute()
    _reject_symlink_components(destination)
    if destination.exists():
        raise PersonalBackupError("Restore destination must not already exist.")
    parent = destination.parent
    if not parent.exists() or not parent.is_dir() or parent.is_symlink():
        raise PersonalBackupError("Restore destination parent must be an existing real directory.")

    stage = Path(tempfile.mkdtemp(prefix=".apaa-restore-stage-", dir=parent))
    os.chmod(stage, 0o700)
    try:
        with zipfile.ZipFile(backup, mode="r") as archive:
            infos = archive.infolist()
            names = [item.filename for item in infos]
            if len(names) != len(set(names)):
                raise PersonalBackupError("Backup archive contains duplicate entries.")
            total_uncompressed = 0
            for info in infos:
                mode = info.external_attr >> 16
                if stat.S_ISLNK(mode) or info.is_dir() or "/" in info.filename or "\\" in info.filename:
                    raise PersonalBackupError("Backup archive contains an unsafe entry.")
                limit = _MAX_MANIFEST_BYTES if info.filename == _MANIFEST else _MAX_DATABASE_BYTES
                if info.file_size > limit:
                    raise PersonalBackupError("Backup archive entry exceeds its size limit.")
                total_uncompressed += info.file_size
            if total_uncompressed > _MAX_ARCHIVE_BYTES:
                raise PersonalBackupError("Backup archive expands beyond the configured size limit.")
            if archive.testzip() is not None:
                raise PersonalBackupError("Backup archive CRC verification failed.")
            manifest_bytes = archive.read(_MANIFEST)
            manifest = json.loads(
                manifest_bytes.decode("utf-8"), object_pairs_hook=_unique_object
            )
            if not isinstance(manifest, dict) or manifest.get("format") != _FORMAT:
                raise PersonalBackupError("Backup manifest format is unsupported.")
            version = manifest.get("version")
            if type(version) is not int:
                raise PersonalBackupError("Backup manifest version is unsupported.")
            if version == 1:
                restore_databases = _DATABASES_V1
            elif version == _VERSION:
                restore_databases = _DATABASES
            else:
                raise PersonalBackupError("Backup manifest version is unsupported.")
            expected_names = set(restore_databases) | {_MANIFEST}
            if (
                set(names) != expected_names
                or manifest.get("approval_signing_key_included") is not False
                or not isinstance(manifest.get("files"), dict)
                or set(manifest["files"]) != set(restore_databases)
            ):
                raise PersonalBackupError("Backup archive or manifest inventory is invalid.")

            for filename in restore_databases:
                metadata = manifest["files"][filename]
                if (
                    not isinstance(metadata, dict)
                    or type(metadata.get("size")) is not int
                    or not 0 <= metadata["size"] <= _MAX_DATABASE_BYTES
                    or not isinstance(metadata.get("sha256"), str)
                    or len(metadata["sha256"]) != 64
                ):
                    raise PersonalBackupError("Backup manifest file metadata is invalid.")
                target = stage / filename
                flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0)
                descriptor = os.open(target, flags, 0o600)
                digest = hashlib.sha256()
                written = 0
                try:
                    with os.fdopen(descriptor, "wb") as output, archive.open(filename) as source:
                        while True:
                            chunk = source.read(_CHUNK)
                            if not chunk:
                                break
                            written += len(chunk)
                            if written > metadata["size"]:
                                raise PersonalBackupError("Backup file size does not match its manifest.")
                            digest.update(chunk)
                            output.write(chunk)
                        output.flush()
                        os.fsync(output.fileno())
                except Exception:
                    try:
                        target.unlink()
                    except OSError:
                        pass
                    raise
                if written != metadata["size"] or not hmac.compare_digest(
                    digest.hexdigest(), metadata["sha256"]
                ):
                    raise PersonalBackupError("Backup file hash or size verification failed.")
                _sqlite_integrity(target)

        security_store = SQLiteSecurityStore(stage / "security.sqlite3")
        if not security_store.verify_audit_chain():
            raise PersonalBackupError("Restored durable audit chain failed verification.")
        if version == 1:
            # Legacy backups predate the local Owner passphrase database. Create
            # an unconfigured store so the Owner must perform first-run setup.
            LocalOwnerAuthStore(stage / "owner-auth.sqlite3")
        # Deliberately rotate approval signing material: no pre-restore receipt
        # can be replayed after the recovery boundary.
        load_or_create_approval_signing_key(stage)

        if destination.exists():
            raise PersonalBackupError("Restore destination appeared during restore; refusing overwrite.")
        os.rename(stage, destination)
        return destination
    except PersonalBackupError:
        raise
    except (
        OSError, sqlite3.Error, UnicodeError, json.JSONDecodeError,
        zipfile.BadZipFile, ValueError, RecursionError,
    ) as exc:
        raise PersonalBackupError("Personal backup restore failed safely.") from exc
    finally:
        if stage.exists():
            shutil.rmtree(stage, ignore_errors=True)
