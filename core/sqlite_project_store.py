"""Tenant-scoped SQLite persistence for project CRUD.

All reads and mutations include the validated issuer + subject pair in SQL.
Legacy/unscoped project records are never adopted automatically.
"""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
import os
import sqlite3
import stat
from uuid import uuid4

from core.storage import StoredProject, TenantKey


class SQLiteProjectStore:
    """SQLite implementation of ProjectStore with strict tenant predicates."""

    def __init__(self, database_path: str | Path, *, timeout: float = 10.0) -> None:
        raw_database_path = str(database_path)
        if raw_database_path == ":memory:":
            raise ValueError("SQLiteProjectStore requires a filesystem-backed database path; :memory: is unsupported.")
        self._database_path = str(Path(raw_database_path).absolute())
        self._timeout = timeout
        if self._database_path != ":memory:":
            self._secure_database_file(create_parent=True)
        self._initialize()
        if self._database_path != ":memory:":
            self._secure_database_file(create_parent=False)

    def _secure_database_file(self, *, create_parent: bool) -> None:
        """Reject symlinked parent components and unsafe database targets."""
        path = Path(self._database_path)
        # Checking only path.lstat() misses a symlink in a parent directory.
        # Inspect the lexical absolute path without resolving away symlinks.
        for parent in path.absolute().parents:
            try:
                parent_metadata = parent.lstat()
            except FileNotFoundError:
                continue
            if stat.S_ISLNK(parent_metadata.st_mode):
                raise ValueError("Project database parent path must not contain symlinks.")
        if create_parent:
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        # SQLite rollback journals and WAL sidecars live beside the database.
        # A private database file is not sufficient if other users can list or
        # access its containing directory. Never chmod an existing shared dir.
        parent_metadata = path.parent.stat()
        if not stat.S_ISDIR(parent_metadata.st_mode):
            raise ValueError("Project database parent path must be a directory.")
        if os.name == "posix" and parent_metadata.st_mode & 0o077:
            raise ValueError("Project database parent directory must be owner-only.")
        try:
            metadata = path.lstat()
        except FileNotFoundError:
            # SQLite otherwise creates a new database using the process umask,
            # which may briefly expose it before the post-init chmod. Create it
            # atomically with owner-only permissions before SQLite can open it.
            flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0)
            try:
                descriptor = os.open(path, flags, 0o600)
            except FileExistsError:
                metadata = path.lstat()
            else:
                os.close(descriptor)
                metadata = path.lstat()
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
            raise ValueError("Project database must be a regular, non-symlink file.")
        os.chmod(path, 0o600)

    def _connect(self) -> sqlite3.Connection:
        # Revalidate immediately before every pathname-based SQLite open.
        # This narrows replacement windows but cannot eliminate a hostile same-UID race.
        self._secure_database_file(create_parent=False)
        connection = sqlite3.connect(
            self._database_path, timeout=self._timeout, isolation_level=None
        )
        connection.row_factory = sqlite3.Row
        connection.execute(f"PRAGMA busy_timeout = {int(self._timeout * 1000)}")
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        statements = (
            """CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL
            )""",
            """CREATE TABLE IF NOT EXISTS projects (
                project_id TEXT PRIMARY KEY,
                tenant_issuer TEXT NOT NULL CHECK (length(trim(tenant_issuer)) > 0),
                tenant_subject TEXT NOT NULL CHECK (length(trim(tenant_subject)) > 0),
                name TEXT NOT NULL CHECK (length(trim(name)) BETWEEN 1 AND 80),
                description TEXT NOT NULL DEFAULT '' CHECK (length(description) <= 500),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )""",
            """CREATE INDEX IF NOT EXISTS idx_projects_tenant_created
                ON projects (tenant_issuer, tenant_subject, created_at)""",
            """CREATE INDEX IF NOT EXISTS idx_projects_tenant_id
                ON projects (tenant_issuer, tenant_subject, project_id)""",
        )
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                # Execute statements individually: sqlite3.executescript() may
                # implicitly commit a pending transaction before running.
                for statement in statements:
                    connection.execute(statement)
                connection.execute(
                    "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                    (1, datetime.now(timezone.utc).isoformat()),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise

    @staticmethod
    def _validate(tenant: TenantKey, name: str, description: str) -> None:
        if not isinstance(tenant, TenantKey):
            raise TypeError("A validated TenantKey is required.")
        if not isinstance(name, str) or not name.strip() or len(name.strip()) > 80:
            raise ValueError("Project name must contain 1 to 80 characters.")
        if not isinstance(description, str) or len(description.strip()) > 500:
            raise ValueError("Project description must be 500 characters or fewer.")

    @staticmethod
    def _project(row: sqlite3.Row) -> StoredProject:
        return StoredProject(
            project_id=row["project_id"],
            tenant=TenantKey(row["tenant_issuer"], row["tenant_subject"]),
            name=row["name"],
            description=row["description"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def create(self, tenant: TenantKey, *, name: str, description: str) -> StoredProject:
        self._validate(tenant, name, description)
        now = datetime.now(timezone.utc).isoformat()
        project_id = str(uuid4())
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                connection.execute(
                    """INSERT INTO projects
                       (project_id, tenant_issuer, tenant_subject, name, description, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (project_id, tenant.issuer, tenant.subject, name.strip(),
                     description.strip(), now, now),
                )
                row = connection.execute(
                    "SELECT * FROM projects WHERE project_id = ? AND tenant_issuer = ? AND tenant_subject = ?",
                    (project_id, tenant.issuer, tenant.subject),
                ).fetchone()
                connection.commit()
                return self._project(row)
            except Exception:
                connection.rollback()
                raise

    def list_for_tenant(self, tenant: TenantKey) -> list[StoredProject]:
        if not isinstance(tenant, TenantKey):
            raise TypeError("A validated TenantKey is required.")
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """SELECT * FROM projects
                   WHERE tenant_issuer = ? AND tenant_subject = ?
                   ORDER BY created_at, project_id""",
                (tenant.issuer, tenant.subject),
            ).fetchall()
        return [self._project(row) for row in rows]

    def get_for_tenant(self, tenant: TenantKey, project_id: str) -> StoredProject | None:
        if not isinstance(tenant, TenantKey):
            raise TypeError("A validated TenantKey is required.")
        with closing(self._connect()) as connection:
            row = connection.execute(
                """SELECT * FROM projects
                   WHERE project_id = ? AND tenant_issuer = ? AND tenant_subject = ?""",
                (project_id, tenant.issuer, tenant.subject),
            ).fetchone()
        return self._project(row) if row else None

    def update_for_tenant(
        self, tenant: TenantKey, project_id: str, *, name: str, description: str
    ) -> StoredProject | None:
        self._validate(tenant, name, description)
        now = datetime.now(timezone.utc).isoformat()
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                cursor = connection.execute(
                    """UPDATE projects SET name = ?, description = ?, updated_at = ?
                       WHERE project_id = ? AND tenant_issuer = ? AND tenant_subject = ?""",
                    (name.strip(), description.strip(), now, project_id,
                     tenant.issuer, tenant.subject),
                )
                row = connection.execute(
                    """SELECT * FROM projects
                       WHERE project_id = ? AND tenant_issuer = ? AND tenant_subject = ?""",
                    (project_id, tenant.issuer, tenant.subject),
                ).fetchone() if cursor.rowcount else None
                connection.commit()
                return self._project(row) if row else None
            except Exception:
                connection.rollback()
                raise

    def delete_for_tenant(self, tenant: TenantKey, project_id: str) -> bool:
        if not isinstance(tenant, TenantKey):
            raise TypeError("A validated TenantKey is required.")
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                cursor = connection.execute(
                    """DELETE FROM projects
                       WHERE project_id = ? AND tenant_issuer = ? AND tenant_subject = ?""",
                    (project_id, tenant.issuer, tenant.subject),
                )
                connection.commit()
                return cursor.rowcount == 1
            except Exception:
                connection.rollback()
                raise

    def get_by_id_for_internal_use(self, project_id: str) -> StoredProject | None:
        """Trusted UI helper; never expose this unscoped lookup as an authorization boundary."""
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM projects WHERE project_id = ?", (project_id,)
            ).fetchone()
        return self._project(row) if row else None
