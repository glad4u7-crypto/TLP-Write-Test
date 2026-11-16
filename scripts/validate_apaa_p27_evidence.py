"""Validate an APAA S09 C01 P27 evidence directory.

This checks manifest structure, UTC timestamps, safe relative paths and SHA-256
integrity of every listed artifact. It does NOT verify the detached manifest
signature, host identity, signer custody, or whether observations are genuine.
Those checks require the independent reviewer and trusted evidence verifier.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_IMAGE_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_REQUIRED_TEXT = (
    "run_id", "operator", "approval_reference", "host_alias",
    "runtime_name", "runtime_version", "collector_version",
    "signer_version", "proxy_policy_id",
)
_REQUIRED_FILES = {
    "host-preflight.json", "identity.json", "trust.json", "lifecycle.json",
    "egress.json", "negative-tests.json", "failure-cleanup.json",
    "anchor-recovery.json", "review.json",
}


class EvidenceValidationError(ValueError):
    """Raised when a P27 evidence pack is incomplete or inconsistent."""


def _utc_timestamp(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise EvidenceValidationError(f"{field} must be a non-empty UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise EvidenceValidationError(f"{field} is not ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise EvidenceValidationError(f"{field} must use UTC (Z or +00:00)")
    return parsed


def _safe_relative_path(value: Any) -> PurePosixPath:
    if not isinstance(value, str) or not value or "\\" in value:
        raise EvidenceValidationError("artifact paths must be non-empty POSIX relative paths")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in ("", ".", "..") for part in path.parts):
        raise EvidenceValidationError("artifact path escapes the evidence directory")
    if path.as_posix() != value or value == "manifest.json":
        raise EvidenceValidationError("artifact path is non-canonical or names the manifest")
    return path


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_evidence_directory(directory: str | Path) -> dict[str, Any]:
    root = Path(directory)
    if root.is_symlink() or not root.is_dir():
        raise EvidenceValidationError("evidence directory must be a real directory")
    manifest_path = root / "manifest.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise EvidenceValidationError("manifest.json is missing or is not a regular file")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise EvidenceValidationError("manifest.json is unreadable or invalid JSON") from exc
    if not isinstance(manifest, dict):
        raise EvidenceValidationError("manifest must be a JSON object")
    if type(manifest.get("schema_version")) is not int or manifest["schema_version"] != 1:
        raise EvidenceValidationError("schema_version must equal integer 1")
    for field in _REQUIRED_TEXT:
        if not isinstance(manifest.get(field), str) or not manifest[field].strip():
            raise EvidenceValidationError(f"{field} must be a non-empty string")
    if not _IMAGE_DIGEST.fullmatch(str(manifest.get("test_image_digest", ""))):
        raise EvidenceValidationError("test_image_digest must be an immutable sha256 digest")

    started = _utc_timestamp(manifest.get("started_at_utc"), "started_at_utc")
    ended = _utc_timestamp(manifest.get("ended_at_utc"), "ended_at_utc")
    if ended < started:
        raise EvidenceValidationError("ended_at_utc precedes started_at_utc")

    files = manifest.get("files")
    if not isinstance(files, dict) or not files:
        raise EvidenceValidationError("files must map artifact paths to SHA-256 digests")
    normalized: dict[str, str] = {}
    for name, expected in files.items():
        rel = _safe_relative_path(name)
        if not isinstance(expected, str) or not _SHA256.fullmatch(expected):
            raise EvidenceValidationError(f"invalid SHA-256 digest for {name}")
        normalized[rel.as_posix()] = expected

    missing_required = sorted(_REQUIRED_FILES - set(normalized))
    if missing_required:
        raise EvidenceValidationError(
            "required evidence artifacts missing: " + ", ".join(missing_required)
        )

    actual: set[str] = set()
    for current, dirs, names in __import__("os").walk(root, followlinks=False):
        current_path = Path(current)
        for dirname in list(dirs):
            candidate = current_path / dirname
            if candidate.is_symlink():
                raise EvidenceValidationError("symlink directories are not allowed")
        for filename in names:
            candidate = current_path / filename
            relative = candidate.relative_to(root).as_posix()
            if relative == "manifest.json":
                continue
            if candidate.is_symlink() or not stat.S_ISREG(candidate.lstat().st_mode):
                raise EvidenceValidationError("only regular evidence files are allowed")
            actual.add(relative)

    if actual != set(normalized):
        missing = sorted(set(normalized) - actual)
        unlisted = sorted(actual - set(normalized))
        details = []
        if missing:
            details.append("missing: " + ", ".join(missing))
        if unlisted:
            details.append("unlisted: " + ", ".join(unlisted))
        raise EvidenceValidationError("artifact inventory mismatch (" + "; ".join(details) + ")")

    for name, expected in normalized.items():
        observed = _sha256_file(root.joinpath(*PurePosixPath(name).parts))
        if observed != expected:
            raise EvidenceValidationError(f"SHA-256 mismatch for {name}")

    return {
        "valid": True,
        "schema_version": 1,
        "run_id": manifest["run_id"],
        "artifact_count": len(normalized),
        "integrity": "PASS",
        "authenticity": "NOT_CHECKED",
        "host_qualification": "NOT_ASSESSED",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate an APAA P27 evidence pack")
    parser.add_argument("evidence_directory", type=Path)
    args = parser.parse_args(argv)
    try:
        result = validate_evidence_directory(args.evidence_directory)
    except EvidenceValidationError as exc:
        print(json.dumps({"valid": False, "error": str(exc)}, sort_keys=True))
        return 2
    except OSError:
        print(json.dumps({"valid": False, "error": "evidence I/O failed"}, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
