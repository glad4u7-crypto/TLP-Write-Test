import hashlib
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from scripts.build_apaa_p27_manifest import ManifestBuildError, build_manifest, main
from scripts.validate_apaa_p27_evidence import validate_evidence_directory

FILES = (
    "host-preflight.json", "identity.json", "trust.json", "lifecycle.json",
    "egress.json", "negative-tests.json", "failure-cleanup.json",
    "anchor-recovery.json", "review.json",
)
METADATA = {
    "run_id": "operator-run-01",
    "operator": "approved-operator",
    "approval_reference": "change-approval-123",
    "host_alias": "disposable-linux-01",
    "started_at_utc": "2026-11-16T10:00:00Z",
    "ended_at_utc": "2026-11-16T10:30:00+00:00",
    "runtime_name": "podman",
    "runtime_version": "4.9.3",
    "collector_version": "reviewed-build",
    "signer_version": "external-provider-v1",
    "test_image_digest": "sha256:" + "a" * 64,
    "proxy_policy_id": "approved-proxy-policy-01",
}


def _evidence(root: Path):
    root.mkdir()
    for name in FILES:
        # Deliberately BLOCKED: manifest creation must not imply a qualification PASS.
        (root / name).write_text(json.dumps({"gate": name, "result": "BLOCKED"}), encoding="utf-8")


def test_builds_manifest_that_integrity_validator_accepts(tmp_path):
    root = tmp_path / "evidence"
    _evidence(root)
    manifest = build_manifest(root, METADATA)
    assert manifest["schema_version"] == 1
    assert set(manifest["files"]) == set(FILES)
    for name in FILES:
        assert manifest["files"][name] == hashlib.sha256((root / name).read_bytes()).hexdigest()
    result = validate_evidence_directory(root)
    assert result["valid"] is True
    assert result["authenticity"] == "NOT_CHECKED"
    assert result["host_qualification"] == "NOT_ASSESSED"


def test_refuses_to_overwrite_existing_manifest(tmp_path):
    root = tmp_path / "evidence"
    _evidence(root)
    build_manifest(root, METADATA)
    with pytest.raises(ManifestBuildError, match="already exists"):
        build_manifest(root, METADATA)


def test_rejects_missing_or_extra_artifacts(tmp_path):
    root = tmp_path / "evidence"
    _evidence(root)
    (root / "review.json").unlink()
    with pytest.raises(ManifestBuildError, match="inventory mismatch"):
        build_manifest(root, METADATA)


def test_rejects_symlink_artifact(tmp_path):
    root = tmp_path / "evidence"
    _evidence(root)
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")
    (root / "egress.json").unlink()
    (root / "egress.json").symlink_to(outside)
    with pytest.raises(ManifestBuildError, match="regular non-symlink"):
        build_manifest(root, METADATA)


@pytest.mark.parametrize("field,value,match", [
    ("test_image_digest", "podman:latest", "immutable sha256"),
    ("started_at_utc", "2026-11-16T10:00:00+05:30", "UTC"),
    ("ended_at_utc", "2026-11-16T09:00:00Z", "precedes"),
])
def test_rejects_invalid_metadata(tmp_path, field, value, match):
    root = tmp_path / "evidence"
    _evidence(root)
    metadata = dict(METADATA)
    metadata[field] = value
    with pytest.raises(ManifestBuildError, match=match):
        build_manifest(root, metadata)


def test_rejects_non_json_artifact(tmp_path):
    root = tmp_path / "evidence"
    _evidence(root)
    (root / "trust.json").write_text("not-json", encoding="utf-8")
    with pytest.raises(ManifestBuildError, match="valid UTF-8 JSON"):
        build_manifest(root, METADATA)


def test_cli_reports_non_approval(tmp_path, capsys):
    root = tmp_path / "evidence"
    _evidence(root)
    args = [str(root)]
    for key, value in METADATA.items():
        args.extend(["--" + key.replace("_", "-"), value])
    assert main(args) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["authenticity"] == "NOT_CHECKED"
    assert output["host_qualification"] == "NOT_ASSESSED"



