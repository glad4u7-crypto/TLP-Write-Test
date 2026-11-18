import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from core.oci_worker_lifecycle import (
    CommandResult, OCIWorkerLifecycle, WorkerLifecycleError, WorkerState,
)
from test_attested_browser_runtime import (
    CHALLENGE, NOW, PROXY_IP, make_spec, signed_evidence,
)
from test_oci_worker_plan import plan


class FakeRunner:
    def __init__(self, fail_on=None):
        self.calls = []
        self.fail_on = fail_on

    def __call__(self, argv, *, timeout_seconds):
        self.calls.append(tuple(argv))
        if argv[1] == self.fail_on:
            raise RuntimeError("simulated runner failure")
        return CommandResult(0, stdout="normalized-inspect-output")


def make_lifecycle(runner, envelope, key):
    spec = make_spec()
    return OCIWorkerLifecycle(
        plan(), spec,
        command_runner=runner,
        evidence_provider=lambda _plan, _inspect: envelope,
        trusted_public_keys={"host-inspector-prod": key.public_key().public_bytes_raw()},
        expected_proxy_addresses=[PROXY_IP],
    )


def test_successful_create_inspect_attest_start_and_cleanup_order():
    spec = make_spec()
    key = Ed25519PrivateKey.generate()
    envelope = signed_evidence(spec, key)
    runner = FakeRunner()
    lifecycle = make_lifecycle(runner, envelope, key)

    result = lifecycle.launch(challenge=CHALLENGE, now=NOW)

    assert result.returncode == 0
    assert lifecycle.state is WorkerState.RUNNING
    assert [call[1] for call in runner.calls] == ["create", "inspect", "start"]

    lifecycle.cleanup()
    assert lifecycle.state is WorkerState.REMOVED
    assert [call[1] for call in runner.calls] == ["create", "inspect", "start", "stop", "rm"]
    lifecycle.cleanup()
    assert len(runner.calls) == 5


def test_invalid_or_tampered_evidence_never_starts_and_removes_created_worker():
    spec = make_spec()
    key = Ed25519PrivateKey.generate()
    envelope = signed_evidence(spec, key)
    envelope["payload"]["firewall"]["default_egress_policy"] = "accept"
    runner = FakeRunner()
    lifecycle = make_lifecycle(runner, envelope, key)

    with pytest.raises(WorkerLifecycleError, match="attestation rejected"):
        lifecycle.launch(challenge=CHALLENGE, now=NOW)

    assert "start" not in [call[1] for call in runner.calls]
    assert runner.calls[-1][1] == "rm"
    assert lifecycle.state is WorkerState.REMOVED


def test_create_failure_attempts_remove_without_inspect_or_start():
    key = Ed25519PrivateKey.generate()
    runner = FakeRunner(fail_on="create")
    lifecycle = make_lifecycle(runner, {}, key)

    with pytest.raises(WorkerLifecycleError):
        lifecycle.launch(challenge=CHALLENGE, now=NOW)

    assert [call[1] for call in runner.calls] == ["create", "rm"]
    assert lifecycle.state is WorkerState.REMOVED


def test_start_failure_attempts_stop_then_remove():
    spec = make_spec()
    key = Ed25519PrivateKey.generate()
    runner = FakeRunner(fail_on="start")
    lifecycle = make_lifecycle(runner, signed_evidence(spec, key), key)

    with pytest.raises(WorkerLifecycleError):
        lifecycle.launch(challenge=CHALLENGE, now=NOW)

    assert [call[1] for call in runner.calls] == [
        "create", "inspect", "start", "stop", "rm",
    ]
    assert lifecycle.state is WorkerState.REMOVED


def test_launch_is_one_shot_and_abort_cleans_up_running_worker():
    spec = make_spec()
    key = Ed25519PrivateKey.generate()
    runner = FakeRunner()
    lifecycle = make_lifecycle(runner, signed_evidence(spec, key), key)
    lifecycle.launch(challenge=CHALLENGE, now=NOW)

    with pytest.raises(WorkerLifecycleError, match="not repeatable"):
        lifecycle.launch(challenge=CHALLENGE, now=NOW)

    lifecycle.abort()
    assert lifecycle.state is WorkerState.REMOVED
    assert [call[1] for call in runner.calls] == [
        "create", "inspect", "start", "stop", "rm",
    ]


def test_runner_receives_only_argv_and_lifecycle_rejects_string_results():
    spec = make_spec()
    key = Ed25519PrivateKey.generate()
    seen = []

    def invalid_runner(argv, *, timeout_seconds):
        seen.append(argv)
        return "shell command result"

    lifecycle = make_lifecycle(invalid_runner, signed_evidence(spec, key), key)
    with pytest.raises(WorkerLifecycleError):
        lifecycle.launch(challenge=CHALLENGE, now=NOW)
    assert all(isinstance(argv, tuple) for argv in seen)
    assert seen[0][1] == "create"
