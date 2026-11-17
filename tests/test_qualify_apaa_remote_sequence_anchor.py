import threading

import pytest

from core.remote_owner_anchor import RemoteAnchorError
from scripts import qualify_apaa_remote_sequence_anchor as cli


class SharedSequenceAnchor:
    def __init__(self):
        self.value = 0
        self.lock = threading.Lock()

    def read_sequence(self, issuer_key_id):
        with self.lock:
            return self.value

    def advance_sequence(self, issuer_key_id, *, expected_current, new_sequence):
        with self.lock:
            if self.value != expected_current or new_sequence != expected_current + 1:
                return False
            self.value = new_sequence
            return True


def test_sequence_anchor_conformance_has_one_cas_winner_and_rejects_stale_write():
    shared = SharedSequenceAnchor()
    result = cli.run_sequence_conformance(
        client_factory=lambda: shared,
        test_issuer_id="apaa-test-root-001",
    )
    assert result["status"] == "REMOTE_SEQUENCE_ANCHOR_CAS_CONFORMANCE_PASS"
    assert result["successful_writers"] == 1
    assert result["stale_write"] == "REJECTED"
    assert result["provider_backup_restore_anti_rollback"] == "NOT_ASSESSED"
    assert shared.value == 1


def test_sequence_conformance_refuses_non_test_or_nonzero_issuer():
    shared = SharedSequenceAnchor()
    with pytest.raises(RemoteAnchorError, match="dedicated"):
        cli.run_sequence_conformance(
            client_factory=lambda: shared, test_issuer_id="control:root-001",
        )
    shared.value = 5
    with pytest.raises(RemoteAnchorError, match="sequence zero"):
        cli.run_sequence_conformance(
            client_factory=lambda: shared, test_issuer_id="apaa-test-root-002",
        )


def test_sequence_cli_requires_explicit_confirmation_and_test_issuer(capsys):
    args = [
        "--endpoint", "https://anchor.example.test",
        "--ca-file", "/tmp/ca.pem",
        "--client-cert", "/tmp/client.pem",
        "--client-key", "/tmp/client.key",
        "--test-issuer-id", "control:root-001",
    ]
    assert cli.main(args) == 2
    assert "Refusing remote writes" in capsys.readouterr().err
    assert cli.main(args + ["--confirm-write-tests"]) == 2
    assert "must start with apaa-test-" in capsys.readouterr().err
