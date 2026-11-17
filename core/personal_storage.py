"""Owner-private SQLite persistence for APAA Personal Edition projects.

This adapter is intentionally local-only. The caller must obtain the tenant
from trusted server-side runtime state; never accept tenant identity from task
text, query parameters, or browser-controlled fields.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import os
from pathlib import Path
import sqlite3
import stat
from typing import Iterator
from uuid import uuid4

from core.personal_runtime import ensure_private_data_dir
from core.storage import StoredProject, TenantKey


_SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS projects (
    project_id TEXT PRIMARY KEY,
    tenant_issuer TEXT NOT NULL CHECK(length(trim(tenant_issuer)) > 0),
    tenant_subject TEXT NOT NULL CHECK(length(trim(tenant_subject)) > 0),
    name TEXT NOT NULL CHECK(length(trim(name)) BETWEEN 1 AND 80),
    description TEXT NOT NULL DEFAULT '' CHECK(length(description) <= 500),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_personal_projects_owner
ON projects(tenant_issuer, tenant_subject, created_at, project_id);
"""

_SCHEMA_VERSION = 1


def _validate_database_file(path: Path, *, create: bool) -> None:
    """Create a 0600 database file atomically or reject unsafe existing files."""
    if path.is_symlink():
        raise ValueError("Personal database must not be a symlink.")
    if not path.exists() and create:
        flags = os.O_CREAT | os.O_EXCL | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(path, flags, 0o600)
        except FileExistsError:
            pass
        except OSError as exc:
            raise ValueError("Could not safely create personal database.") from exc
        else:
            os.close(descriptor)
    try:
        metadata = path.lstat()
    except FileNotFoundError as exc:
        raise ValueError("Personal database does not exist.") from exc
    if not stat.S_ISREG(metadata.st_mode):
        raise ValueError("Personal database must be a regular file.")
    if os.name == "posix" and metadata.st_mode & 0o077:
        raise ValueError("Personal database must be owner-only (0600).")


class SQLitePersonalProjectStore:
    """SQLite project store with mandatory composite owner scoping."""

    def __init__(self, database_path: str | Path) -> None:
        requested = Path(database_path).expanduser().absolute()
        ensure_private_data_dir(requested.parent)
        _validate_database_file(requested, create=True)
        self.path = requested
        self._initialize()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        _validate_database_file(self.path, create=False)
        connection = sqlite3.connect(self.path, timeout=10, isolation_level="IMMEDIATE")
        try:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA busy_timeout = 10000")
            yield connection
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(_SCHEMA)
            row = connection.execute(
                "SELECT version FROM schema_migrations ORDER BY version DESC LIMIT 1"
            ).fetchone()
            if row is None:
                connection.execute(
                    "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                    (_SCHEMA_VERSION, datetime.now(timezone.utc).isoformat()),
                )
            elif row["version"] != _SCHEMA_VERSION:
                raise RuntimeError("Unsupported personal project database schema version.")

    @staticmethod
    def _validate_fields(name: str, description: str) -> tuple[str, str]:
        if not isinstance(name, str) or not name.strip() or len(name.strip()) > 80:
            raise ValueError("Project name must contain 1–80 characters.")
        if not isinstance(description, str) or len(description) > 500:
            raise ValueError("Project description must be at most 500 characters.")
        return name.strip(), description.strip()

    @staticmethod
    def _to_project(row: sqlite3.Row) -> StoredProject:
        return StoredProject(
            project_id=row["project_id"],
            tenant=TenantKey(row["tenant_issuer"], row["tenant_subject"]),
            name=row["name"],
            description=row["description"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def create(self, tenant: TenantKey, *, name: str, description: str = "") -> StoredProject:
        if not isinstance(tenant, TenantKey):
            raise TypeError("A trusted TenantKey is required.")
        name, description = self._validate_fields(name, description)
        now = datetime.now(timezone.utc).isoformat()
        project_id = str(uuid4())
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO projects
                (project_id, tenant_issuer, tenant_subject, name, description, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (project_id, tenant.issuer, tenant.subject, name, description, now, now),
            )
            row = connection.execute(
                "SELECT * FROM projects WHERE project_id = ? AND tenant_issuer = ? AND tenant_subject = ?",
                (project_id, tenant.issuer, tenant.subject),
            ).fetchone()
        return self._to_project(row)

    def list_for_tenant(self, tenant: TenantKey) -> list[StoredProject]:
        if not isinstance(tenant, TenantKey):
            raise TypeError("A trusted TenantKey is required.")
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT * FROM projects WHERE tenant_issuer = ? AND tenant_subject = ?
                ORDER BY created_at, project_id""",
                (tenant.issuer, tenant.subject),
            ).fetchall()
        return [self._to_project(row) for row in rows]

    def get_for_tenant(self, tenant: TenantKey, project_id: str) -> StoredProject | None:
        if not isinstance(tenant, TenantKey) or not isinstance(project_id, str):
            return None
        with self._connect() as connection:
            row = connection.execute(
                """SELECT * FROM projects WHERE project_id = ?
                AND tenant_issuer = ? AND tenant_subject = ?""",
                (project_id, tenant.issuer, tenant.subject),
            ).fetchone()
        return self._to_project(row) if row else None

    def update_for_tenant(
        self, tenant: TenantKey, project_id: str, *, name: str, description: str
    ) -> StoredProject | None:
        if not isinstance(tenant, TenantKey) or not isinstance(project_id, str):
            return None
        name, description = self._validate_fields(name, description)
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            result = connection.execute(
                """UPDATE projects SET name = ?, description = ?, updated_at = ?
                WHERE project_id = ? AND tenant_issuer = ? AND tenant_subject = ?""",
                (name, description, now, project_id, tenant.issuer, tenant.subject),
            )
            if result.rowcount != 1:
                return None
            row = connection.execute(
                """SELECT * FROM projects WHERE project_id = ?
                AND tenant_issuer = ? AND tenant_subject = ?""",
                (project_id, tenant.issuer, tenant.subject),
            ).fetchone()
        return self._to_project(row) if row else None

    def delete_for_tenant(self, tenant: TenantKey, project_id: str) -> bool:
        if not isinstance(tenant, TenantKey) or not isinstance(project_id, str):
            return False
        with self._connect() as connection:
            result = connection.execute(
                """DELETE FROM projects WHERE project_id = ?
                AND tenant_issuer = ? AND tenant_subject = ?""",
                (project_id, tenant.issuer, tenant.subject),
            )
        return result.rowcount == 1