def test_rejects_hardlinked_artifact(tmp_path):
    root = tmp_path / "evidence"
    _evidence(root)
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")
    (root / "egress.json").unlink()
    (root / "egress.json").hardlink_to(outside)
    with pytest.raises(ManifestBuildError, match="singly-linked regular file"):
        build_manifest(root, METADATA)


def test_rejects_evidence_directory_symlink(tmp_path):
    actual = tmp_path / "actual"
    _evidence(actual)
    alias = tmp_path / "evidence-link"
    alias.symlink_to(actual, target_is_directory=True)
    with pytest.raises(ManifestBuildError, match="real directory"):
        build_manifest(alias, METADATA)


def test_no_follow_open_rejects_symlink_swap_after_inventory(tmp_path, monkeypatch):
    import os
    import scripts.build_apaa_p27_manifest as builder

    root = tmp_path / "evidence"
    _evidence(root)
    outside = tmp_path / "outside.json"
    outside.write_text('{"secret":"not-read"}', encoding="utf-8")
    real_open = os.open
    swapped = False

    def swap_before_open(path, flags, *args, **kwargs):
        nonlocal swapped
        if path == "egress.json" and kwargs.get("dir_fd") is not None and not swapped:
            swapped = True
            (root / "egress.json").unlink()
            (root / "egress.json").symlink_to(outside)
        return real_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(builder.os, "open", swap_before_open)
    with pytest.raises(ManifestBuildError, match="regular non-symlink"):
        build_manifest(root, METADATA)
    assert swapped is True
    assert not (root / "manifest.json").exists()



def test_concurrent_builders_publish_exactly_one_complete_manifest(tmp_path, monkeypatch):
    import scripts.build_apaa_p27_manifest as builder

    root = tmp_path / "evidence"
    _evidence(root)
    barrier = threading.Barrier(2)
    real_read = builder._read_artifact

    def synchronized_read(root_fd, name):
        raw = real_read(root_fd, name)
        if name == "review.json":
            barrier.wait(timeout=5)
        return raw

    monkeypatch.setattr(builder, "_read_artifact", synchronized_read)

    def attempt():
        try:
            return ("created", build_manifest(root, METADATA))
        except ManifestBuildError:
            return ("rejected", None)

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _: attempt(), range(2)))

    assert sorted(item[0] for item in outcomes) == ["created", "rejected"]
    published = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    assert set(published["files"]) == set(FILES)
    assert not list(root.glob(".manifest-*.tmp"))


def test_manifest_is_fully_staged_before_atomic_publication(tmp_path, monkeypatch):
    import scripts.build_apaa_p27_manifest as builder

    root = tmp_path / "evidence"
    _evidence(root)
    real_link = builder.os.link
    observed = []

    def inspect_then_publish(src, dst, **kwargs):
        assert dst == "manifest.json"
        assert not (root / "manifest.json").exists()
        staged = (root / src).read_bytes()
        parsed = json.loads(staged.decode("utf-8"))
        assert set(parsed["files"]) == set(FILES)
        observed.append(len(staged))
        return real_link(src, dst, **kwargs)

    monkeypatch.setattr(builder.os, "link", inspect_then_publish)
    build_manifest(root, METADATA)
    assert observed and (root / "manifest.json").stat().st_size == observed[0]
    assert not list(root.glob(".manifest-*.tmp"))


def test_failed_manifest_publication_leaves_no_partial_final_file(tmp_path, monkeypatch):
    import scripts.build_apaa_p27_manifest as builder

    root = tmp_path / "evidence"
    _evidence(root)

    def fail_link(*args, **kwargs):
        raise OSError("simulated publication interruption")

    monkeypatch.setattr(builder.os, "link", fail_link)
    with pytest.raises(OSError, match="simulated publication interruption"):
        build_manifest(root, METADATA)
    assert not (root / "manifest.json").exists()
    assert not list(root.glob(".manifest-*.tmp"))
