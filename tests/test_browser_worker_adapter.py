import threading
import time

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import core.browser_worker_adapter as adapter_module
from core.browser_worker_adapter import AttestedBrowserWorkerAdapter, BrowserWorkerBootstrapError
from core.browser_runtime import build_worker_launch_spec
from core.browser_isolation import validate_worker_profile
from core.browser_execution import CancellationToken


PROXY_IP = "172.20.0.2"
PROXY = "http://egress-proxy.internal:3128"


def make_spec():
    profile = validate_worker_profile({
        "schema_version": 1, "uid": 10001, "gid": 10001,
        "privileged": False, "read_only_root": True, "no_new_privileges": True,
        "capabilities_drop": ["ALL"], "host_network": False, "host_pid": False,
        "host_ipc": False, "host_mounts": [], "secret_mounts": [],
        "writable_mounts": ["/tmp/job"], "browser_profile_persistence": False,
        "cdp_exposed": False, "direct_egress": False, "proxy_only_egress": True,
        "dns_via_proxy_only": True, "egress_proxy": PROXY,
        "memory_limit_bytes": 512 * 1024 * 1024, "cpu_limit_millis": 1000,
        "pids_limit": 64, "job_timeout_seconds": 30,
    })
    return build_worker_launch_spec(profile)


class FakeSnapshotSource:
    def read_runtime_attestation(self): return {}
    def read_network_namespace_identity(self): return {}
    def read_nftables_json(self): return {}


class FakeProcess:
    def __init__(self, result=None, *, fail_terminate=False, block=False):
        self.result = result or {"ok": True}
        self.fail_terminate = fail_terminate
        self.block = block
        self.terminate_calls = 0
        self.stop = threading.Event()

    def run(self, job, **kwargs):
        if self.block:
            while not self.stop.wait(0.01):
                if kwargs["cancellation"].cancelled:
                    break
                if time.monotonic() >= kwargs["deadline_monotonic"]:
                    break
        return self.result

    def terminate(self):
        self.terminate_calls += 1
        self.stop.set()
        return not self.fail_terminate


class FakeBackend:
    def __init__(self, process=None, *, source=None, fail_destroy=False):
        self.process = process or FakeProcess()
        self.source = source or FakeSnapshotSource()
        self.fail_destroy = fail_destroy
        self.calls = []
        self.handle = object()

    def provision(self, spec, *, session_id):
        self.calls.append(("provision", spec.digest, session_id))
        return self.handle

    def snapshot_source(self, handle):
        self.calls.append(("snapshot", handle))
        return self.source

    def start_worker(self, handle, spec, verified):
        self.calls.append(("start", handle, spec.digest, verified))
        return self.process

    def destroy_worker(self, handle):
        self.calls.append(("destroy", handle))
        return not self.fail_destroy


def make_adapter(monkeypatch, backend=None, *, challenge="a" * 64):
    spec = make_spec()
    key = Ed25519PrivateKey.generate()
    backend = backend or FakeBackend()
    collected = []

    def collect(source, received_spec, **kwargs):
        collected.append((source, received_spec, kwargs))
        return {"signed": "evidence"}

    class FakeGate:
        def __init__(self, gate_spec, **kwargs):
            self.spec = gate_spec
            self.kwargs = kwargs

        def launch(self, evidence, *, challenge, now):
            assert evidence == {"signed": "evidence"}
            return self.kwargs["worker_start"](self.spec, {"verified": True})

    monkeypatch.setattr(adapter_module, "collect_signed_inspector_evidence", collect)
    monkeypatch.setattr(adapter_module, "AttestedBrowserRuntime", FakeGate)
    instance = AttestedBrowserWorkerAdapter(
        spec,
        backend=backend,
        signing_key=key,
        key_id="host-inspector-prod",
        trusted_public_keys={"host-inspector-prod": key.public_key().public_bytes_raw()},
        expected_proxy_addresses=[PROXY_IP],
        challenge_factory=lambda size: challenge,
        cleanup_wait_seconds=2,
    )
    return instance, backend, collected


def execute(adapter, session_id="session-1234567890"):
    return adapter.run(
        {"job_id": "job_12345678"},
        session_id=session_id,
        cancellation=CancellationToken(),
        deadline_monotonic=time.monotonic() + 5,
        pinned_destination={"hostname": "example.com", "addresses": ["93.184.216.34"]},
    )


