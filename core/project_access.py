"""Owner-controlled, fail-closed project access grants.

This is a persistence primitive only. It does not by itself expose shared
projects in the UI or change PersistentProjectRegistry authorization. Callers
must use has_access at every server-side resource boundary.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from core.identity import Principal, require_authenticated
from core.sqlite_project_store import SQLiteProjectStore


@dataclass(frozen=True)
class ProjectAccessGrant:
    project_id: str
    issuer: str
    subject: str
    granted_by_issuer: str
    granted_by_subject: str
    granted_at: str
    revoked_at: str | None


class ProjectAccessControl:
    """Durable owner-managed read-access grants bound to OIDC issuer + subject."""

    def __init__(self, store: SQLiteProjectStore) -> None:
        if not isinstance(store, SQLiteProjectStore):
            raise TypeError("A SQLiteProjectStore is required.")
        self._store = store
        with self._store._connect() as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS project_access_grants (
                    project_id TEXT NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
                    grantee_issuer TEXT NOT NULL CHECK(length(trim(grantee_issuer)) > 0),
                    grantee_subject TEXT NOT NULL CHECK(length(trim(grantee_subject)) > 0),
                    granted_by_issuer TEXT NOT NULL CHECK(length(trim(granted_by_issuer)) > 0),
                    granted_by_subject TEXT NOT NULL CHECK(length(trim(granted_by_subject)) > 0),
                    granted_at TEXT NOT NULL,
                    revoked_at TEXT,
                    PRIMARY KEY(project_id, grantee_issuer, grantee_subject)
                )"""
            )
            connection.execute(
                """CREATE INDEX IF NOT EXISTS idx_project_access_active
                   ON project_access_grants(grantee_issuer, grantee_subject, revoked_at)"""
            )

    @staticmethod
    def _identity(principal: Principal) -> tuple[str, str]:
        verified = require_authenticated(principal)
        return verified.issuer, verified.subject

    def grant_read(self, project_id: str, owner: Principal, grantee: Principal) -> ProjectAccessGrant:
        """Grant read access; only the exact owner may grant and owner identity is immutable."""
        owner_issuer, owner_subject = self._identity(owner)
        grantee_issuer, grantee_subject = self._identity(grantee)
        if (owner_issuer, owner_subject) == (grantee_issuer, grantee_subject):
            raise ValueError("The owner already has access and cannot be added as a grantee.")
        now = datetime.now(timezone.utc).isoformat()
        with self._store._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                project = connection.execute(
                    """SELECT 1 FROM projects WHERE project_id = ?
                       AND tenant_issuer = ? AND tenant_subject = ?""",
                    (project_id, owner_issuer, owner_subject),
                ).fetchone()
                if project is None:
                    raise PermissionError("Only the project owner may grant access.")
                connection.execute(
                    """INSERT INTO project_access_grants
                       (project_id, grantee_issuer, grantee_subject, granted_by_issuer,
                        granted_by_subject, granted_at, revoked_at)
                       VALUES (?, ?, ?, ?, ?, ?, NULL)
                       ON CONFLICT(project_id, grantee_issuer, grantee_subject)
                       DO UPDATE SET granted_by_issuer=excluded.granted_by_issuer,
                         granted_by_subject=excluded.granted_by_subject,
                         granted_at=excluded.granted_at, revoked_at=NULL""",
                    (project_id, grantee_issuer, grantee_subject, owner_issuer,
                     owner_subject, now),
                )
                row = connection.execute(
                    """SELECT * FROM project_access_grants WHERE project_id = ?
                       AND grantee_issuer = ? AND grantee_subject = ?""",
                    (project_id, grantee_issuer, grantee_subject),
                ).fetchone()
                connection.commit()
                return ProjectAccessGrant(
                    row["project_id"], row["grantee_issuer"], row["grantee_subject"],
                    row["granted_by_issuer"], row["granted_by_subject"],
                    row["granted_at"], row["revoked_at"],
                )
            except Exception:
                connection.rollback()
                raise

    def revoke_read(self, project_id: str, owner: Principal, grantee: Principal) -> bool:
        """Revoke a grantee; only the owner can revoke and cannot revoke themself."""
        owner_issuer, owner_subject = self._identity(owner)
        grantee_issuer, grantee_subject = self._identity(grantee)
        if (owner_issuer, owner_subject) == (grantee_issuer, grantee_subject):
            raise ValueError("The owner cannot revoke their own ownership access.")
        with self._store._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                project = connection.execute(
                    """SELECT 1 FROM projects WHERE project_id = ?
                       AND tenant_issuer = ? AND tenant_subject = ?""",
                    (project_id, owner_issuer, owner_subject),
                ).fetchone()
                if project is None:
                    raise PermissionError("Only the project owner may revoke access.")
                cursor = connection.execute(
                    """UPDATE project_access_grants SET revoked_at = ?
                       WHERE project_id = ? AND grantee_issuer = ?
                         AND grantee_subject = ? AND revoked_at IS NULL""",
                    (datetime.now(timezone.utc).isoformat(), project_id,
                     grantee_issuer, grantee_subject),
                )
                connection.commit()
                return cursor.rowcount == 1
            except Exception:
                connection.rollback()
                raise

    def has_access(self, project_id: str, principal: Principal) -> bool:
        """Return owner or active-grantee access; invalid identities fail closed."""
        try:
            issuer, subject = self._identity(principal)
        except (PermissionError, TypeError, ValueError):
            return False
        with self._store._connect() as connection:
            project = connection.execute(
                "SELECT tenant_issuer, tenant_subject FROM projects WHERE project_id = ?",
                (project_id,),
            ).fetchone()
            if project is None:
                return False
            if (project["tenant_issuer"], project["tenant_subject"]) == (issuer, subject):
                return True
            grant = connection.execute(
                """SELECT 1 FROM project_access_grants WHERE project_id = ?
                   AND grantee_issuer = ? AND grantee_subject = ? AND revoked_at IS NULL""",
                (project_id, issuer, subject),
            ).fetchone()
            return grant is not None

    def list_for_owner(self, project_id: str, owner: Principal) -> list[ProjectAccessGrant]:
        """List grants only for the exact project owner; revoked records remain auditable."""
        issuer, subject = self._identity(owner)
        with self._store._connect() as connection:
            project = connection.execute(
                """SELECT 1 FROM projects WHERE project_id = ?
                   AND tenant_issuer = ? AND tenant_subject = ?""",
                (project_id, issuer, subject),
            ).fetchone()
            if project is None:
                raise PermissionError("Only the project owner may list access grants.")
            rows = connection.execute(
                """SELECT * FROM project_access_grants WHERE project_id = ?
                   ORDER BY granted_at, grantee_issuer, grantee_subject""",
                (project_id,),
            ).fetchall()
        return [
            ProjectAccessGrant(
                row["project_id"], row["grantee_issuer"], row["grantee_subject"],
                row["granted_by_issuer"], row["granted_by_subject"],
                row["granted_at"], row["revoked_at"],
            )
            for row in rows
        ]
