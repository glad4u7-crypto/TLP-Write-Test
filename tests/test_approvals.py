from dataclasses import replace

import pytest

from core.approvals import ApprovalAuthority


def test_approval_requires_explicit_user_confirmation():
    authority = ApprovalAuthority()
    with pytest.raises(PermissionError):
        authority.issue(
            "write_file",
            {"path": "a.txt"},
            confirmed_by_user=False,
        )


def test_financial_or_unknown_action_cannot_receive_approval():
    authority = ApprovalAuthority()
    for action in ("place_order", "run_shell", "external_api_request"):
        with pytest.raises(PermissionError):
            authority.issue(action, {}, confirmed_by_user=True)


def test_receipt_is_bound_to_exact_payload_and_action():
    authority = ApprovalAuthority()
    payload = {"path": "a.txt"}
    receipt = authority.issue(
        "write_file", payload, confirmed_by_user=True
    )

    assert authority.consume(receipt, "write_file", payload) is True


def test_receipt_rejects_payload_tampering():
    authority = ApprovalAuthority()
    receipt = authority.issue(
        "write_file", {"path": "a.txt"}, confirmed_by_user=True
    )

    assert authority.consume(
        receipt, "write_file", {"path": "b.txt"}
    ) is False


def test_receipt_rejects_signature_tampering():
    authority = ApprovalAuthority()
    receipt = authority.issue(
        "write_file", {"path": "a.txt"}, confirmed_by_user=True
    )
    tampered = replace(receipt, signature="0" * len(receipt.signature))

    assert authority.consume(
        tampered, "write_file", {"path": "a.txt"}
    ) is False


def test_receipt_rejects_replay():
    authority = ApprovalAuthority()
    payload = {"path": "a.txt"}
    receipt = authority.issue(
        "write_file", payload, confirmed_by_user=True
    )

    assert authority.consume(receipt, "write_file", payload) is True
    assert authority.consume(receipt, "write_file", payload) is False


def test_expired_receipt_is_rejected():
    authority = ApprovalAuthority()
    receipt = authority.issue(
        "write_file", {"path": "a.txt"}, confirmed_by_user=True
    )
    expired = replace(receipt, expires_at=1)

    assert authority.consume(
        expired, "write_file", {"path": "a.txt"}
    ) is False


def test_expiry_is_bounded_and_requires_integer():
    authority = ApprovalAuthority()
    for ttl in (0, 301, True):
        with pytest.raises(ValueError):
            authority.issue(
                "write_file",
                {"path": "a.txt"},
                confirmed_by_user=True,
                ttl_seconds=ttl,
            )
