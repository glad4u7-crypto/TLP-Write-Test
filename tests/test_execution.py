import pytest

from core.approvals import ApprovalAuthority
from core.execution import ExecutionGateway


def test_gateway_has_no_handlers_by_default():
    result = ExecutionGateway().execute("read")
    assert result.executed is False
    assert "No trusted handler" in result.reason


def test_mutation_is_not_dispatched_without_trusted_receipt():
    calls = []
    gateway = ExecutionGateway({"write_file": lambda payload: calls.append(payload)})

    result = gateway.execute("write_file", {"path": "notes.txt"})

    assert result.executed is False
    assert calls == []


def test_mutation_dispatches_after_payload_bound_receipt():
    calls = []
    authority = ApprovalAuthority()
    payload = {"path": "notes.txt"}
    gateway = ExecutionGateway(
        {"write_file": lambda data: calls.append(data) or "ok"},
        approval_authority=authority,
    )
    receipt = authority.issue(
        "write_file", payload
    )

    result = gateway.execute("write_file", payload, approval_receipt=receipt)

    assert result.executed is True
    assert result.output == "ok"
    assert calls == [payload]


def test_receipt_cannot_authorize_different_action_or_payload():
    authority = ApprovalAuthority()
    calls = []
    gateway = ExecutionGateway(
        {
            "write_file": lambda data: calls.append(data),
            "delete_file": lambda data: calls.append(data),
        },
        approval_authority=authority,
    )
    payload = {"path": "important.txt"}
    receipt = authority.issue(
        "write_file", payload
    )

    wrong_action = gateway.execute(
        "delete_file", payload, approval_receipt=receipt
    )
    wrong_payload = gateway.execute(
        "write_file", {"path": "other.txt"}, approval_receipt=receipt
    )

    assert wrong_action.executed is False
    assert wrong_payload.executed is False
    assert calls == []


def test_receipt_is_one_time_and_cannot_be_replayed():
    authority = ApprovalAuthority()
    calls = []
    payload = {"path": "one.txt"}
    gateway = ExecutionGateway(
        {"write_file": lambda data: calls.append(data)},
        approval_authority=authority,
    )
    receipt = authority.issue(
        "write_file", payload
    )

    first = gateway.execute("write_file", payload, approval_receipt=receipt)
    replay = gateway.execute("write_file", payload, approval_receipt=receipt)

    assert first.executed is True
    assert replay.executed is False
    assert calls == [payload]


@pytest.mark.parametrize(
    "action",
    ["run_shell", "execute_code", "external_api_request", "place_order"],
)
def test_prohibited_or_unknown_actions_cannot_be_registered(action):
    with pytest.raises(ValueError):
        ExecutionGateway({action: lambda payload: "should never run"})


def test_auto_run_requires_exact_allowlist_and_registered_handler():
    calls = []
    gateway = ExecutionGateway(
        {"write_file": lambda payload: calls.append(payload) or "saved"}
    )

    denied = gateway.execute(
        "write_file",
        {"path": "a.txt"},
        auto_run=True,
        auto_run_actions={"delete_file"},
    )
    allowed = gateway.execute(
        "write_file",
        {"path": "a.txt"},
        auto_run=True,
        auto_run_actions={"write_file"},
    )

    assert denied.executed is False
    assert allowed.executed is True
    assert calls == [{"path": "a.txt"}]


def test_blocked_action_cannot_be_enabled_by_auto_run():
    gateway = ExecutionGateway()
    result = gateway.execute(
        "place_order",
        auto_run=True,
        auto_run_actions={"place_order"},
    )
    assert result.executed is False


def test_non_mapping_payload_is_rejected_without_dispatch():
    calls = []
    gateway = ExecutionGateway(
        {"write_file": lambda payload: calls.append(payload)},
        approval_authority=ApprovalAuthority(),
    )

    result = gateway.execute("write_file", ["not", "a", "mapping"])

    assert result.executed is False
    assert calls == []


def test_gateway_audits_denied_attempt_without_recording_payload():
    gateway = ExecutionGateway()
    secret_payload = {"token": "do-not-log-this"}
    result = gateway.execute("unknown_action", secret_payload)

    assert result.executed is False
    assert len(gateway.audit_events) == 1
    event = gateway.audit_events[0]
    assert event.action == "unknown_action"
    assert event.executed is False
    assert "do-not-log-this" not in repr(event)


def test_gateway_audits_successful_execution_without_recording_payload():
    authority = ApprovalAuthority()
    payload = {"path": "private.txt", "content": "secret"}
    gateway = ExecutionGateway(
        {"write_file": lambda data: "saved"},
        approval_authority=authority,
    )
    receipt = authority.issue("write_file", payload)

    result = gateway.execute("write_file", payload, approval_receipt=receipt)

    assert result.executed is True
    assert len(gateway.audit_events) == 1
    event = gateway.audit_events[0]
    assert event.action == "write_file"
    assert event.executed is True
    assert "secret" not in repr(event)


def test_gateway_audit_snapshot_cannot_be_mutated():
    gateway = ExecutionGateway()
    gateway.execute("unknown_action")

    events = gateway.audit_events
    assert isinstance(events, tuple)
    assert len(events) == 1
