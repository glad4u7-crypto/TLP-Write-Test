import ssl
import time
import threading

import pytest

from core.browser_execution import (
    BrowserCancelled,
    BrowserExecutionCoordinator,
    BrowserExecutionError,
    BrowserTimeout,
    CancellationToken,
    PinnedDestination,
    PinnedHTTPSConnection,
)


def valid_job(**overrides):
    raw = {
        "job_id": "job_p74_123456",
        "url": "https://example.com/docs",
        "allowed_origins": ["https://example.com"],
        "action": "read_visible_text",
        "expires_at": int(time.time()) + 120,
        "max_response_bytes": 100_000,
        "max_runtime_seconds": 10,
    }
    raw.update(overrides)
    return raw


class FakeWorker:
    def __init__(self, result=None):
        self.result = result or {"text": "safe"}
        self.calls = []
        self.terminated = []

    def run(self, job, *, session_id, cancellation, deadline_monotonic, pinned_destination):
        self.calls.append((job, session_id, pinned_destination))
        cancellation.raise_if_cancelled()
        assert pinned_destination.addresses == ("93.184.216.34",)
        return self.result

    def terminate(self, session_id):
        self.terminated.append(session_id)
        return True


def test_cancellation_token_is_idempotent_and_observable():
    token = CancellationToken()
    assert token.cancel() is True
    assert token.cancel() is False
    assert token.cancelled is True
    with pytest.raises(BrowserCancelled):
        token.raise_if_cancelled()


@pytest.mark.parametrize("address", [
    "127.0.0.1", "169.254.169.254", "100.64.0.1",
    "192.0.2.1", "::ffff:127.0.0.1", "ff02::1",
])
def test_pinned_destination_rejects_non_public_and_special_use_ips(address):
    with pytest.raises(ValueError):
        PinnedDestination("example.com", 443, (address,))


def test_pinned_destination_rejects_duplicate_ips():
    with pytest.raises(ValueError):
        PinnedDestination("example.com", 443, ("93.184.216.34", "93.184.216.34"))


def test_tls_context_must_verify_certificates_and_hostname():
    destination = PinnedDestination("example.com", 443, ("93.184.216.34",))
    insecure = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    insecure.check_hostname = False
    insecure.verify_mode = ssl.CERT_NONE
    with pytest.raises(ValueError, match="mandatory"):
        PinnedHTTPSConnection(destination, context=insecure)


def test_tls_transport_uses_logical_hostname_and_pinned_ip():
    destination = PinnedDestination("example.com", 443, ("93.184.216.34",))
    connection = PinnedHTTPSConnection(destination)
    assert connection.host == "example.com"
    assert connection.port == 443
    assert connection.destination.addresses == ("93.184.216.34",)
    assert connection._context.verify_mode == ssl.CERT_REQUIRED
    assert connection._context.check_hostname is True
    connection.close()


def test_execution_fails_closed_without_attested_worker():
    coordinator = BrowserExecutionCoordinator(None, audit=lambda event: None)
    with pytest.raises(BrowserExecutionError, match="disabled"):
        coordinator.execute(valid_job(), resolver=lambda host: ["93.184.216.34"])


def test_execution_requires_live_dns_and_passes_pins_to_worker():
    worker = FakeWorker()
    events = []
    coordinator = BrowserExecutionCoordinator(worker, audit=events.append)
    result = coordinator.execute(
        valid_job(),
        resolver=lambda host: ["93.184.216.34", "93.184.216.34"],
    )
    assert result == {"text": "safe"}
    assert worker.calls[0][2].addresses == ("93.184.216.34",)
    assert [event["event"] for event in events] == [
        "job_accepted", "job_completed", "session_closed"
    ]


def test_private_dns_answer_blocks_before_worker_launch():
    worker = FakeWorker()
    coordinator = BrowserExecutionCoordinator(worker, audit=lambda event: None)
    with pytest.raises(BrowserExecutionError, match="DNS/IP pin"):
        coordinator.execute(
            valid_job(),
            resolver=lambda host: ["93.184.216.34", "169.254.169.254"],
        )
    assert worker.calls == []


def test_dns_failure_blocks_before_worker_launch():
    worker = FakeWorker()
    coordinator = BrowserExecutionCoordinator(worker, audit=lambda event: None)

    def broken(host):
        raise OSError("DNS unavailable")

    with pytest.raises(BrowserExecutionError, match="DNS/IP pin"):
        coordinator.execute(valid_job(), resolver=broken)
    assert worker.calls == []


