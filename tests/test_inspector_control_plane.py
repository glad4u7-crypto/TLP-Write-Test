import copy
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from core.inspector_control_plane import (
    InspectorControlPlaneError,
    InspectorEvidenceControlPlane,
)
from core.inspector_key_registry import (
    InspectorPublicKeyRecord,
    InspectorPublicKeyRegistry,
)
from core.sqlite_security_store import SQLiteSecurityStore
from core.storage import TenantKey
from core.browser_runtime import build_worker_launch_spec
from test_browser_inspector import profile, signed_envelope


TENANT = TenantKey("https://issuer.example", "inspector-service")
RUNTIME = "runtime:test-001"
WORKER = "worker:test-001"
NOW = 1000


def _registry(public_key, *, key_id="host-inspector-prod", not_before=900,
              not_after=1100, revoked=False):
    return InspectorPublicKeyRegistry([
        InspectorPublicKeyRecord(
            key_id=key_id,
            public_key=public_key,
            not_before=not_before,
            not_after=not_after,
            revoked=revoked,
        )
    ])


def _setup(tmp_path, *, now=NOW):
    spec = build_worker_launch_spec(profile())
    private = Ed25519PrivateKey.generate()
    envelope, _ = signed_envelope(spec, private)
    public_key = private.public_key().public_bytes(encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw)
    store = SQLiteSecurityStore(tmp_path / "inspector-control.sqlite3")
    registry = _registry(public_key)
    control = InspectorEvidenceControlPlane(
        security_store=store, key_registry=registry,
    )
    challenge = control.issue_challenge(
        TENANT, runtime_id=RUNTIME, worker_id=WORKER, ttl_seconds=60, now=now,
    )
    envelope["payload"]["challenge"] = challenge.value
    # Re-sign the modified payload with the test-only ephemeral private key.
    import base64
    import json
    signed = {
        "schema_version": envelope["schema_version"],
        "key_id": envelope["key_id"],
        "payload": envelope["payload"],
    }
    canonical = json.dumps(
        signed, sort_keys=True, separators=(",", ":"),
        ensure_ascii=True, allow_nan=False,
    ).encode("utf-8")
    envelope["signature"] = base64.b64encode(private.sign(canonical)).decode("ascii")
    return spec, private, store, control, challenge, envelope


def _accept(control, spec, challenge, envelope, *, now=NOW, tenant=TENANT):
    return control.verify_and_consume(
        tenant, spec, envelope,
        expected_challenge=challenge.value,
        expected_runtime_id=RUNTIME,
        expected_worker_id=WORKER,
        expected_proxy_addresses=["172.20.0.2"],
        now=now,
    )


def test_control_plane_issues_and_accepts_valid_evidence_once(tmp_path):
    spec, _, _, control, challenge, envelope = _setup(tmp_path)
    accepted = _accept(control, spec, challenge, envelope)
    assert accepted.evidence.runtime.runtime_id == RUNTIME
    assert accepted.evidence.runtime.worker_id == WORKER
    assert accepted.accepted_at == NOW
    with pytest.raises(InspectorControlPlaneError, match="replayed"):
        _accept(control, spec, challenge, envelope)


def test_bad_signature_does_not_consume_challenge(tmp_path):
    spec, _, store, control, challenge, envelope = _setup(tmp_path)
    broken = copy.deepcopy(envelope)
    broken["signature"] = "A" * 88
    with pytest.raises(InspectorControlPlaneError, match="verification failed"):
        _accept(control, spec, challenge, broken)
    assert store.consume_inspector_challenge(
        TENANT, challenge.value, runtime_id=RUNTIME, worker_id=WORKER, now=NOW,
    )


def test_revoked_or_expired_key_rejected_without_consuming_challenge(tmp_path):
    spec, private, store, control, challenge, envelope = _setup(tmp_path)
    public_key = private.public_key().public_bytes_raw()
    revoked = InspectorEvidenceControlPlane(
        security_store=store,
        key_registry=_registry(public_key, revoked=True),
    )
    with pytest.raises(InspectorControlPlaneError):
        _accept(revoked, spec, challenge, envelope)
    assert store.consume_inspector_challenge(
        TENANT, challenge.value, runtime_id=RUNTIME, worker_id=WORKER, now=NOW,
    )


def test_expired_key_is_rejected(tmp_path):
    spec, private, store, _, challenge, envelope = _setup(tmp_path)
    expired = InspectorEvidenceControlPlane(
        security_store=store,
        key_registry=_registry(
            private.public_key().public_bytes_raw(), not_before=800, not_after=NOW,
        ),
    )
    with pytest.raises(InspectorControlPlaneError):
        _accept(expired, spec, challenge, envelope)
    assert store.consume_inspector_challenge(
        TENANT, challenge.value, runtime_id=RUNTIME, worker_id=WORKER, now=NOW,
    )


def test_wrong_tenant_cannot_consume_another_tenants_challenge(tmp_path):
    spec, _, store, control, challenge, envelope = _setup(tmp_path)
    other = TenantKey("https://issuer.example", "another-principal")
    with pytest.raises(InspectorControlPlaneError, match="unknown"):
        _accept(control, spec, challenge, envelope, tenant=other)
    assert store.consume_inspector_challenge(
        TENANT, challenge.value, runtime_id=RUNTIME, worker_id=WORKER, now=NOW,
    )


def test_wrong_expected_runtime_or_worker_does_not_consume(tmp_path):
    spec, _, store, control, challenge, envelope = _setup(tmp_path)
    with pytest.raises(InspectorControlPlaneError, match="identity mismatch"):
        control.verify_and_consume(
            TENANT, spec, envelope, expected_challenge=challenge.value,
            expected_runtime_id="runtime:other-001",
            expected_worker_id=WORKER,
            expected_proxy_addresses=["172.20.0.2"], now=NOW,
        )
    assert store.consume_inspector_challenge(
        TENANT, challenge.value, runtime_id=RUNTIME, worker_id=WORKER, now=NOW,
    )


def test_expired_challenge_is_rejected_after_signature_verification(tmp_path):
    spec, _, _, control, challenge, envelope = _setup(tmp_path)
    with pytest.raises(InspectorControlPlaneError, match="unknown, expired"):
        _accept(control, spec, challenge, envelope, now=challenge.expires_at)
