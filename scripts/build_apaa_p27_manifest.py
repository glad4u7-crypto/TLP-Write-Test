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
import secrets
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path

# Capture interpreter filesystem capabilities before tests or callers can wrap
# os.open/os.link. Runtime monkeypatching must not change the platform contract.
_OPEN_SUPPORTS_DIR_FD = os.open in os.supports_dir_fd
_LINK_SUPPORTS_DIR_FD = os.link in os.supports_dir_fd

_REQUIRED = (
    "host-preflight.json", "identity.json", "trust.json", "lifecycle.json",
    "egress.json", "negative-tests.json", "failure-cleanup.json",
    "anchor-recovery.json", "review.json",
)
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_MAX_ARTIFACT_BYTES = 16 * 1024 * 1024
_STAGING_NAME = re.compile(r"^\.manifest-[0-9a-f]{32}\.tmp$")


def _cleanup_staging_files(root_fd: int) -> None:
    """Remove only reserved manifest staging names without following entries."""
    removed = False
    for name in os.listdir(root_fd):
        if _STAGING_NAME.fullmatch(name):
            try:
                os.unlink(name, dir_fd=root_fd)
                removed = True
            except FileNotFoundError:
                pass
    if removed:
        os.fsync(root_fd)


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


def _open_evidence_directory(root: Path) -> int:
    """Open the directory itself without following a final-component symlink."""
    required = ("O_NOFOLLOW", "O_DIRECTORY")
    if any(not hasattr(os, flag) for flag in required) or not _OPEN_SUPPORTS_DIR_FD:
        raise ManifestBuildError("platform lacks safe directory-relative no-follow file access")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    try:
        fd = os.open(root, flags)
    except OSError as exc:
        raise ManifestBuildError("evidence directory cannot be opened safely") from exc
    if not stat.S_ISDIR(os.fstat(fd).st_mode):
        os.close(fd)
        raise ManifestBuildError("evidence directory must be a real directory")
    return fd


def _read_artifact(root_fd: int, name: str) -> bytes:
    """Read one flat artifact through a no-follow descriptor and detect concurrent writes."""
    flags = os.O_RDONLY | os.O_NOFOLLOW
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    try:
        fd = os.open(name, flags, dir_fd=root_fd)
    except OSError as exc:
        raise ManifestBuildError(f"{name} cannot be opened as a regular non-symlink file") from exc
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise ManifestBuildError(f"{name} must be a singly-linked regular file")
        if before.st_size > _MAX_ARTIFACT_BYTES:
            raise ManifestBuildError(f"{name} exceeds the 16 MiB limit")
        raw = stream.read(_MAX_ARTIFACT_BYTES + 1)
        after = os.fstat(stream.fileno())
        stable_before = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
        stable_after = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)
        if stable_before != stable_after or len(raw) != after.st_size:
            raise ManifestBuildError(f"{name} changed while being read")
        if len(raw) > _MAX_ARTIFACT_BYTES:
            raise ManifestBuildError(f"{name} exceeds the 16 MiB limit")
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise ManifestBuildError(f"{name} must contain valid UTF-8 JSON") from exc
        if not isinstance(payload, dict):
            raise ManifestBuildError(f"{name} must contain a JSON object")
        return raw


def build_manifest(directory: str | Path, metadata: dict[str, str]) -> dict:
    root = Path(directory)
    if root.is_symlink() or not root.is_dir():
        raise ManifestBuildError("evidence directory must be a real directory")
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

    root_fd = _open_evidence_directory(root)
    try:
        try:
            os.stat("manifest.json", dir_fd=root_fd, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            # A prior process may have crashed after publication but before its
            # staging-file cleanup. The final manifest is immutable; remove only
            # reserved staging names, then refuse replacement.
            _cleanup_staging_files(root_fd)
            raise ManifestBuildError("manifest.json already exists; refusing to overwrite")

        present = {name for name in os.listdir(root_fd) if not _STAGING_NAME.fullmatch(name)}
        expected = set(_REQUIRED)
        if present != expected:
            missing, extra = sorted(expected - present), sorted(present - expected)
            raise ManifestBuildError(f"artifact inventory mismatch; missing={missing}, extra={extra}")

        hashes: dict[str, str] = {}
        for name in _REQUIRED:
            raw = _read_artifact(root_fd, name)
            hashes[name] = hashlib.sha256(raw).hexdigest()

        manifest = {
            "schema_version": 1,
            **{key: metadata[key] for key in required_metadata if key not in {"started_at_utc", "ended_at_utc"}},
            "started_at_utc": started,
            "ended_at_utc": ended,
            "files": hashes,
        }
        encoded = (json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
        # Write to a unique private staging inode first. Publishing with link()
        # makes the complete, fsynced bytes visible in one atomic no-overwrite step;
        # O_EXCL on the final path alone would expose a partially-written manifest.
        if not _LINK_SUPPORTS_DIR_FD:
            raise ManifestBuildError("platform lacks atomic directory-relative manifest publication")
        temp_name = f".manifest-{secrets.token_hex(16)}.tmp"
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
        if hasattr(os, "O_CLOEXEC"):
            flags |= os.O_CLOEXEC
        try:
            fd = os.open(temp_name, flags, 0o600, dir_fd=root_fd)
            with os.fdopen(fd, "wb") as stream:
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
            try:
                os.link(
                    temp_name, "manifest.json",
                    src_dir_fd=root_fd, dst_dir_fd=root_fd,
                    follow_symlinks=False,
                )
            except FileExistsError as exc:
                raise ManifestBuildError("manifest.json already exists; refusing to overwrite") from exc
            os.fsync(root_fd)
            # Once this complete manifest wins publication, reserved staging
            # names are disposable; a live losing builder will fail its link safely.
            _cleanup_staging_files(root_fd)
        finally:
            try:
                os.unlink(temp_name, dir_fd=root_fd)
                os.fsync(root_fd)
            except FileNotFoundError:
                pass
        return manifest
    finally:
        os.close(root_fd)


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