def test_audit_acceptance_failure_blocks_execution():
    worker = FakeWorker()

    def broken_audit(event):
        raise OSError("audit store unavailable")

    coordinator = BrowserExecutionCoordinator(worker, audit=broken_audit)
    with pytest.raises(BrowserExecutionError, match="Final browser audit"):
        coordinator.execute(valid_job(), resolver=lambda host: ["93.184.216.34"])
    assert worker.calls == []


def test_invalid_or_expired_job_never_reaches_worker():
    worker = FakeWorker()
    coordinator = BrowserExecutionCoordinator(worker, audit=lambda event: None)
    with pytest.raises(BrowserExecutionError):
        coordinator.execute(
            valid_job(expires_at=int(time.time()) - 1),
            resolver=lambda host: ["93.184.216.34"],
        )
    assert worker.calls == []


def test_worker_failure_is_audited_and_session_closed():
    class FailingWorker(FakeWorker):
        def run(self, *args, **kwargs):
            raise RuntimeError("worker crash")

    events = []
    coordinator = BrowserExecutionCoordinator(FailingWorker(), audit=events.append)
    with pytest.raises(RuntimeError, match="worker crash"):
        coordinator.execute(valid_job(), resolver=lambda host: ["93.184.216.34"])
    assert [event["event"] for event in events] == [
        "job_accepted", "job_failed", "session_closed"
    ]


def test_audit_records_do_not_include_url_or_page_content():
    events = []
    coordinator = BrowserExecutionCoordinator(FakeWorker(), audit=events.append)
    coordinator.execute(
        valid_job(url="https://example.com/private?token=do-not-log"),
        resolver=lambda host: ["93.184.216.34"],
    )
    rendered = repr(events)
    assert "do-not-log" not in rendered
    assert "private" not in rendered
    assert "safe" not in rendered


def test_worker_result_must_be_mapping():
    class BadWorker(FakeWorker):
        def run(self, *args, **kwargs):
            return "not-an-envelope"

    events = []
    coordinator = BrowserExecutionCoordinator(BadWorker(), audit=events.append)
    with pytest.raises(BrowserExecutionError, match="invalid result"):
        coordinator.execute(valid_job(), resolver=lambda host: ["93.184.216.34"])
    assert events[-1]["event"] == "session_closed"



def test_cancel_terminates_the_unique_worker_session():
    started = threading.Event()
    release = threading.Event()
    terminated = []

    class BlockingWorker(FakeWorker):
        def run(self, job, *, session_id, cancellation, deadline_monotonic, pinned_destination):
            started.set()
            release.wait(timeout=3)
            cancellation.raise_if_cancelled()
            return {"text": "unexpected"}

        def terminate(self, session_id):
            terminated.append(session_id)
            release.set()
            return True
            return True

    events = []
    coordinator = BrowserExecutionCoordinator(BlockingWorker(), audit=events.append)
    errors = []

    def execute():
        try:
            coordinator.execute(valid_job(), resolver=lambda host: ["93.184.216.34"])
        except Exception as exc:
            errors.append(exc)

    thread = threading.Thread(target=execute)
    thread.start()
    assert started.wait(timeout=2)
    assert coordinator.cancel("job_p74_123456") is True
    assert coordinator.cancel("job_p74_123456") is False
    thread.join(timeout=3)
    assert not thread.is_alive()
    assert len(terminated) == 1
    assert terminated[0] != "job_p74_123456"
    assert len(errors) == 1
    assert isinstance(errors[0], BrowserCancelled)
    assert [event["event"] for event in events] == [
        "job_accepted", "cancel_requested", "job_cancelled", "session_closed"
    ]



def test_hard_deadline_terminates_worker_and_audits_timeout():
    started = threading.Event()
    release = threading.Event()
    terminated = []

    class SlowWorker(FakeWorker):
        def run(self, job, *, session_id, cancellation, deadline_monotonic, pinned_destination):
            started.set()
            release.wait(timeout=4)
            cancellation.raise_if_cancelled()
            return {"text": "too late"}

        def terminate(self, session_id):
            terminated.append(session_id)
            release.set()
            return True

    events = []
    coordinator = BrowserExecutionCoordinator(SlowWorker(), audit=events.append)
    with pytest.raises(BrowserTimeout, match="hard runtime deadline"):
        coordinator.execute(
            valid_job(max_runtime_seconds=1),
            resolver=lambda host: ["93.184.216.34"],
        )
    assert started.is_set()
    assert len(terminated) == 1
    assert [event["event"] for event in events] == [
        "job_accepted", "job_timed_out", "session_closed"
    ]



