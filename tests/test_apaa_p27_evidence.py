import hashlib
import json
from pathlib import Path

import base64
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from scripts.validate_apaa_p27_evidence import (
    EvidenceValidationError,
    main,
    validate_evidence_directory,
)


FILES = (
    "host-preflight.json", "identity.json", "trust.json", "lifecycle.json",
    "egress.json", "negative-tests.json", "failure-cleanup.json",
    "anchor-recovery.json", "review.json",
)


def make_pack(root: Path):
    root.mkdir()
    hashes = {}
    for name in FILES:
        payload = json.dumps({"gate": name, "result": "BLOCKED"}).encode()
        (root / name).write_bytes(payload)
        hashes[name] = hashlib.sha256(payload).hexdigest()
    manifest = {
        "schema_version": 1,
        "run_id": "p27-test-run",
        "operator": "test-operator",
        "approval_reference": "approval-test-001",
        "host_alias": "disposable-host",
        "started_at_utc": "2026-11-16T10:00:00Z",
        "ended_at_utc": "2026-11-16T10:01:00+00:00",
        "runtime_name": "podman",
        "runtime_version": "4.9.3",
        "collector_version": "test",
        "signer_version": "test",
        "test_image_digest": "sha256:" + "a" * 64,
        "proxy_policy_id": "policy-test",
        "files": hashes,
    }
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return manifest


def test_validates_complete_pack_and_labels_authenticity_unchecked(tmp_path):
    root = tmp_path / "evidence"
    make_pack(root)
    result = validate_evidence_directory(root)
    assert result["valid"] is True
    assert result["artifact_count"] == len(FILES)
    assert result["authenticity"] == "NOT_CHECKED"
    assert result["host_qualification"] == "NOT_ASSESSED"


def test_rejects_tampered_artifact(tmp_path):
    root = tmp_path / "evidence"
    make_pack(root)
    (root / "egress.json").write_text('{"tampered":true}')
    with pytest.raises(EvidenceValidationError, match="SHA-256 mismatch"):
        validate_evidence_directory(root)


def test_rejects_unlisted_extra_artifact(tmp_path):
    root = tmp_path / "evidence"
    make_pack(root)
    (root / "extra.log").write_text("unlisted")
    with pytest.raises(EvidenceValidationError, match="inventory mismatch"):
        validate_evidence_directory(root)


