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
