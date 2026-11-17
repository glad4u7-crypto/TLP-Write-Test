from __future__ import annotations

from core.approvals import ApprovalAuthority
from core.audit import create_audit_event
from core.personal_runtime import (
    PERSONAL_OWNER_TENANT,
    load_or_create_approval_signing_key,
    personal_runtime_paths,
)
from core.persistent_projects import PersistentProjectRegistry
from core.project_actions import build_project_gateway
from core.sqlite_project_store import SQLiteProjectStore
from core.sqlite_security_store import SQLiteExecutionAuditLog, SQLiteSecurityStore


def _personal_runtime(tmp_path):
    paths = personal_runtime_paths(tmp_path / "apaa-personal")
    key = load_or_create_approval_signing_key(paths.data_dir)
    security = SQLiteSecurityStore(paths.security_db)
    projects = SQLiteProjectStore(paths.projects_db)
    authority = ApprovalAuthority(nonce_store=security, signing_secret=key)
    audit = SQLiteExecutionAuditLog(security, PERSONAL_OWNER_TENANT)
    registry = PersistentProjectRegistry(projects, PERSONAL_OWNER_TENANT)
    gateway = build_project_gateway(
        registry, authority, audit_log=audit, session_scope="local-ui-session"
    )
    return paths, security, projects, authority, audit, registry, gateway


def test_local_personal_runtime_project_survives_runtime_recreation(tmp_path):
    _, _, _, authority, _, registry, gateway = _personal_runtime(tmp_path)
    payload = {"name": "Personal workspace", "description": "Saved on device"}
    receipt = authority.issue(
        "create_project",
        payload,
        tenant=PERSONAL_OWNER_TENANT,
        session_scope="local-ui-session",
    )
    result = gateway.execute(
        "create_project",
        payload,
        approval_receipt=receipt,
        tenant=PERSONAL_OWNER_TENANT,
    )
    assert result.executed is True
    created_id = result.output.project_id

    _, _, _, _, _, reopened_registry, _ = _personal_runtime(tmp_path)
    restored = reopened_registry.get(created_id)
    assert restored is not None
    assert restored.name == "Personal workspace"
    assert restored.owner_issuer == PERSONAL_OWNER_TENANT.issuer
    assert restored.owner_subject == PERSONAL_OWNER_TENANT.subject
    assert [item.project_id for item in reopened_registry.list_projects()] == [created_id]


def test_local_personal_runtime_approval_nonce_and_audit_are_durable(tmp_path):
    paths, security, _, authority, audit, _, gateway = _personal_runtime(tmp_path)
    payload = {"name": "One-time approval", "description": ""}
    receipt = authority.issue(
        "create_project",
        payload,
        tenant=PERSONAL_OWNER_TENANT,
        session_scope="local-ui-session",
    )
    accepted = gateway.execute(
        "create_project", payload, approval_receipt=receipt, tenant=PERSONAL_OWNER_TENANT
    )
    replayed = gateway.execute(
        "create_project", payload, approval_receipt=receipt, tenant=PERSONAL_OWNER_TENANT
    )

    assert accepted.executed is True
    assert replayed.executed is False
    assert security.verify_audit_chain() is True
    assert audit.verify() != audit.GENESIS

    # A new authority instance shares the same durable nonce database and key.
    restored_key = load_or_create_approval_signing_key(paths.data_dir)
    restored_security = SQLiteSecurityStore(paths.security_db)
    restored_authority = ApprovalAuthority(
        nonce_store=restored_security, signing_secret=restored_key
    )
    assert restored_authority.consume(
        receipt,
        "create_project",
        payload,
        tenant=PERSONAL_OWNER_TENANT,
        session_scope="local-ui-session",
    ) is False


def test_personal_runtime_paths_keep_all_durable_state_under_private_root(tmp_path):
    paths, *_ = _personal_runtime(tmp_path)
    assert paths.projects_db.exists()
    assert paths.security_db.exists()
    assert paths.signing_key.exists()
    assert paths.projects_db.parent == paths.data_dir
    assert paths.audit_log.parent == paths.data_dir
