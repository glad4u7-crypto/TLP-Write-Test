import ssl
import time
import threading
import tempfile
from dataclasses import asdict
from pathlib import Path

import pytest

from core.approvals import ApprovalAuthority
from core.identity import Principal
from core.storage import TenantKey
from core.browser_security import validate_browser_job
from core.browser_recovery import SQLiteBrowserRecoveryLedger
from core.sqlite_security_store import SQLiteSecurityStore

from core.browser_execution import (
    BrowserCancelled,
    BrowserExecutionCoordinator,
    BrowserExecutionError,
    BrowserTimeout,
    CancellationToken,
    PinnedDestination,
    PinnedHTTPSConnection,
    authorize_redirect_and_pin,
)



_ProductionBrowserExecutionCoordinator = BrowserExecutionCoordinator


class BrowserExecutionCoordinator(_ProductionBrowserExecutionCoordinator):
    """Test harness that models trusted Owner UI approval for each ordinary test call."""

    def __init__(self, worker, *, audit, clock=time.monotonic, recovery_ledger=None):
        self._test_tempdir = tempfile.TemporaryDirectory()
        private_dir = Path(self._test_tempdir.name)
        private_dir.chmod(0o700)
        ledger = recovery_ledger or SQLiteBrowserRecoveryLedger(private_dir / "browser.sqlite3")
        self._test_tenant = TenantKey("https://apaa.test", "owner-1")
        self._test_principal = Principal(
            subject="owner-1", issuer="https://apaa.test",
            authenticated=True, roles=("owner",),
        )
        self._test_session = "owner-session-test-001"
        self._test_authority = ApprovalAuthority(
            nonce_store=SQLiteSecurityStore(private_dir / "security.sqlite3"),
            signing_secret=b"APAA test approval signing secret 32 bytes minimum",
        )
        self._test_owner_active = {"value": True}
        super().__init__(
            worker, audit=audit, clock=clock, recovery_ledger=ledger,
            approval_authority=self._test_authority,
            owner_principal=self._test_principal,
            owner_tenant=self._test_tenant,
            session_scope=self._test_session,
            owner_session_check=lambda: self._test_owner_active["value"],
        )

    def _issue_test_receipt(self, raw_job):
        job = validate_browser_job(raw_job)
        payload = asdict(job)
        payload["allowed_origins"] = list(job.allowed_origins)
        ttl = min(60, job.expires_at - int(time.time()))
        return self._test_authority.issue(
            "browser_read", payload, ttl_seconds=ttl,
            tenant=self._test_tenant, session_scope=self._test_session,
        )

    def execute(self, raw_job, *, resolver, approval_receipt=None):
        if approval_receipt is None:
            try:
                approval_receipt = self._issue_test_receipt(raw_job)
            except (TypeError, ValueError):
                # Let the production validator return the authoritative error.
                pass
        return super().execute(
            raw_job, resolver=resolver, approval_receipt=approval_receipt,
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
        "job_accepted", "job_failed", "session_cleanup_unconfirmed"
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

    # The stronger fail-closed approval gate runs before runtime type checks.
    # A duck-typed gate must never be invoked while Owner approval binding is absent.
    with pytest.raises(BrowserExecutionError, match="trusted Owner approval"):
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



def test_redirect_authorization_resolves_fresh_pins_for_target_host():
    calls = []

    def resolver(host):
        calls.append(host)
        return ["93.184.216.35"]

    target, pinned = authorize_redirect_and_pin(
        "https://example.com/start", "/next", ["https://example.com"],
        resolver=resolver,
    )
    assert target.url == "https://example.com/next"
    assert calls == ["example.com"]
    assert pinned.hostname == "example.com"
    assert pinned.addresses == ("93.184.216.35",)


def test_redirect_authorization_rejects_private_dns_answers():
    with pytest.raises(BrowserExecutionError, match="DNS/IP pin"):
        authorize_redirect_and_pin(
            "https://example.com/start", "/next", ["https://example.com"],
            resolver=lambda host: ["169.254.169.254"],
        )


def test_redirect_authorization_rejects_unapproved_origin_before_dns():
    calls = []
    with pytest.raises(BrowserExecutionError, match="URL/origin policy"):
        authorize_redirect_and_pin(
            "https://example.com/start", "https://evil.example/steal",
            ["https://example.com"], resolver=lambda host: calls.append(host) or ["93.184.216.34"],
        )
    assert calls == []


def test_redirect_authorization_requires_live_resolver():
    with pytest.raises(BrowserExecutionError, match="live DNS resolver"):
        authorize_redirect_and_pin(
            "https://example.com/start", "/next", ["https://example.com"],
            resolver=None,
        )



def test_redirect_authorization_fails_closed_when_dns_lookup_errors():
    def broken(host):
        raise OSError("DNS unavailable")

    with pytest.raises(BrowserExecutionError, match="DNS resolution failed"):
        authorize_redirect_and_pin(
            "https://example.com/start", "/next", ["https://example.com"],
            resolver=broken,
        )


def test_redirect_authorization_rejects_unapproved_current_origin():
    calls = []
    with pytest.raises(BrowserExecutionError, match="URL/origin policy"):
        authorize_redirect_and_pin(
            "https://evil.example/start", "/next", ["https://example.com"],
            resolver=lambda host: calls.append(host) or ["93.184.216.34"],
        )
    assert calls == []


class _FakeRawSocket:
    def __init__(self, peer):
        self.peer = peer
        self.closed = False

    def getpeername(self):
        return (self.peer, 443)

    def close(self):
        self.closed = True


class _RecordingTLSContext:
    verify_mode = ssl.CERT_REQUIRED
    check_hostname = True
    minimum_version = ssl.TLSVersion.TLSv1_2
    maximum_version = ssl.TLSVersion.MAXIMUM_SUPPORTED

    def __init__(self):
        self.server_names = []

    def wrap_socket(self, raw, *, server_hostname):
        self.server_names.append(server_hostname)
        return object()


def test_pinned_connection_uses_logical_hostname_for_tls_sni(monkeypatch):
    destination = PinnedDestination("example.com", 443, ("93.184.216.34",))
    context = _RecordingTLSContext()
    connection = PinnedHTTPSConnection(destination, context=context)
    raw = _FakeRawSocket("93.184.216.34")
    monkeypatch.setattr(connection, "_create_connection", lambda address, timeout: raw)

    connection.connect()

    assert context.server_names == ["example.com"]
    assert connection.sock is not None


def test_pinned_connection_rejects_socket_peer_outside_pin_set(monkeypatch):
    destination = PinnedDestination("example.com", 443, ("93.184.216.34",))
    context = _RecordingTLSContext()
    connection = PinnedHTTPSConnection(destination, context=context)
    raw = _FakeRawSocket("1.1.1.1")
    monkeypatch.setattr(connection, "_create_connection", lambda address, timeout: raw)

    with pytest.raises(BrowserExecutionError, match="peer differs"):
        connection.connect()

    assert raw.closed is True
    assert context.server_names == []



def test_production_coordinator_fails_closed_without_owner_approval_configuration():
    coordinator = _ProductionBrowserExecutionCoordinator(
        FakeWorker(), audit=lambda event: None,
    )
    with pytest.raises(BrowserExecutionError, match="Owner approval boundary"):
        coordinator.execute(
            valid_job(), resolver=lambda host: ["93.184.216.34"],
        )


def test_owner_approval_is_exact_job_bound_one_time_and_durably_correlated(tmp_path):
    private_dir = tmp_path / "private"
    private_dir.mkdir(mode=0o700)
    private_dir.chmod(0o700)
    tenant = TenantKey("https://apaa.test", "owner-1")
    principal = Principal(
        subject="owner-1", issuer="https://apaa.test",
        authenticated=True, roles=("owner",),
    )
    authority = ApprovalAuthority(
        nonce_store=SQLiteSecurityStore(private_dir / "security.sqlite3"),
        signing_secret=b"APAA durable test approval secret at least 32 bytes",
    )
    ledger = SQLiteBrowserRecoveryLedger(private_dir / "browser.sqlite3")
    worker = FakeWorker()
    session = {"active": True}
    events = []
    coordinator = _ProductionBrowserExecutionCoordinator(
        worker, audit=events.append, recovery_ledger=ledger,
        approval_authority=authority, owner_principal=principal,
        owner_tenant=tenant, session_scope="owner-session-test-001",
        owner_session_check=lambda: session["active"],
    )
    job = valid_job(job_id="job_approval_0001")
    validated = validate_browser_job(job)
    payload = asdict(validated)
    payload["allowed_origins"] = list(validated.allowed_origins)
    receipt = authority.issue(
        "browser_read", payload, ttl_seconds=60,
        tenant=tenant, session_scope="owner-session-test-001",
    )

    assert coordinator.execute(
        job, resolver=lambda host: ["93.184.216.34"],
        approval_receipt=receipt,
    ) == {"text": "safe"}
    correlations = ledger.list_approval_correlations(job["job_id"])
    assert len(correlations) == 1
    assert correlations[0]["request_digest"] == ledger.list_history(job["job_id"])[0].get("request_digest", correlations[0]["request_digest"])
    assert len(correlations[0]["approval_ref"]) == 64
    assert len(correlations[0]["owner_ref"]) == 64
    assert len(correlations[0]["session_ref"]) == 64
    assert ledger.verify_history()

    with pytest.raises(BrowserExecutionError, match="already consumed"):
        coordinator.execute(
            job, resolver=lambda host: ["93.184.216.34"],
            approval_receipt=receipt,
        )
    assert len(worker.calls) == 1


def test_owner_approval_mismatch_is_rejected_before_dns_or_worker():
    authority = ApprovalAuthority(signing_secret=b"APAA test approval signing secret 32 bytes minimum")
    tenant = TenantKey("https://apaa.test", "owner-1")
    principal = Principal("owner-1", "https://apaa.test", True, ("owner",))
    ledger_dir = tempfile.TemporaryDirectory()
    private_dir = Path(ledger_dir.name)
    private_dir.chmod(0o700)
    ledger = SQLiteBrowserRecoveryLedger(private_dir / "browser.sqlite3")
    worker = FakeWorker()
    coordinator = _ProductionBrowserExecutionCoordinator(
        worker, audit=lambda event: None, recovery_ledger=ledger,
        approval_authority=authority, owner_principal=principal,
        owner_tenant=tenant, session_scope="owner-session-test-001",
        owner_session_check=lambda: True,
    )
    job = valid_job(job_id="job_approval_0002")
    receipt = authority.issue(
        "browser_read",
        {"job_id": "different-job"},
        ttl_seconds=60, tenant=tenant, session_scope="owner-session-test-001",
    )
    dns_calls = []
    with pytest.raises(BrowserExecutionError, match="mismatched"):
        coordinator.execute(
            job, resolver=lambda host: dns_calls.append(host) or ["93.184.216.34"],
            approval_receipt=receipt,
        )
    assert dns_calls == []
    assert worker.calls == []
    ledger_dir.cleanup()


def test_owner_session_is_rechecked_before_consuming_approval():
    authority = ApprovalAuthority(signing_secret=b"APAA test approval signing secret 32 bytes minimum")
    tenant = TenantKey("https://apaa.test", "owner-1")
    principal = Principal("owner-1", "https://apaa.test", True, ("owner",))
    ledger_dir = tempfile.TemporaryDirectory()
    private_dir = Path(ledger_dir.name)
    private_dir.chmod(0o700)
    ledger = SQLiteBrowserRecoveryLedger(private_dir / "browser.sqlite3")
    session = {"active": True}
    coordinator = _ProductionBrowserExecutionCoordinator(
        FakeWorker(), audit=lambda event: None, recovery_ledger=ledger,
        approval_authority=authority, owner_principal=principal,
        owner_tenant=tenant, session_scope="owner-session-test-001",
        owner_session_check=lambda: session["active"],
    )
    job = valid_job(job_id="job_approval_0003")
    validated = validate_browser_job(job)
    payload = asdict(validated)
    payload["allowed_origins"] = list(validated.allowed_origins)
    receipt = authority.issue(
        "browser_read", payload, ttl_seconds=60,
        tenant=tenant, session_scope="owner-session-test-001",
    )
    session["active"] = False
    with pytest.raises(BrowserExecutionError, match="inactive or expired"):
        coordinator.execute(
            job, resolver=lambda host: ["93.184.216.34"],
            approval_receipt=receipt,
        )
    session["active"] = True
    # The first denial did not consume the receipt; a newly active session can
    # still use it once while the same signed session scope remains valid.
    assert coordinator.execute(
        job, resolver=lambda host: ["93.184.216.34"],
        approval_receipt=receipt,
    ) == {"text": "safe"}
    ledger_dir.cleanup()


def test_owner_principal_must_match_tenant_before_coordinator_creation(tmp_path):
    private_dir = tmp_path / "private"
    private_dir.mkdir(mode=0o700)
    private_dir.chmod(0o700)
    tenant = TenantKey("https://apaa.test", "owner-1")
    other = Principal("owner-2", "https://apaa.test", True, ("owner",))
    with pytest.raises(BrowserExecutionError, match="does not match"):
        _ProductionBrowserExecutionCoordinator(
            FakeWorker(), audit=lambda event: None,
            recovery_ledger=SQLiteBrowserRecoveryLedger(private_dir / "browser.sqlite3"),
            approval_authority=ApprovalAuthority(signing_secret=b"APAA test approval signing secret 32 bytes minimum"),
            owner_principal=other, owner_tenant=tenant,
            session_scope="owner-session-test-001", owner_session_check=lambda: True,
        )
