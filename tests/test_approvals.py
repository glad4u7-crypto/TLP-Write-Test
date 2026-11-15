from dataclasses import replace

import pytest

from core.approvals import ApprovalAuthority


def test_unknown_or_prohibited_action_cannot_receive_approval():
    authority = ApprovalAuthority()
    for action in ("place_order", "run_shell", "external_api_request"):
        with pytest.raises(PermissionError):
            authority.issue(action, {})


def test_receipt_is_bound_to_exact_payload_and_action():
    authority = ApprovalAuthority()
    payload = {"path": "a.txt"}
    receipt = authority.issue("write_file", payload)
    assert authority.consume(receipt, "write_file", payload) is True


def test_receipt_rejects_payload_tampering():
    authority = ApprovalAuthority()
    receipt = authority.issue("write_file", {"path": "a.txt"})
    assert authority.consume(receipt, "write_file", {"path": "b.txt"}) is False


def test_receipt_rejects_signature_tampering():
    authority = ApprovalAuthority()
    receipt = authority.issue("write_file", {"path": "a.txt"})
    tampered = replace(receipt, signature="0" * len(receipt.signature))
    assert authority.consume(tampered, "write_file", {"path": "a.txt"}) is False


def test_receipt_rejects_replay():
    authority = ApprovalAuthority()
    payload = {"path": "a.txt"}
    receipt = authority.issue("write_file", payload)
    assert authority.consume(receipt, "write_file", payload) is True
    assert authority.consume(receipt, "write_file", payload) is False


def test_expired_receipt_is_rejected():
    authority = ApprovalAuthority()
    receipt = authority.issue("write_file", {"path": "a.txt"})
    expired = replace(receipt, expires_at=1)
    assert authority.consume(expired, "write_file", {"path": "a.txt"}) is False


def test_expiry_is_bounded_and_requires_integer():
    authority = ApprovalAuthority()
    for ttl in (0, 301, True):
        with pytest.raises(ValueError):
            authority.issue("write_file", {"path": "a.txt"}, ttl_seconds=ttl)


def test_receipt_from_another_authority_is_rejected():
    issuer = ApprovalAuthority()
    other_authority = ApprovalAuthority()
    payload = {"path": "same.txt"}
    receipt = issuer.issue("write_file", payload)
    assert other_authority.consume(receipt, "write_file", payload) is False


@pytest.mark.parametrize(
    "changes",
    [
        {"action": None},
        {"payload_digest": []},
        {"expires_at": True},
        {"nonce": []},
        {"signature": None},
        {"payload_digest": "not-a-digest"},
        {"signature": "not-a-signature"},
    ],
)
def test_malformed_receipts_fail_closed_without_raising(changes):
    authority = ApprovalAuthority()
    receipt = authority.issue("write_file", {"path": "safe.txt"})
    malformed = replace(receipt, **changes)
    assert authority.consume(malformed, "write_file", {"path": "safe.txt"}) is False


def test_non_json_payload_cannot_receive_or_consume_approval():
    authority = ApprovalAuthority()
    with pytest.raises(ValueError):
        authority.issue("write_file", {"path": object()})

    receipt = authority.issue("write_file", {"path": "safe.txt"})
    assert authority.consume(receipt, "write_file", {"path": object()}) is False


