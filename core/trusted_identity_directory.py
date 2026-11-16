"""Closed, opt-in directory of previously authenticated OIDC identities.

This module is a server-side directory primitive only. It does not authenticate
users or expose invitations/routes. Callers must pass Principal objects created
by the trusted OIDC adapter, never values assembled from client input.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from core.identity import Principal, require_authenticated
from core.project_access import ProjectAccessControl


@dataclass(frozen=True)
class DirectoryIdentity:
    """Minimal owner-visible identity summary; contains no email or token."""

    directory_id: str
    display_label: str | None
    first_seen_at: str
    last_seen_at: str


class SQLiteTrustedIdentityDirectory:
    """Persistent opt-in directory scoped to explicitly allowed OIDC issuers.

    Enrollment is private by default. A user must explicitly opt into owner
    discovery before appearing in any project's selectable identity list.
    Directory IDs are opaque selectors, not bearer capabilities.
    """

    def __init__(self, database_path: str | Path, *, allowed_issuers: set[str] | tuple[str, ...]):
        if not isinstance(database_path, (str, Path)) or not str(database_path).strip():
            raise ValueError("A persistent directory database path is required.")
        if not isinstance(allowed_issuers, (set, tuple, list)) or not allowed_issuers:
            raise ValueError("At least one explicitly allowed OIDC issuer is required.")
        issuers = frozenset(allowed_issuers)
        if any(not isinstance(item, str) or not item.strip() for item in issuers):
            raise ValueError("OIDC issuer allowlist entries must be non-empty strings.")
        self._path = str(database_path)
        if self._path == ":memory:":
            raise ValueError("An in-memory directory is not durable and is not supported.")
        self._allowed_issuers = issuers
        Path(self._path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS trusted_identity_directory (
                    directory_id TEXT PRIMARY KEY,
                    issuer TEXT NOT NULL CHECK(length(trim(issuer)) > 0),
                    subject TEXT NOT NULL CHECK(length(trim(subject)) > 0),
                    display_label TEXT,
                    discoverable INTEGER NOT NULL DEFAULT 0 CHECK(discoverable IN (0, 1)),
                    first_seen_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    UNIQUE(issuer, subject)
                )"""
            )
            connection.execute(
                """CREATE INDEX IF NOT EXISTS idx_trusted_identity_discoverable
                   ON trusted_identity_directory(issuer, discoverable, last_seen_at)"""
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def _principal(self, principal: Principal | None) -> Principal:
        verified = require_authenticated(principal)
        if verified.issuer not in self._allowed_issuers:
            raise PermissionError("The authenticated OIDC issuer is not allowlisted.")
        return verified

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _label(value: str | None) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("Display label must be text.")
        label = " ".join(value.split())
        if not label:
            return None
        if len(label) > 80 or any(ord(char) < 32 for char in label):
            raise ValueError("Display label is malformed or too long.")
        return label

    def record_authenticated_principal(
        self, principal: Principal, *, provider_display_label: str | None = None
    ) -> str:
        """Record a trusted sign-in; first enrollment is never discoverable."""
        verified = self._principal(principal)
        label = self._label(provider_display_label)
        now = self._now()
        with self._connect() as connection:
            row = connection.execute(
                """SELECT directory_id FROM trusted_identity_directory
                   WHERE issuer = ? AND subject = ?""",
                (verified.issuer, verified.subject),
            ).fetchone()
            if row is None:
                directory_id = uuid4().hex
                connection.execute(
                    """INSERT INTO trusted_identity_directory
                       (directory_id, issuer, subject, display_label, discoverable,
                        first_seen_at, last_seen_at)
                       VALUES (?, ?, ?, ?, 0, ?, ?)""",
                    (directory_id, verified.issuer, verified.subject, label, now, now),
                )
                return directory_id
            connection.execute(
                """UPDATE trusted_identity_directory
                   SET last_seen_at = ?, display_label = COALESCE(?, display_label)
                   WHERE directory_id = ?""",
                (now, label, row["directory_id"]),
            )
            return str(row["directory_id"])

    def set_discoverability(self, principal: Principal, *, discoverable: bool) -> None:
        """Allow an authenticated user to opt in/out of owner directory discovery."""
        verified = self._principal(principal)
        if not isinstance(discoverable, bool):
            raise TypeError("discoverable must be a boolean.")
        with self._connect() as connection:
            cursor = connection.execute(
                """UPDATE trusted_identity_directory SET discoverable = ?, last_seen_at = ?
                   WHERE issuer = ? AND subject = ?""",
                (1 if discoverable else 0, self._now(), verified.issuer, verified.subject),
            )
            if cursor.rowcount != 1:
                raise LookupError("The identity must sign in before changing directory visibility.")

    @staticmethod
    def _require_project_owner(
        owner: Principal, project_id: str, access_control: ProjectAccessControl
    ) -> Principal:
        verified = require_authenticated(owner)
        if not isinstance(access_control, ProjectAccessControl):
            raise TypeError("A ProjectAccessControl instance is required.")
        if not isinstance(project_id, str) or not project_id.strip():
            raise ValueError("A project ID is required.")
        if not access_control.is_owner(project_id, verified):
            raise PermissionError("Only the exact project owner may browse directory identities.")
        return verified

    def list_owner_selectable_identities(
        self, project_id: str, *, owner: Principal,
        access_control: ProjectAccessControl,
    ) -> list[DirectoryIdentity]:
        """List opted-in identities from the owner's exact issuer only."""
        verified_owner = self._require_project_owner(owner, project_id, access_control)
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT directory_id, display_label, first_seen_at, last_seen_at
                   FROM trusted_identity_directory
                   WHERE issuer = ? AND discoverable = 1 AND subject != ?
                   ORDER BY display_label COLLATE NOCASE, first_seen_at, directory_id""",
                (verified_owner.issuer, verified_owner.subject),
            ).fetchall()
        return [
            DirectoryIdentity(
                row["directory_id"], row["display_label"],
                row["first_seen_at"], row["last_seen_at"],
            )
            for row in rows
        ]

    def resolve_owner_selection(
        self, project_id: str, directory_id: str, *, owner: Principal,
        access_control: ProjectAccessControl,
    ) -> Principal:
        """Resolve an opaque selector to a trusted server-side Principal.

        This result is suitable for passing to OwnerProjectAccessController;
        the caller must still require explicit owner confirmation for the
        exact project and read-only permission.
        """
        verified_owner = self._require_project_owner(owner, project_id, access_control)
        if not isinstance(directory_id, str) or not directory_id.strip():
            raise LookupError("The selected directory identity is unavailable.")
        with self._connect() as connection:
            row = connection.execute(
                """SELECT issuer, subject FROM trusted_identity_directory
                   WHERE directory_id = ? AND issuer = ? AND discoverable = 1""",
                (directory_id, verified_owner.issuer),
            ).fetchone()
        if row is None or row["subject"] == verified_owner.subject:
            raise LookupError("The selected directory identity is unavailable.")
        return Principal(
            subject=str(row["subject"]),
            issuer=str(row["issuer"]),
            authenticated=True,
            roles=(),
        )
