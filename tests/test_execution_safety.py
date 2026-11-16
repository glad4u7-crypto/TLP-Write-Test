import pytest
from core.approvals import ApprovalAuthority
from core.execution_safety import ExecutionSafetyBoundary, validate_pre_execution

class Audit:
    def __init__(self, fail_at=None): self.events, self.fail_at = [], fail_at
    def append(self, event):
        if self.fail_at == len(self.events): raise OSError("audit unavailable")
        self.events.append(event)

def test_preflight_rejects_invalid_shape_and_payload():
    assert not validate_pre_execution("", {}).valid
    assert not validate_pre_execution("inspect", []).valid
    assert not validate_pre_execution("inspect", {"x": float("nan")}).valid
    assert not validate_pre_execution("inspect", {"x": "a" * 100}, max_payload_bytes=10).valid

@pytest.mark.parametrize("action", ["payment", "buy_item", "checkout", "transfer_money", "trade_stock", "paid_api_call", "external_api_request", "unknown_action", "run_shell"])
def test_preflight_blocks_prohibited_and_unknown_actions(action):
    assert not validate_pre_execution(action, {}).valid

def test_read_only_action_audits_intent_and_completion():
    audit = Audit()
    boundary = ExecutionSafetyBoundary(approval_authority=ApprovalAuthority(), audit_log=audit, handlers={"inspect": lambda p: {"count": p["count"]}})
    result = boundary.execute("inspect", {"count": 2})
    assert result.executed and result.value == {"count": 2}
    assert [e.reason for e in audit.events] == ["execution_intent", "execution_completed"]

def test_mutation_requires_exact_payload_bound_single_use_receipt():
    authority, audit = ApprovalAuthority(signing_secret=b"x" * 32), Audit()
    boundary = ExecutionSafetyBoundary(approval_authority=authority, audit_log=audit, handlers={"write_file": lambda p: "written"})
    payload = {"path": "notes.txt", "content": "hello"}
    assert not boundary.execute("write_file", payload).executed
    receipt = authority.issue("write_file", payload)
    assert not boundary.execute("write_file", {"path": "other.txt"}, receipt=receipt).executed
    receipt = authority.issue("write_file", payload)
    assert boundary.execute("write_file", payload, receipt=receipt).executed
    assert not boundary.execute("write_file", payload, receipt=receipt).executed

def test_audit_intent_failure_blocks_handler():
    calls, audit = [], Audit(fail_at=0)
    boundary = ExecutionSafetyBoundary(approval_authority=ApprovalAuthority(), audit_log=audit, handlers={"inspect": lambda p: calls.append(p)})
    assert not boundary.execute("inspect", {}).executed and calls == []

def test_handler_failure_is_audited():
    audit = Audit()
    boundary = ExecutionSafetyBoundary(approval_authority=ApprovalAuthority(), audit_log=audit, handlers={"inspect": lambda p: (_ for _ in ()).throw(RuntimeError())})
    assert not boundary.execute("inspect", {}).executed
    assert audit.events[-1].reason == "handler_failed"

def test_completion_audit_failure_requires_manual_review():
    audit = Audit(fail_at=1)
    boundary = ExecutionSafetyBoundary(approval_authority=ApprovalAuthority(), audit_log=audit, handlers={"inspect": lambda p: "done"})
    result = boundary.execute("inspect", {})
    assert not result.executed and result.manual_review_required

def test_missing_handler_is_not_success():
    boundary = ExecutionSafetyBoundary(approval_authority=ApprovalAuthority(), audit_log=Audit(), handlers={})
    result = boundary.execute("inspect", {})
    assert not result.executed and "No reviewed handler" in result.reason