@pytest.mark.parametrize("non_finite", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_json_numbers_cannot_receive_or_consume_approval(non_finite):
    authority = ApprovalAuthority()
    with pytest.raises(ValueError):
        authority.issue("write_file", {"amount": non_finite})

    receipt = authority.issue("write_file", {"amount": 1.0})
    assert authority.consume(
        receipt, "write_file", {"amount": non_finite}
    ) is False


def test_receipt_can_only_be_consumed_once_under_concurrency():
    from concurrent.futures import ThreadPoolExecutor

    authority = ApprovalAuthority()
    payload = {"path": "concurrent.txt"}
    receipt = authority.issue("write_file", payload)

    with ThreadPoolExecutor(max_workers=12) as pool:
        results = list(
            pool.map(
                lambda _: authority.consume(receipt, "write_file", payload),
                range(12),
            )
        )

    assert results.count(True) == 1
    assert results.count(False) == 11


def test_durable_nonce_store_requires_tenant_and_persists_replay_across_authority_restart(tmp_path):
    from core.storage import TenantKey
    from core.sqlite_security_store import SQLiteSecurityStore

    path = tmp_path / "security.sqlite3"
    tenant = TenantKey("https://issuer.example", "alice")
    payload = {"path": "durable.txt"}
    secret = b"test-only-signing-secret-material-32-bytes-minimum"
    first_authority = ApprovalAuthority(
        nonce_store=SQLiteSecurityStore(path), signing_secret=secret
    )
    receipt = first_authority.issue("write_file", payload, tenant=tenant)

    assert first_authority.consume(receipt, "write_file", payload, tenant=tenant) is True
    second_authority = ApprovalAuthority(
        nonce_store=SQLiteSecurityStore(path), signing_secret=secret
    )
    assert second_authority.consume(receipt, "write_file", payload, tenant=tenant) is False


def test_durable_nonce_mode_fails_closed_without_validated_tenant(tmp_path):
    from core.storage import TenantKey
    from core.sqlite_security_store import SQLiteSecurityStore

    authority = ApprovalAuthority(
        nonce_store=SQLiteSecurityStore(tmp_path / "security.sqlite3"),
        signing_secret=b"test-only-signing-secret-material-32-bytes-minimum",
    )
    payload = {"path": "tenant-required.txt"}
    with pytest.raises(ValueError):
        authority.issue("write_file", payload)
    receipt = authority.issue("write_file", payload, tenant=TenantKey("https://issuer.example", "alice"))
    assert authority.consume(receipt, "write_file", payload) is False


def test_durable_nonce_mode_accepts_tenant_and_rejects_replay(tmp_path):
    from core.storage import TenantKey
    from core.sqlite_security_store import SQLiteSecurityStore

    tenant = TenantKey("https://issuer.example", "alice")
    authority = ApprovalAuthority(
        nonce_store=SQLiteSecurityStore(tmp_path / "security.sqlite3"),
        signing_secret=b"test-only-signing-secret-material-32-bytes-minimum",
    )
    payload = {"path": "tenant-bound.txt"}
    receipt = authority.issue("write_file", payload, tenant=tenant)
    assert authority.consume(receipt, "write_file", payload, tenant=tenant) is True
    assert authority.consume(receipt, "write_file", payload, tenant=tenant) is False


def test_durable_approval_receipt_cannot_be_transferred_to_another_issuer(tmp_path):
    from core.storage import TenantKey
    from core.sqlite_security_store import SQLiteSecurityStore

    secret = b"test-only-signing-secret-material-32-bytes-minimum"
    store = SQLiteSecurityStore(tmp_path / "security.sqlite3")
    owner = TenantKey("https://issuer-one.example", "same-subject")
    other = TenantKey("https://issuer-two.example", "same-subject")
    authority = ApprovalAuthority(nonce_store=store, signing_secret=secret)
    payload = {"name": "issuer private", "description": ""}
    receipt = authority.issue("create_project", payload, tenant=owner)
    assert authority.consume(receipt, "create_project", payload, tenant=other) is False
    assert authority.consume(receipt, "create_project", payload, tenant=owner) is True


def test_receipt_is_bound_to_the_originating_session_scope():
    authority = ApprovalAuthority(
        signing_secret=b"session-scope-test-secret-at-least-32-bytes"
    )
    payload = {"name": "session-bound"}
    receipt = authority.issue(
        "write_file", payload, session_scope="session-one"
    )
    assert authority.consume(
        receipt, "write_file", payload, session_scope="session-one"
    ) is True


def test_receipt_from_another_session_is_rejected_even_for_same_tenant(tmp_path):
    from core.storage import TenantKey
    from core.sqlite_security_store import SQLiteSecurityStore

    secret = b"durable-session-scope-test-secret-32-bytes"
    tenant = TenantKey("https://issuer.example", "alice")
    authority = ApprovalAuthority(
        nonce_store=SQLiteSecurityStore(tmp_path / "security.sqlite3"),
        signing_secret=secret,
    )
    payload = {"name": "private"}
    receipt = authority.issue(
        "create_project", payload, tenant=tenant, session_scope="browser-session-A"
    )
    assert authority.consume(
        receipt, "create_project", payload, tenant=tenant,
        session_scope="browser-session-B",
    ) is False
    assert authority.consume(
        receipt, "create_project", payload, tenant=tenant,
        session_scope="browser-session-A",
    ) is True


def test_durable_receipt_has_exactly_one_winner_under_concurrent_consumption(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from core.storage import TenantKey
    from core.sqlite_security_store import SQLiteSecurityStore

    tenant = TenantKey("https://issuer.example", "alice")
    secret = b"concurrent-durable-approval-secret-32-bytes"
    authority = ApprovalAuthority(
        nonce_store=SQLiteSecurityStore(tmp_path / "concurrent.sqlite3"),
        signing_secret=secret,
    )
    payload = {"operation": "update_project", "project_id": "p-123"}
    receipt = authority.issue(
        "update_project", payload, tenant=tenant, session_scope="session-A"
    )

    def consume(_):
        return authority.consume(
            receipt, "update_project", payload,
            tenant=tenant, session_scope="session-A",
        )

    with ThreadPoolExecutor(max_workers=12) as pool:
        results = list(pool.map(consume, range(24)))

    assert results.count(True) == 1
    assert results.count(False) == 23
