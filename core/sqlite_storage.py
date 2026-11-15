"""Local SQLite implementation of the tenant-scoped ProjectStore contract."""
from __future__ import annotations

import os
import sqlite3
from contextlib import closing
import uuid
from datetime import datetime, timezone
from pathlib import Path
import stat

from core.storage import (
    SCHEMA_VERSION,
    SQLITE_SCHEMA_V1,
    StoredProject,
    TenantKey,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _validate_fields(name: str, description: str) -> None:
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 80:
        raise ValueError("Project name must contain 1 to 80 characters.")
    if not isinstance(description, str) or len(description) > 500:
        raise ValueError("Project description must be text up to 500 characters.")


class SQLiteProjectStore:
    """SQLite-backed store; every project query is scoped by issuer and subject.

    TenantKey must be created from a validated server-side Principal. This
    adapter deliberately has no API that accepts an owner from client payload.
    """

    def __init__(self, database_path: str | Path, *, timeout: float = 5.0) -> None:
        self._database_path = str(database_path)
        self._timeout = timeout
        if self._database_path != ":memory:":
            self._secure_database_file(create_parent=True)
        self._initialize()
        if self._database_path != ":memory:":
            self._secure_database_file(create_parent=False)

    def _secure_database_file(self, *, create_parent: bool) -> None:
        """Reject symlinked parents/targets and restrict database file access."""
        path = Path(self._database_path)
        # Inspect lexical parents so symlinks are not hidden by path resolution.
        for parent in path.absolute().parents:
            try:
                parent_metadata = parent.lstat()
            except FileNotFoundError:
                continue
            if stat.S_ISLNK(parent_metadata.st_mode):
                raise ValueError("Project database parent path must not contain symlinks.")
        if create_parent:
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            metadata = path.lstat()
        except FileNotFoundError:
            # Pre-create with owner-only permissions before SQLite opens it;
            # post-initialization chmod alone leaves a brief umask-dependent window.
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
        # Project names and descriptions may contain private user information.
        os.chmod(path, 0o600)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self._database_path, timeout=self._timeout, isolation_level=None
        )
        connection.row_factory = sqlite3.Row
        connection.execute(f"PRAGMA busy_timeout = {int(self._timeout * 1000)}")
        return connection

    def _initialize(self) -> None:
        # Execute statements separately so the migration ledger and schema
        # creation remain inside one explicit transaction.
        statements = [part.strip() for part in SQLITE_SCHEMA_V1.split(";") if part.strip()]
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                for statement in statements:
                    connection.execute(statement)
                connection.execute(
                    "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                    (SCHEMA_VERSION, _utc_now()),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise

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
        _validate_fields(name, description)
        now = _utc_now()
        project_id = str(uuid.uuid4())
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                connection.execute(
                    """INSERT INTO projects
                       (project_id, tenant_issuer, tenant_subject, name, description, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (project_id, tenant.issuer, tenant.subject, name.strip(), description, now, now),
                )
                row = connection.execute(
                    """SELECT * FROM projects
                       WHERE project_id = ? AND tenant_issuer = ? AND tenant_subject = ?""",
                    (project_id, tenant.issuer, tenant.subject),
                ).fetchone()
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return self._to_project(row)

    def list_for_tenant(self, tenant: TenantKey) -> list[StoredProject]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """SELECT * FROM projects
                   WHERE tenant_issuer = ? AND tenant_subject = ?
                   ORDER BY created_at, project_id""",
                (tenant.issuer, tenant.subject),
            ).fetchall()
        return [self._to_project(row) for row in rows]

    def get_for_tenant(self, tenant: TenantKey, project_id: str) -> StoredProject | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                """SELECT * FROM projects
                   WHERE project_id = ? AND tenant_issuer = ? AND tenant_subject = ?""",
                (project_id, tenant.issuer, tenant.subject),
            ).fetchone()
        return self._to_project(row) if row else None

    def update_for_tenant(
        self, tenant: TenantKey, project_id: str, *, name: str, description: str
    ) -> StoredProject | None:
        _validate_fields(name, description)
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                cursor = connection.execute(
                    """UPDATE projects SET name = ?, description = ?, updated_at = ?
                       WHERE project_id = ? AND tenant_issuer = ? AND tenant_subject = ?""",
                    (name.strip(), description, _utc_now(), project_id, tenant.issuer, tenant.subject),
                )
                row = None
                if cursor.rowcount:
                    row = connection.execute(
                        """SELECT * FROM projects
                           WHERE project_id = ? AND tenant_issuer = ? AND tenant_subject = ?""",
                        (project_id, tenant.issuer, tenant.subject),
                    ).fetchone()
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return self._to_project(row) if row else None

    def delete_for_tenant(self, tenant: TenantKey, project_id: str) -> bool:
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
