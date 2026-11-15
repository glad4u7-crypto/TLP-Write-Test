import pytest

from core.storage import (
    ProjectStore,
    SQLITE_SCHEMA_V1,
    SCHEMA_VERSION,
    StoredProject,
    TenantKey,
)


def test_tenant_key_requires_both_non_empty_identity_parts():
    with pytest.raises(ValueError, match="issuer"):
        TenantKey("", "alice")
    with pytest.raises(ValueError, match="subject"):
        TenantKey("https://issuer.example.test", " ")


def test_tenant_key_is_composite_and_distinguishes_issuers():
    first = TenantKey("https://issuer-one.example", "alice")
    second = TenantKey("https://issuer-two.example", "alice")
    assert first != second
    assert first.subject == second.subject


def test_stored_project_uses_composite_tenant_key():
    tenant = TenantKey("https://issuer.example", "alice")
    project = StoredProject(
        project_id="p-1",
        tenant=tenant,
        name="Private",
        description="",
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
    )
    assert project.tenant == tenant


def test_project_store_protocol_declares_tenant_scoped_operations():
    assert getattr(ProjectStore, "_is_protocol", False) is True
    for method in (
        "create",
        "list_for_tenant",
        "get_for_tenant",
        "update_for_tenant",
        "delete_for_tenant",
    ):
        assert callable(getattr(ProjectStore, method))


def test_sqlite_schema_has_composite_tenant_columns_and_indexes():
    assert SCHEMA_VERSION == 1
    assert "tenant_issuer TEXT NOT NULL" in SQLITE_SCHEMA_V1
    assert "tenant_subject TEXT NOT NULL" in SQLITE_SCHEMA_V1
    assert "ON projects (tenant_issuer, tenant_subject, created_at)" in SQLITE_SCHEMA_V1
    assert "ON projects (tenant_issuer, tenant_subject, project_id)" in SQLITE_SCHEMA_V1
    assert "owner_subject" not in SQLITE_SCHEMA_V1
