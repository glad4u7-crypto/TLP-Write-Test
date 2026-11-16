"""Build a P27 manifest from operator-collected JSON artifacts.

This utility only inventories and hashes files. It does not collect host facts,
run qualification tests, authenticate a signer, or approve qualification.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path

_REQUIRED = (
    "host-preflight.json", "identity.json", "trust.json", "lifecycle.json",
    "egress.json", "negative-tests.json", "failure-cleanup.json",
    "anchor-recovery.json", "review.json",
)
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")


class ManifestBuildError(ValueError):
    """Raised when the evidence directory cannot safely be inventoried."""


def _utc(value: str, field: str) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise ManifestBuildError(f"{field} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None or parsed.utcoffset().total_seconds() != 0:
        raise ManifestBuildError(f"{field} must use UTC")
    return parsed.isoformat().replace("+00:00", "Z")


def build_manifest(directory: str | Path, metadata: dict[str, str]) -> dict:
    root = Path(directory)
    if root.is_symlink() or not root.is_dir():
        raise ManifestBuildError("evidence directory must be a real directory")
    target = root / "manifest.json"
    if target.exists() or target.is_symlink():
        raise ManifestBuildError("manifest.json already exists; refusing to overwrite")
    required_metadata = (
        "run_id", "operator", "approval_reference", "host_alias",
        "started_at_utc", "ended_at_utc", "runtime_name", "runtime_version",
        "collector_version", "signer_version", "test_image_digest", "proxy_policy_id",
    )
    if set(metadata) != set(required_metadata):
        raise ManifestBuildError("metadata fields are incomplete or contain unknown values")
    for key in required_metadata:
        if not isinstance(metadata[key], str) or not metadata[key].strip():
            raise ManifestBuildError(f"{key} must be a non-empty string")
    if not _DIGEST.fullmatch(metadata["test_image_digest"]):
        raise ManifestBuildError("test_image_digest must be an immutable sha256 digest")
    started = _utc(metadata["started_at_utc"], "started_at_utc")
    ended = _utc(metadata["ended_at_utc"], "ended_at_utc")
    if datetime.fromisoformat(ended.replace("Z", "+00:00")) < datetime.fromisoformat(started.replace("Z", "+00:00")):
        raise ManifestBuildError("ended_at_utc precedes started_at_utc")

    present = {p.name for p in root.iterdir()}
    expected = set(_REQUIRED)
    if present != expected:
        missing, extra = sorted(expected - present), sorted(present - expected)
        raise ManifestBuildError(f"artifact inventory mismatch; missing={missing}, extra={extra}")
    hashes: dict[str, str] = {}
    for name in _REQUIRED:
        path = root / name
        if path.is_symlink() or not path.is_file() or not stat.S_ISREG(path.stat().st_mode):
            raise ManifestBuildError(f"{name} must be a regular non-symlink file")
        raw = path.read_bytes()
        if len(raw) > 16 * 1024 * 1024:
            raise ManifestBuildError(f"{name} exceeds the 16 MiB limit")
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise ManifestBuildError(f"{name} must contain valid UTF-8 JSON") from exc
        if not isinstance(payload, dict):
            raise ManifestBuildError(f"{name} must contain a JSON object")
        hashes[name] = hashlib.sha256(raw).hexdigest()

    manifest = {
        "schema_version": 1,
        **{key: metadata[key] for key in required_metadata if key not in {"started_at_utc", "ended_at_utc"}},
        "started_at_utc": started,
        "ended_at_utc": ended,
        "files": hashes,
    }
    # Exclusive creation prevents accidental replacement if another process races us.
    encoded = (json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(target, flags, 0o600)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
    except Exception:
        try:
            target.unlink()
        except OSError:
            pass
        raise
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build (do not sign) an APAA P27 evidence manifest")
    parser.add_argument("evidence_directory", type=Path)
    for name in (
        "run-id", "operator", "approval-reference", "host-alias",
        "started-at-utc", "ended-at-utc", "runtime-name", "runtime-version",
        "collector-version", "signer-version", "test-image-digest", "proxy-policy-id",
    ):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args(argv)
    metadata = {
        "run_id": args.run_id, "operator": args.operator,
        "approval_reference": args.approval_reference, "host_alias": args.host_alias,
        "started_at_utc": args.started_at_utc, "ended_at_utc": args.ended_at_utc,
        "runtime_name": args.runtime_name, "runtime_version": args.runtime_version,
        "collector_version": args.collector_version, "signer_version": args.signer_version,
        "test_image_digest": args.test_image_digest, "proxy_policy_id": args.proxy_policy_id,
    }
    try:
        build_manifest(args.evidence_directory, metadata)
    except (ManifestBuildError, OSError) as exc:
        print(json.dumps({"created": False, "error": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps({
        "created": True, "integrity": "HASHES_RECORDED_NOT_YET_VERIFIED",
        "authenticity": "NOT_CHECKED", "host_qualification": "NOT_ASSESSED",
        "next": "run scripts.validate_apaa_p27_evidence, then sign manifest with the independently provisioned host key",
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