def test_attested_runtime_factory_rejects_duck_typed_bypass():
    calls = []

    class FakeGate:
        def launch(self, evidence, *, challenge, now):
            calls.append(True)
            return FakeWorker()

    with pytest.raises(TypeError, match="concrete AttestedBrowserRuntime"):
        BrowserExecutionCoordinator.from_attested_runtime(
            FakeGate(), {"signed": "evidence"}, challenge="a" * 64, now=1234,
            audit=lambda event: None,
        )
    assert calls == []




def test_cancel_terminates_worker_even_if_audit_storage_fails():
    started = threading.Event()
    release = threading.Event()
    terminated = []

    class BlockingWorker(FakeWorker):
        def run(self, job, *, session_id, cancellation, deadline_monotonic, pinned_destination):
            started.set()
            release.wait(timeout=3)
            cancellation.raise_if_cancelled()
            return {"text": "unexpected"}

        def terminate(self, session_id):
            terminated.append(session_id)
            release.set()
            return True

    events = []

    def broken_audit(event):
        if event["event"] == "cancel_requested":
            raise OSError("audit unavailable")
        events.append(event)

    coordinator = BrowserExecutionCoordinator(BlockingWorker(), audit=broken_audit)
    errors = []

    def execute():
        try:
            coordinator.execute(valid_job(), resolver=lambda host: ["93.184.216.34"])
        except Exception as exc:
            errors.append(exc)

    thread = threading.Thread(target=execute)
    thread.start()
    assert started.wait(timeout=2)
    with pytest.raises(BrowserExecutionError, match="audit write failed"):
        coordinator.cancel("job_p74_123456")
    thread.join(timeout=3)
    assert not thread.is_alive()
    assert len(terminated) == 1



def test_timeout_does_not_claim_session_closed_when_termination_unconfirmed():
    class UnconfirmedWorker(FakeWorker):
        def run(self, job, *, session_id, cancellation, deadline_monotonic, pinned_destination):
            threading.Event().wait(timeout=3)
            return {"text": "late"}

        def terminate(self, session_id):
            self.terminated.append(session_id)
            return False

    events = []
    coordinator = BrowserExecutionCoordinator(UnconfirmedWorker(), audit=events.append)
    with pytest.raises(BrowserExecutionError, match="could not be terminated"):
        coordinator.execute(
            valid_job(max_runtime_seconds=1),
            resolver=lambda host: ["93.184.216.34"],
        )
    assert any(event["event"] == "session_cleanup_unconfirmed" for event in events)
    assert not any(event["event"] == "session_closed" for event in events)



def test_cancel_wakes_coordinator_without_waiting_for_worker_callback():
    started = threading.Event()
    release = threading.Event()
    terminated = []

    class StuckWorker(FakeWorker):
        def run(self, job, *, session_id, cancellation, deadline_monotonic, pinned_destination):
            started.set()
            release.wait(timeout=8)
            return {"text": "must-not-be-returned"}

        def terminate(self, session_id):
            terminated.append(session_id)
            release.set()
            return True

    events = []
    coordinator = BrowserExecutionCoordinator(StuckWorker(), audit=events.append)
    errors = []

    def execute():
        try:
            coordinator.execute(valid_job(max_runtime_seconds=20), resolver=lambda host: ["93.184.216.34"])
        except Exception as exc:
            errors.append(exc)

    thread = threading.Thread(target=execute)
    thread.start()
    assert started.wait(timeout=2)
    assert coordinator.cancel("job_p74_123456") is True
    thread.join(timeout=1)
    release.set()
    assert not thread.is_alive()
    assert len(terminated) == 1
    assert len(errors) == 1
    assert isinstance(errors[0], BrowserCancelled)
    assert events[-1]["event"] == "session_closed"



@pytest.mark.parametrize("result", [
    {"text": "x" * 1000},
    {"text": object()},
    {1: "non-string-key"},
    {"nested": {1: "non-string-nested-key"}},
    {"number": float("nan")},
])
def test_worker_result_must_be_json_safe_and_within_response_limit(result):
    class ResultWorker(FakeWorker):
        def run(self, *args, **kwargs):
            return result

    events = []
    coordinator = BrowserExecutionCoordinator(ResultWorker(), audit=events.append)
    with pytest.raises(BrowserExecutionError):
        coordinator.execute(
            valid_job(max_response_bytes=128),
            resolver=lambda host: ["93.184.216.34"],
        )
    assert events[-1]["event"] == "session_closed"



def test_tls_transport_rejects_legacy_tls_minimum_version():
    destination = PinnedDestination("example.com", 443, ("93.184.216.34",))
    legacy = ssl.create_default_context()
    legacy.minimum_version = ssl.TLSVersion.TLSv1_1
    with pytest.raises(ValueError, match="TLS 1.2"):
        PinnedHTTPSConnection(destination, context=legacy)
