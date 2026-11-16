import threading

from core.offline_owner_recovery import AnchorState
from core.remote_owner_anchor import RemoteAnchorError
from scripts import qualify_apaa_remote_anchor as cli


class SharedAnchor:
    def __init__(self):
        self.state = AnchorState(0, None, None)
        self.lock = threading.Lock()

    def read(self):
        with self.lock:
            return self.state

    def compare_and_advance(self, *, expected, target):
        with self.lock:
            if self.state != expected or target.revision != expected.revision + 1:
                return False
            self.state = target
            return True


def test_remote_anchor_conformance_has_one_cas_winner_and_rejects_stale_write():
    shared = SharedAnchor()
    result = cli.run_conformance(
        client_factory=lambda: shared, test_anchor_id="apaa-test-owner-001",
    )
    assert result["status"] == "REMOTE_ANCHOR_ATOMIC_CAS_CONFORMANCE_PASS"
    assert result["successful_writers"] == 1
    assert result["stale_write"] == "REJECTED"
    assert result["provider_backup_restore_anti_rollback"] == "NOT_ASSESSED"
    assert shared.state.revision == 1


def test_remote_anchor_conformance_refuses_non_test_anchor_and_nonzero_state():
    import pytest
    shared = SharedAnchor()
    with pytest.raises(RemoteAnchorError, match="dedicated"):
        cli.run_conformance(client_factory=lambda: shared, test_anchor_id="owner:primary")
    shared.state = AnchorState(2, "a" * 64, "existing-002")
    with pytest.raises(RemoteAnchorError, match="revision zero"):
        cli.run_conformance(client_factory=lambda: shared, test_anchor_id="apaa-test-owner-002")


def test_cli_requires_confirmation_and_rejects_production_anchor_id(capsys):
    args = [
        "--endpoint", "https://anchor.example.test", "--ca-file", "/tmp/ca.pem",
        "--client-cert", "/tmp/client.pem", "--client-key", "/tmp/client.key",
        "--test-anchor-id", "owner:primary",
    ]
    assert cli.main(args) == 2
    assert "Refusing remote writes" in capsys.readouterr().err
    assert cli.main(args + ["--confirm-write-tests"]) == 2
    assert "must start with apaa-test-" in capsys.readouterr().err
