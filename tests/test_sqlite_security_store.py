from concurrent.futures import ThreadPoolExecutor

import pytest

from core.storage import TenantKey
from core.sqlite_security_store import DurableAuditEvent, SQLiteSecurityStore


@pytest.fixture
def security_store(tmp_path):
    return SQLiteSecurityStore(tmp_path / "security.sqlite3")


def test_nonce_is_single_use_and_tenant_scoped(security_store):
    alice = TenantKey("https://issuer.example", "alice")
    bob = TenantKey("https://issuer.example", "bob")
    assert security_store.consume_approval_nonce(alice, "nonce-1", 500, now=100)
    assert not security_store.consume_approval_nonce(alice, "nonce-1", 500, now=100)
    assert security_store.consume_approval_nonce(bob, "nonce-1", 500, now=100)


def test_expired_nonce_is_rejected(security_store):
    tenant = TenantKey("https://issuer.example", "alice")
    assert not security_store.consume_approval_nonce(tenant, "expired", 100, now=100)


def test_invalid_nonce_inputs_fail_closed(security_store):
    tenant = TenantKey("https://issuer.example", "alice")
    assert not security_store.consume_approval_nonce(tenant, "", 500, now=100)
    assert not security_store.consume_approval_nonce(tenant, "n", True, now=100)


def test_concurrent_duplicate_nonce_has_exactly_one_winner(security_store):
    tenant = TenantKey("https://issuer.example", "alice")
    def attempt(_):
        return security_store.consume_approval_nonce(tenant, "race-nonce", 500, now=100)
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(attempt, range(16)))
    assert sum(results) == 1


def test_nonce_persists_after_store_reopen(tmp_path):
    path = tmp_path / "security.sqlite3"
    tenant = TenantKey("https://issuer.example", "alice")
    assert SQLiteSecurityStore(path).consume_approval_nonce(tenant, "persist", 500, now=100)
    assert not SQLiteSecurityStore(path).consume_approval_nonce(tenant, "persist", 500, now=100)


def test_audit_events_are_payload_free_and_chain_verifies(security_store):
    event = DurableAuditEvent(
        action="project.update",
        result="denied",
        reason_code="tenant_mismatch",
        principal_fingerprint="sha256:principal",
        request_id="req-123",
    )
    security_store.append_audit_event(event)
    security_store.append_audit_event(
        DurableAuditEvent("project.read", "allowed", "ok", "sha256:principal", "req-124")
    )
    assert security_store.verify_audit_chain()


def test_audit_event_rejects_payload_like_or_unbounded_fields(security_store):
    with pytest.raises(ValueError):
        security_store.append_audit_event(
            DurableAuditEvent("x" * 257, "ok", "ok", "fp", "req")
        )


def test_audit_chain_detects_modified_row(security_store, tmp_path):
    path = tmp_path / "tamper.sqlite3"
    store = SQLiteSecurityStore(path)
    store.append_audit_event(DurableAuditEvent("action", "ok", "ok", "fp", "req"))
    import sqlite3
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE durable_audit_events SET action = 'tampered'")
    assert not store.verify_audit_chain()


def test_execution_audit_adapter_satisfies_gateway_append_verify_contract(tmp_path):
    from types import SimpleNamespace
    from core.sqlite_security_store import SQLiteExecutionAuditLog

    store = SQLiteSecurityStore(tmp_path / "adapter.sqlite3")
    tenant = TenantKey("https://issuer.example", "alice")
    audit = SQLiteExecutionAuditLog(store, tenant)
    assert audit.verify() == audit.GENESIS
    audit.append(SimpleNamespace(action="project.create", executed=False, reason="denied"))
    assert audit.verify() != audit.GENESIS
    assert store.verify_audit_chain()


def test_execution_audit_adapter_persists_only_principal_fingerprint(tmp_path):
    from types import SimpleNamespace
    import sqlite3
    from core.sqlite_security_store import SQLiteExecutionAuditLog

    path = tmp_path / "adapter.sqlite3"
    store = SQLiteSecurityStore(path)
    audit = SQLiteExecutionAuditLog(store, TenantKey("https://issuer.example", "alice"))
    audit.append(SimpleNamespace(action="project.create", executed=False, reason="denied"))
    with sqlite3.connect(path) as connection:
        row = connection.execute(
            "SELECT principal_fingerprint FROM durable_audit_events"
        ).fetchone()
    assert row[0] == __import__("hashlib").sha256(
        b"https://issuer.example\nalice"
    ).hexdigest()
    assert "alice" not in row[0]
