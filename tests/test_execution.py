import pytest

from core.execution import ExecutionGateway


def test_gateway_has_no_handlers_by_default():
    result = ExecutionGateway().execute("read")
    assert result.executed is False
    assert "No trusted handler" in result.reason


def test_mutation_is_not_dispatched_without_exact_approval():
    calls = []
    gateway = ExecutionGateway({"write_file": lambda payload: calls.append(payload)})

    result = gateway.execute("write_file", {"path": "notes.txt"})

    assert result.executed is False
    assert calls == []


def test_mutation_dispatches_only_after_exact_approval():
    calls = []
    gateway = ExecutionGateway({"write_file": lambda payload: calls.append(payload) or "ok"})

    result = gateway.execute(
        "write_file",
        {"path": "notes.txt"},
        approved_action="write_file",
    )

    assert result.executed is True
    assert result.output == "ok"
    assert calls == [{"path": "notes.txt"}]


def test_mismatched_approval_never_calls_handler():
    calls = []
    gateway = ExecutionGateway({"delete_file": lambda payload: calls.append(payload)})

    result = gateway.execute(
        "delete_file",
        {"path": "important.txt"},
        approved_action="write_file",
    )

    assert result.executed is False
    assert calls == []


@pytest.mark.parametrize("action", ["run_shell", "execute_code", "external_api_request", "place_order"])
def test_prohibited_or_unknown_actions_cannot_be_registered_or_dispatched(action):
    with pytest.raises(ValueError):
        ExecutionGateway({action: lambda payload: "should never run"})


def test_auto_run_requires_exact_allowlist_and_registered_handler():
    calls = []
    gateway = ExecutionGateway({"write_file": lambda payload: calls.append(payload) or "saved"})

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
    gateway = ExecutionGateway({"write_file": lambda payload: calls.append(payload)})

    result = gateway.execute(
        "write_file",
        ["not", "a", "mapping"],
        approved_action="write_file",
    )

    assert result.executed is False
    assert calls == []