def test_worker_is_provisioned_attested_started_and_destroyed_in_order(monkeypatch):
    worker, backend, collected = make_adapter(monkeypatch)
    result = execute(worker)

    assert result == {"ok": True}
    assert [call[0] for call in backend.calls] == [
        "provision", "snapshot", "start", "destroy"
    ]
    assert collected[0][1] is worker._spec
    assert collected[0][2]["challenge"] == "a" * 64
    assert backend.process.terminate_calls == 1


def test_worker_cleanup_runs_when_snapshot_collection_fails(monkeypatch):
    backend = FakeBackend()

    def broken_collect(*args, **kwargs):
        raise OSError("inspector unavailable")

    monkeypatch.setattr(adapter_module, "collect_signed_inspector_evidence", broken_collect)
    spec = make_spec()
    key = Ed25519PrivateKey.generate()
    worker = AttestedBrowserWorkerAdapter(
        spec, backend=backend, signing_key=key, key_id="host-inspector-prod",
        trusted_public_keys={"host-inspector-prod": key.public_key().public_bytes_raw()},
        expected_proxy_addresses=[PROXY_IP], cleanup_wait_seconds=2,
    )
    with pytest.raises(BrowserWorkerBootstrapError, match="trusted host snapshot source"):
        execute(worker)
    assert [call[0] for call in backend.calls] == ["provision", "snapshot", "destroy"]


def test_worker_refuses_missing_or_invalid_backend_before_any_execution():
    spec = make_spec()
    key = Ed25519PrivateKey.generate()
    with pytest.raises(TypeError, match="IsolatedWorkerBackend"):
        AttestedBrowserWorkerAdapter(
            spec, backend=None, signing_key=key, key_id="host-inspector-prod",
            trusted_public_keys={"host-inspector-prod": key.public_key().public_bytes_raw()},
            expected_proxy_addresses=[PROXY_IP],
        )


def test_invalid_snapshot_source_fails_closed_and_destroys_worker(monkeypatch):
    backend = FakeBackend(source=object())
    worker, backend, _ = make_adapter(monkeypatch, backend)
    with pytest.raises(BrowserWorkerBootstrapError, match="failed closed"):
        execute(worker)
    assert [call[0] for call in backend.calls] == ["provision", "snapshot", "destroy"]


def test_worker_process_exit_and_storage_cleanup_must_both_be_confirmed(monkeypatch):
    backend = FakeBackend(fail_destroy=True)
    worker, backend, _ = make_adapter(monkeypatch, backend)
    with pytest.raises(BrowserWorkerBootstrapError, match="not confirmed"):
        execute(worker)
    assert backend.process.terminate_calls == 1
    assert backend.calls[-1][0] == "destroy"


def test_duplicate_session_ids_are_rejected(monkeypatch):
    worker, backend, _ = make_adapter(monkeypatch)
    state = adapter_module._WorkerState(session_id="session-1234567890")
    worker._states[state.session_id] = state
    with pytest.raises(BrowserWorkerBootstrapError, match="cannot be reused"):
        execute(worker)
    assert backend.calls == []


def test_cancel_terminates_remote_process_and_waits_for_cleanup(monkeypatch):
    worker, backend, _ = make_adapter(monkeypatch, FakeBackend(process=FakeProcess(block=True)))
    cancellation = CancellationToken()
    outcome = {}

    def run():
        try:
            outcome["result"] = worker.run(
                {"job_id": "job_12345678"},
                session_id="session-cancel-1234",
                cancellation=cancellation,
                deadline_monotonic=time.monotonic() + 5,
                pinned_destination={},
            )
        except Exception as exc:
            outcome["error"] = exc

    thread = threading.Thread(target=run)
    thread.start()
    deadline = time.monotonic() + 2
    while (
        worker._states.get("session-cancel-1234") is None
        or worker._states["session-cancel-1234"].process is None
    ) and time.monotonic() < deadline:
        time.sleep(0.01)
    assert worker._states["session-cancel-1234"].process is not None
    cancellation.cancel()
    assert worker.terminate("session-cancel-1234") is True
    thread.join(timeout=2)
    assert not thread.is_alive()
    assert backend.calls[-1][0] == "destroy"



