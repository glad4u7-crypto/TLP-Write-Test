from core.sqlite_security_store import SQLiteSecurityStore
from core.storage import TenantKey


def test_owner_reconciliation_is_tenant_scoped_and_atomically_audited(tmp_path):
    store = SQLiteSecurityStore(tmp_path / "security.sqlite3")
    owner = TenantKey("https://owner.example", "owner-1")
    other = TenantKey("https://owner.example", "owner-2")
    key = "owner-recovery-request-0001"
    assert store.claim_execution(owner, key, "project.create", "a" * 64) == "claimed"
    assert store.finish_execution(owner, key, "uncertain") is True
    assert store.resolve_uncertain_execution(
        other, key, "completed", owner_confirmed=True
    ) is False
    assert store.resolve_uncertain_execution(
        owner, key, "completed", owner_confirmed=False
    ) is False
    assert store.list_unresolved_executions(owner)[0]["status"] == "uncertain"
    assert store.resolve_uncertain_execution(
        owner, key, "completed", owner_confirmed=True
    ) is True
    assert store.list_unresolved_executions(owner) == ()
    assert store.verify_audit_chain() is True
    events = store.list_audit_events(
        principal_fingerprint=__import__("hashlib").sha256(
            (owner.issuer + "\\n" + owner.subject).encode("utf-8")
        ).hexdigest(),
        limit=10,
    )
    assert any(
        event["action"] == "execution.reconcile"
        and event["result"] == "completed"
        and event["request_id"] == key
        for event in events
    )
    assert store.resolve_uncertain_execution(
        owner, key, "cancelled", owner_confirmed=True
    ) is False