def test_rejects_missing_required_artifact(tmp_path):
    root = tmp_path / "evidence"
    manifest = make_pack(root)
    (root / "review.json").unlink()
    manifest["files"].pop("review.json")
    (root / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(EvidenceValidationError, match="required evidence artifacts"):
        validate_evidence_directory(root)


@pytest.mark.parametrize("path", ["../outside", "/tmp/escape", "a/../../escape", "manifest.json"])
def test_rejects_unsafe_manifest_paths(tmp_path, path):
    root = tmp_path / "evidence"
    manifest = make_pack(root)
    digest = manifest["files"].pop(FILES[0])
    manifest["files"][path] = digest
    (root / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(EvidenceValidationError):
        validate_evidence_directory(root)


def test_rejects_non_utc_or_reversed_timestamps(tmp_path):
    root = tmp_path / "evidence"
    manifest = make_pack(root)
    manifest["started_at_utc"] = "2026-11-16T10:00:00+05:30"
    (root / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(EvidenceValidationError, match="must use UTC"):
        validate_evidence_directory(root)


def test_rejects_mutable_or_invalid_image_reference(tmp_path):
    root = tmp_path / "evidence"
    manifest = make_pack(root)
    manifest["test_image_digest"] = "latest"
    (root / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(EvidenceValidationError, match="immutable sha256"):
        validate_evidence_directory(root)


def test_cli_returns_nonzero_for_missing_directory(tmp_path, capsys):
    assert main([str(tmp_path / "missing")]) == 2
    assert '"valid": false' in capsys.readouterr().out


def test_cli_returns_zero_for_valid_pack(tmp_path, capsys):
    root = tmp_path / "evidence"
    make_pack(root)
    assert main([str(root)]) == 0
    assert '"integrity": "PASS"' in capsys.readouterr().out


def test_rejects_unknown_manifest_fields(tmp_path):
    root = tmp_path / "evidence"
    manifest = make_pack(root)
    manifest["unexpected"] = "must-not-be-ignored"
    (root / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(EvidenceValidationError, match="unknown fields"):
        validate_evidence_directory(root)


def test_rejects_duplicate_json_object_keys(tmp_path):
    root = tmp_path / "evidence"
    make_pack(root)
    original = (root / "manifest.json").read_text()
    (root / "manifest.json").write_text(original[:-1] + ', "schema_version": 1}')
    with pytest.raises(EvidenceValidationError, match="duplicate JSON object keys"):
        validate_evidence_directory(root)


def _signed_pack(root: Path, tmp_path: Path):
    make_pack(root)
    raw = (root / "manifest.json").read_bytes()
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw)
    pub_path, sig_path = tmp_path / "trusted.pub", tmp_path / "manifest.sig"
    pub_path.write_bytes(public)
    sig_path.write_text(base64.b64encode(private.sign(raw)).decode("ascii"), encoding="ascii")
    return pub_path, sig_path, hashlib.sha256(public).hexdigest()


def test_detached_ed25519_manifest_signature_verifies(tmp_path):
    root = tmp_path / "evidence"
    pub, sig, fp = _signed_pack(root, tmp_path)
    result = validate_evidence_directory(root, signature_path=sig, public_key_path=pub, expected_key_sha256=fp)
    assert result["authenticity"] == "VERIFIED_ED25519"
    assert result["signer_key_sha256"] == fp


def test_rejects_manifest_changed_after_signing(tmp_path):
    root = tmp_path / "evidence"
    pub, sig, fp = _signed_pack(root, tmp_path)
    (root / "manifest.json").write_bytes((root / "manifest.json").read_bytes() + b" ")
    with pytest.raises(EvidenceValidationError):
        validate_evidence_directory(root, signature_path=sig, public_key_path=pub, expected_key_sha256=fp)


def test_rejects_wrong_pinned_key_fingerprint(tmp_path):
    root = tmp_path / "evidence"
    pub, sig, _ = _signed_pack(root, tmp_path)
    with pytest.raises(EvidenceValidationError, match="fingerprint"):
        validate_evidence_directory(root, signature_path=sig, public_key_path=pub, expected_key_sha256="0" * 64)


def test_rejects_signature_from_another_key(tmp_path):
    root = tmp_path / "evidence"; root.mkdir()
    pub, sig, fp = _signed_pack(root, tmp_path)
    wrong = Ed25519PrivateKey.generate()
    sig.write_text(base64.b64encode(wrong.sign((root / "manifest.json").read_bytes())).decode("ascii"))
    with pytest.raises(EvidenceValidationError, match="signature verification"):
        validate_evidence_directory(root, signature_path=sig, public_key_path=pub, expected_key_sha256=fp)


def test_rejects_signature_inside_evidence_directory(tmp_path):
    root = tmp_path / "evidence"
    manifest = make_pack(root)
    sig = root / "manifest.sig"; sig.write_text("invalid")
    manifest["files"]["manifest.sig"] = hashlib.sha256(sig.read_bytes()).hexdigest()
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    pub = tmp_path / "trusted.pub"; pub.write_bytes(b"x" * 32)
    with pytest.raises(EvidenceValidationError, match="outside the evidence directory"):
        validate_evidence_directory(root, signature_path=sig, public_key_path=pub, expected_key_sha256="0" * 64)


def test_requires_signature_and_key_together(tmp_path):
    root = tmp_path / "evidence"; root.mkdir(); make_pack(root)
    with pytest.raises(EvidenceValidationError, match="supplied together"):
        validate_evidence_directory(root, signature_path=tmp_path / "manifest.sig")
