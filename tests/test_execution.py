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


def test_auto_run_requires_trusted_gateway_allowlist_and_registered_handler():
    calls = []
    gateway = ExecutionGateway(
        {"write_file": lambda payload: calls.append(payload) or "saved"}
    )

    denied = gateway.execute(
        "write_file",
        {"path": "a.txt"},
        auto_run=True,
    )
    assert denied.executed is False

    trusted_configured_gateway = ExecutionGateway(
        {"write_file": lambda payload: calls.append(payload) or "saved"},
        auto_run_actions={"write_file"},
    )
    allowed = trusted_configured_gateway.execute(
        "write_file",
        {"path": "a.txt"},
        auto_run=True,
    )

    assert allowed.executed is True
    assert calls == [{"path": "a.txt"}]


def test_blocked_action_cannot_be_enabled_by_auto_run():
    gateway = ExecutionGateway(auto_run_actions={"place_order"})
    result = gateway.execute("place_order", auto_run=True)
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
    assert len(gateway.audit_events) == 2
    intent, event = gateway.audit_events
    assert intent.executed is False
    assert intent.reason == "authorized_dispatch_pending"
    assert event.action == "write_file"
    assert event.executed is True
    assert "secret" not in repr(intent)
    assert "secret" not in repr(event)


def test_gateway_audit_snapshot_cannot_be_mutated():
    gateway = ExecutionGateway()
    gateway.execute("unknown_action")

    events = gateway.audit_events
    assert isinstance(events, tuple)
    assert len(events) == 1


def test_execution_result_returns_payload_free_audit_event():
    authority = ApprovalAuthority()
    payload = {"content": "sensitive-user-content"}
    gateway = ExecutionGateway(
        {"write_file": lambda data: "ok"},
        approval_authority=authority,
    )
    receipt = authority.issue("write_file", payload)

    result = gateway.execute("write_file", payload, approval_receipt=receipt)

    assert result.executed is True
    assert result.audit_event is not None
    assert result.audit_event.executed is True
    assert "sensitive-user-content" not in repr(result.audit_event)


def test_task_cannot_supply_its_own_auto_run_allowlist():
    calls = []
    gateway = ExecutionGateway(
        {"write_file": lambda payload: calls.append(payload)}
    )
    # execute() accepts only the auto_run request; the allowlist is fixed at
    # gateway construction by trusted application configuration.
    with pytest.raises(TypeError):
        gateway.execute(
            "write_file",
            {"path": "unapproved.txt"},
            auto_run=True,
            auto_run_actions={"write_file"},
        )
    assert calls == []


def test_gateway_persists_intent_and_completion_audit(tmp_path):
    from core.audit import JsonlAuditLog

    authority = ApprovalAuthority()
    payload = {"path": "approved.txt"}
    calls = []
    log = JsonlAuditLog(tmp_path / "gateway.jsonl")
    gateway = ExecutionGateway(
        {"write_file": lambda data: calls.append(data) or "saved"},
        approval_authority=authority,
        audit_log=log,
    )
    receipt = authority.issue("write_file", payload)

    result = gateway.execute("write_file", payload, approval_receipt=receipt)

    assert result.executed is True
    assert calls == [payload]
    assert log.verify() != log.GENESIS
    assert len((tmp_path / "gateway.jsonl").read_text().splitlines()) == 2
    assert "approved.txt" not in (tmp_path / "gateway.jsonl").read_text()


def test_gateway_fails_closed_when_intent_audit_cannot_be_written(tmp_path, monkeypatch):
    from core.audit import JsonlAuditLog

    authority = ApprovalAuthority()
    calls = []
    log = JsonlAuditLog(tmp_path / "gateway.jsonl")

    def fail_append(event):
        raise OSError("disk unavailable")

    monkeypatch.setattr(log, "append", fail_append)
    gateway = ExecutionGateway(
        {"write_file": lambda data: calls.append(data)},
        approval_authority=authority,
        audit_log=log,
    )
    payload = {"path": "must-not-write.txt"}
    receipt = authority.issue("write_file", payload)

    result = gateway.execute("write_file", payload, approval_receipt=receipt)

    assert result.executed is False
    assert "not executed" in result.reason
    assert calls == []


def test_gateway_reports_completion_audit_failure_after_side_effect(tmp_path, monkeypatch):
    from core.audit import JsonlAuditLog

    authority = ApprovalAuthority()
    calls = []
    log = JsonlAuditLog(tmp_path / "gateway.jsonl")
    original_append = log.append
    count = {"value": 0}

    def fail_second_append(event):
        count["value"] += 1
        if count["value"] == 2:
            raise OSError("disk became unavailable")
        return original_append(event)

    monkeypatch.setattr(log, "append", fail_second_append)
    gateway = ExecutionGateway(
        {"write_file": lambda data: calls.append(data) or "saved"},
        approval_authority=authority,
        audit_log=log,
    )
    payload = {"path": "already-written.txt"}
    receipt = authority.issue("write_file", payload)

    result = gateway.execute("write_file", payload, approval_receipt=receipt)

    assert result.executed is True
    assert "completion audit persistence failed" in result.reason
    assert calls == [payload]
    assert len((tmp_path / "gateway.jsonl").read_text().splitlines()) == 1


def test_gateway_fails_closed_on_unexpected_intent_audit_backend_error(tmp_path, monkeypatch):
    from core.audit import JsonlAuditLog

    authority = ApprovalAuthority()
    calls = []
    log = JsonlAuditLog(tmp_path / "gateway.jsonl")

    def fail_append(event):
        raise RuntimeError("audit backend unavailable")

    monkeypatch.setattr(log, "append", fail_append)
    gateway = ExecutionGateway(
        {"write_file": lambda data: calls.append(data)},
        approval_authority=authority,
        audit_log=log,
    )
    payload = {"path": "must-not-run.txt"}
    receipt = authority.issue("write_file", payload)

    result = gateway.execute("write_file", payload, approval_receipt=receipt)

    assert result.executed is False
    assert "not executed" in result.reason
    assert calls == []
