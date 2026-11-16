"""Tenant-aware project storage contracts and SQLite schema.

This module defines the persistence boundary only. It does not open databases,
perform migrations, or replace the current in-memory registry yet.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, order=True)
class TenantKey:
    """Stable tenant identity from a validated server-side Principal."""

    issuer: str
    subject: str

    def __post_init__(self) -> None:
        if not isinstance(self.issuer, str) or not self.issuer.strip():
            raise ValueError("Tenant issuer must be non-empty text.")
        if not isinstance(self.subject, str) or not self.subject.strip():
            raise ValueError("Tenant subject must be non-empty text.")


@dataclass(frozen=True)
class StoredProject:
    """Persistence DTO; ownership is represented by a composite tenant key."""

    project_id: str
    tenant: TenantKey
    name: str
    description: str
    created_at: str
    updated_at: str


@runtime_checkable
class ProjectStore(Protocol):
    """Persistence contract. Implementations must enforce tenant scope in storage."""

    def create(self, tenant: TenantKey, *, name: str, description: str) -> StoredProject:
        """Create a project owned by exactly this tenant."""

    def list_for_tenant(self, tenant: TenantKey) -> list[StoredProject]:
        """List only projects belonging to this exact issuer/subject pair."""

    def get_for_tenant(self, tenant: TenantKey, project_id: str) -> StoredProject | None:
        """Return a project only when its composite tenant key matches."""

    def update_for_tenant(
        self, tenant: TenantKey, project_id: str, *, name: str, description: str
    ) -> StoredProject | None:
        """Update only a project belonging to this exact tenant."""

    def delete_for_tenant(self, tenant: TenantKey, project_id: str) -> bool:
        """Delete only a project belonging to this exact tenant."""


# Static schema contract for the planned SQLite adapter. Migration execution is
# intentionally deferred to P08-P07-B after review of legacy-data handling.
SQLITE_SCHEMA_V1 = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS projects (
    project_id TEXT PRIMARY KEY,
    tenant_issuer TEXT NOT NULL CHECK (length(trim(tenant_issuer)) > 0),
    tenant_subject TEXT NOT NULL CHECK (length(trim(tenant_subject)) > 0),
    name TEXT NOT NULL CHECK (length(trim(name)) BETWEEN 1 AND 80),
    description TEXT NOT NULL DEFAULT '' CHECK (length(description) <= 500),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_projects_tenant_created
ON projects (tenant_issuer, tenant_subject, created_at);

CREATE INDEX IF NOT EXISTS idx_projects_tenant_id
ON projects (tenant_issuer, tenant_subject, project_id);
"""

SCHEMA_VERSION = 1
