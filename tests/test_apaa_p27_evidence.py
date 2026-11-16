import hashlib
import json
from pathlib import Path

import pytest

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
