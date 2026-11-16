import base64
import hashlib
import json
from pathlib import Path
from datetime import datetime, timezone

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from scripts.verify_apaa_p27_review import (
    ReviewAttestationError,
    verify_review_attestation,
)
from scripts.validate_apaa_p27_evidence import validate_evidence_directory

FILES = (
    "host-preflight.json", "identity.json", "trust.json", "lifecycle.json",
    "egress.json", "negative-tests.json", "failure-cleanup.json",
    "anchor-recovery.json", "review.json",
)


def _pack(root: Path, tmp_path: Path):
    root.mkdir()
    hashes = {}
    for name in FILES:
        payload = json.dumps({"gate": name, "result": "BLOCKED"}).encode()
        (root / name).write_bytes(payload)
        hashes[name] = hashlib.sha256(payload).hexdigest()
    manifest = {
        "schema_version": 1, "run_id": "review-test", "operator": "operator",
        "approval_reference": "approval", "host_alias": "disposable",
        "started_at_utc": "2026-11-16T10:00:00Z", "ended_at_utc": "2026-11-16T10:01:00Z",
        "runtime_name": "podman", "runtime_version": "4.9.3",
        "collector_version": "test", "signer_version": "test",
        "test_image_digest": "sha256:" + "a" * 64, "proxy_policy_id": "policy",
        "files": hashes,
    }
    raw = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    (root / "manifest.json").write_bytes(raw)
    manifest_private = Ed25519PrivateKey.generate()
    manifest_public = manifest_private.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    manifest_sig = tmp_path / "manifest.sig"
    manifest_pub = tmp_path / "manifest.pub"
    manifest_sig.write_text(base64.b64encode(manifest_private.sign(raw)).decode())
    manifest_pub.write_bytes(manifest_public)

    reviewer_private = Ed25519PrivateKey.generate()
    reviewer_public = reviewer_private.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    attestation = {
        "schema_version": 1,
        "reviewer_id": "independent-reviewer-01",
        "reviewed_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "manifest_sha256": hashlib.sha256(raw).hexdigest(),
        "reviewer_key_sha256": hashlib.sha256(reviewer_public).hexdigest(),
        "disposition": "PASS",
        "findings": [],
    }
    canonical = json.dumps(attestation, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    attestation_path = tmp_path / "review-attestation.json"
    signature_path = tmp_path / "review-attestation.sig"
    reviewer_pub_path = tmp_path / "reviewer.pub"
    attestation_path.write_bytes(canonical)
    signature_path.write_text(base64.b64encode(reviewer_private.sign(canonical)).decode())
    reviewer_pub_path.write_bytes(reviewer_public)
    return {
        "manifest_signature": manifest_sig, "manifest_public": manifest_pub,
        "manifest_fingerprint": hashlib.sha256(manifest_public).hexdigest(),
        "attestation": attestation_path, "review_signature": signature_path,
        "review_public": reviewer_pub_path,
        "review_fingerprint": hashlib.sha256(reviewer_public).hexdigest(),
        "attestation_data": attestation,
        "reviewer_private": reviewer_private,
    }


def _verify(root, data):
    return verify_review_attestation(
        root,
        manifest_signature_path=data["manifest_signature"],
        manifest_public_key_path=data["manifest_public"],
        expected_manifest_key_sha256=data["manifest_fingerprint"],
        review_attestation_path=data["attestation"],
        review_signature_path=data["review_signature"],
        reviewer_public_key_path=data["review_public"],
        expected_reviewer_key_sha256=data["review_fingerprint"],
    )


def _resign(data):
    att = data["attestation_data"]
    canonical = json.dumps(att, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    data["attestation"].write_bytes(canonical)
    data["review_signature"].write_text(
        base64.b64encode(data["reviewer_private"].sign(canonical)).decode()
    )


def test_accepts_manifest_bound_signed_independent_review(tmp_path):
    root = tmp_path / "evidence"
    data = _pack(root, tmp_path)
    result = _verify(root, data)
    assert result["valid"] is True
    assert result["disposition"] == "PASS"
    assert result["qualification_approval"] == "NOT_GRANTED_BY_CRYPTOGRAPHIC_VERIFICATION"
    assert result["reviewer_independence"] == "OUT_OF_BAND_INDEPENDENCE_CHECK_REQUIRED"


def test_rejects_review_bound_to_different_manifest(tmp_path):
    root = tmp_path / "evidence"
    data = _pack(root, tmp_path)
    data["attestation_data"]["manifest_sha256"] = "0" * 64
    _resign(data)
    with pytest.raises(ReviewAttestationError, match="not bound"):
        _verify(root, data)


def test_rejects_wrong_reviewer_key_pin(tmp_path):
    root = tmp_path / "evidence"
    data = _pack(root, tmp_path)
    data["review_fingerprint"] = "0" * 64
    with pytest.raises(ReviewAttestationError, match="pinned fingerprint"):
        _verify(root, data)


def test_rejects_tampered_review_attestation(tmp_path):
    root = tmp_path / "evidence"
    data = _pack(root, tmp_path)
    data["attestation"].write_text(data["attestation"].read_text().replace("PASS", "FAIL"))
    with pytest.raises(ReviewAttestationError, match="signature verification"):
        _verify(root, data)


def test_rejects_pass_with_unresolved_findings(tmp_path):
    root = tmp_path / "evidence"
    data = _pack(root, tmp_path)
    data["attestation_data"]["findings"] = ["egress evidence missing"]
    _resign(data)
    with pytest.raises(ReviewAttestationError, match="cannot contain"):
        _verify(root, data)


def test_rejects_non_utc_review_timestamp(tmp_path):
    root = tmp_path / "evidence"
    data = _pack(root, tmp_path)
    data["attestation_data"]["reviewed_at_utc"] = "2026-11-16T10:02:00+05:30"
    _resign(data)
    with pytest.raises(ReviewAttestationError, match="must use UTC"):
        _verify(root, data)


def test_rejects_attestation_sidecar_inside_evidence_pack(tmp_path):
    root = tmp_path / "evidence"
    data = _pack(root, tmp_path)
    inside = root / "review-attestation.json"
    inside.write_bytes(data["attestation"].read_bytes())
    data["attestation"] = inside
    with pytest.raises(ReviewAttestationError, match="outside the evidence directory"):
        _verify(root, data)
