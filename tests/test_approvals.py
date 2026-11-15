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
    receipt = first_authority.issue("write_file", payload)

    assert first_authority.consume(receipt, "write_file", payload) is True
    second_authority = ApprovalAuthority(
        nonce_store=SQLiteSecurityStore(path), signing_secret=secret
    )
    assert second_authority.consume(receipt, "write_file", payload, tenant=tenant) is False


def test_durable_nonce_mode_fails_closed_without_validated_tenant(tmp_path):
    from core.sqlite_security_store import SQLiteSecurityStore

    authority = ApprovalAuthority(
        nonce_store=SQLiteSecurityStore(tmp_path / "security.sqlite3"),
        signing_secret=b"test-only-signing-secret-material-32-bytes-minimum",
    )
    payload = {"path": "tenant-required.txt"}
    receipt = authority.issue("write_file", payload)
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
    receipt = authority.issue("write_file", payload)
    assert authority.consume(receipt, "write_file", payload, tenant=tenant) is True
    assert authority.consume(receipt, "write_file", payload, tenant=tenant) is False
