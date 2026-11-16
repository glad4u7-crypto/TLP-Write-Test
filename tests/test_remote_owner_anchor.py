import json

import pytest

from core.offline_owner_recovery import AnchorState
from core.remote_owner_anchor import HTTPSMonotonicAnchor, RemoteAnchorError


class FakeResponse:
    def __init__(self, status, document):
        self.status = status
        self.body = json.dumps(document).encode()

    def read(self, size):
        return self.body[:size]


class FakeConnection:
    def __init__(self, response):
        self.response = response
        self.calls = []
        self.sock = None

    def request(self, method, path, body=None, headers=None):
        self.calls.append((method, path, body, headers))

    def getresponse(self):
        return self.response

    def close(self):
        pass


class FakeSSLContext:
    def load_cert_chain(self, **_kwargs):
        pass


def make_anchor(tmp_path, response, calls):
    files = []
    for name, mode in (("ca.pem", 0o644), ("client.pem", 0o644), ("client.key", 0o600)):
        path = tmp_path / name
        path.write_text("test")
        path.chmod(mode)
        files.append(path)
    connection = FakeConnection(response)
    def factory(*_args, **_kwargs):
        calls.append(connection)
        return connection
    return HTTPSMonotonicAnchor(
        endpoint="https://anchor.example.test/prefix", ca_file=str(files[0]),
        client_cert=str(files[1]), client_key=str(files[2]), anchor_id="owner:primary",
        connection_factory=factory, ssl_context_factory=lambda _ca: FakeSSLContext(),
    )


def test_remote_owner_anchor_reads_and_atomic_cas_confirms_exact_state(tmp_path):
    calls = []
    target = {"revision": 1, "generation": "a" * 64, "change_id": "rekey-001"}
    response = FakeResponse(200, {"schema_version": 1, "state": target})
    anchor = make_anchor(tmp_path, response, calls)
    assert anchor.read() == AnchorState(1, "a" * 64, "rekey-001")
    assert calls[-1].calls[0][0:2] == ("GET", "/prefix/v1/anchors/owner%3Aprimary")

    calls.clear()
    response = FakeResponse(200, {"schema_version": 1, "advanced": True, "state": target})
    anchor = make_anchor(tmp_path, response, calls)
    assert anchor.compare_and_advance(
        expected=AnchorState(0, None, None),
        target=AnchorState(1, "a" * 64, "rekey-001"),
    ) is True
    request = json.loads(calls[-1].calls[0][2])
    assert request["expected"]["revision"] == 0
    assert request["target"] == target


def test_remote_anchor_conflict_and_malformed_response_fail_closed(tmp_path):
    calls = []
    anchor = make_anchor(
        tmp_path, FakeResponse(409, {
            "schema_version": 1, "advanced": False,
            "state": {"revision": 1, "generation": "b" * 64, "change_id": "other-001"},
        }), calls,
    )
    assert anchor.compare_and_advance(
        expected=AnchorState(0, None, None),
        target=AnchorState(1, "a" * 64, "rekey-001"),
    ) is False

    anchor = make_anchor(tmp_path, FakeResponse(200, {"schema_version": 1, "advanced": True}), [])
    with pytest.raises(RemoteAnchorError):
        anchor.compare_and_advance(
            expected=AnchorState(0, None, None),
            target=AnchorState(1, "a" * 64, "rekey-001"),
        )


def test_remote_anchor_rejects_http_redirects_and_unsafe_tls_key_permissions(tmp_path):
    calls = []
    anchor = make_anchor(tmp_path, FakeResponse(302, {"schema_version": 1}), calls)
    with pytest.raises(RemoteAnchorError, match="HTTP 302"):
        anchor.read()

    key = tmp_path / "bad.key"
    key.write_text("test")
    key.chmod(0o644)
    with pytest.raises(RemoteAnchorError, match="permissions"):
        HTTPSMonotonicAnchor(
            endpoint="https://anchor.example.test", ca_file=str(tmp_path / "ca.pem"),
            client_cert=str(tmp_path / "client.pem"), client_key=str(key),
            anchor_id="owner:primary", connection_factory=lambda *_a, **_k: None,
            ssl_context_factory=lambda _ca: FakeSSLContext(),
        )


def test_remote_anchor_rejects_non_https_and_bad_transitions(tmp_path):
    with pytest.raises(RemoteAnchorError, match="HTTPS"):
        HTTPSMonotonicAnchor(
            endpoint="http://anchor.example.test", ca_file=str(tmp_path / "ca.pem"),
            client_cert=str(tmp_path / "client.pem"), client_key=str(tmp_path / "client.key"),
            anchor_id="owner:primary", ssl_context_factory=lambda _ca: FakeSSLContext(),
        )
    calls = []
    anchor = make_anchor(
        tmp_path, FakeResponse(200, {"schema_version": 1, "advanced": True,
                                     "state": {"revision": 2, "generation": "a" * 64, "change_id": "jump-001"}}),
        calls,
    )
    assert anchor.compare_and_advance(
        expected=AnchorState(0, None, None),
        target=AnchorState(2, "a" * 64, "jump-001"),
    ) is False


def test_remote_sequence_backend_uses_same_mtls_anchor_service(tmp_path):
    calls = []
    anchor = make_anchor(
        tmp_path, FakeResponse(200, {"schema_version": 1, "sequence": 7}), calls,
    )
    assert anchor.read_sequence("control:root-001") == 7
    calls.clear()
    anchor = make_anchor(
        tmp_path, FakeResponse(200, {"schema_version": 1, "advanced": True, "sequence": 8}), calls,
    )
    assert anchor.advance_sequence("control:root-001", expected_current=7, new_sequence=8)
    request = json.loads(calls[-1].calls[0][2])
    assert request == {"schema_version": 1, "expected_current": 7, "new_sequence": 8}