class RealSignedHost:
    def __init__(self, spec):
        now = int(time.time())
        self.runtime = {
            "schema_version": 1, "launch_spec_digest": spec.digest,
            "runtime_id": "runtime:real-test-01", "worker_id": "worker:real-test-01",
            "image_digest": "sha256:" + "a" * 64,
            "attestor_id": "inspector:real-test-01", "evidence_digest": "b" * 64,
            "observed_at": now, "state": "created", "process_started": False,
            "runtime_config_verified": True, "host_firewall_verified": True,
            "uid": spec.uid, "gid": spec.gid, "privileged": False,
            "read_only_root": True, "no_new_privileges": True,
            "capabilities_effective": [], "namespaces": list(spec.namespaces),
            "host_mounts": [], "secret_mounts": [],
            "writable_mounts": list(spec.writable_mounts),
            "browser_profile_persistence": False, "cdp_exposed": False,
            "direct_egress": False, "proxy_only_egress": True,
            "dns_via_proxy_only": True, "egress_proxy": spec.egress_proxy,
            "memory_limit_bytes": spec.memory_limit_bytes,
            "cpu_limit_millis": spec.cpu_limit_millis,
            "pids_limit": spec.pids_limit, "job_timeout_seconds": spec.job_timeout_seconds,
            "seccomp_enforced": True, "network_namespace_isolated": True,
            "firewall_default_deny": True,
            "egress_allowed": ["egress-proxy.internal:3128"],
            "direct_dns_egress_blocked": True, "proxy_side_dns_only": True,
        }
        self.namespace = {
            "runtime_id": "runtime:real-test-01", "worker_id": "worker:real-test-01",
            "inode": 4026533001, "interface": "eth0",
        }
        self.rules = {"nftables": [
            {"metainfo": {"version": "1.0.9", "release_name": "test"}},
            {"table": {"family": "inet", "name": "filter"}},
            {"chain": {"family": "inet", "table": "filter", "name": "egress",
                       "type": "filter", "hook": "output", "prio": 0, "policy": "drop"}},
            {"rule": {"family": "inet", "table": "filter", "chain": "egress", "expr": [
                {"match": {"op": "==", "left": {"meta": {"key": "l4proto"}}, "right": "tcp"}},
                {"match": {"op": "==", "left": {"payload": {"protocol": "ip", "field": "daddr"}}, "right": PROXY_IP}},
                {"match": {"op": "==", "left": {"payload": {"protocol": "tcp", "field": "dport"}}, "right": 3128}},
                {"accept": None},
            ]}},
        ]}

    def read_runtime_attestation(self): return self.runtime
    def read_network_namespace_identity(self): return self.namespace
    def read_nftables_json(self): return self.rules


class RealGateBackend(FakeBackend):
    def __init__(self):
        super().__init__()
        self.verified_evidence = None

    def snapshot_source(self, handle):
        self.calls.append(("snapshot", handle))
        return RealSignedHost(self._spec)

    def provision(self, spec, *, session_id):
        self._spec = spec
        return super().provision(spec, session_id=session_id)

    def start_worker(self, handle, spec, verified):
        from core.browser_inspector import VerifiedInspectorEvidence
        assert type(verified) is VerifiedInspectorEvidence
        self.verified_evidence = verified
        return super().start_worker(handle, spec, verified)


def test_real_ed25519_and_nftables_evidence_gate_precedes_remote_browser_start():
    spec = make_spec()
    key = Ed25519PrivateKey.generate()
    backend = RealGateBackend()
    worker = AttestedBrowserWorkerAdapter(
        spec,
        backend=backend,
        signing_key=key,
        key_id="host-inspector-prod",
        trusted_public_keys={"host-inspector-prod": key.public_key().public_bytes_raw()},
        expected_proxy_addresses=[PROXY_IP],
        cleanup_wait_seconds=2,
    )

    result = execute(worker, session_id="session-real-gate-1234")

    assert result == {"ok": True}
    assert backend.verified_evidence is not None
    assert backend.verified_evidence.firewall.default_egress_policy == "drop"
    assert backend.verified_evidence.firewall.allowed_proxy_addresses == (PROXY_IP,)
    assert [call[0] for call in backend.calls] == ["provision", "snapshot", "start", "destroy"]
