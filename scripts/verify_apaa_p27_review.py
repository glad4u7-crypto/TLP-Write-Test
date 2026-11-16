"""Verify an independent P27 review attestation against a signed evidence manifest.

The review attestation and reviewer key are detached from the evidence directory.
The verifier proves signatures and digest binding only; reviewer identity and
independence must be established out-of-band by the owner.
"""
from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from scripts.validate_apaa_p27_evidence import (
    EvidenceValidationError,
    validate_evidence_directory,
)

_FIELDS = {
    "schema_version", "reviewer_id", "reviewed_at_utc", "manifest_sha256",
    "reviewer_key_sha256", "disposition", "findings",
}
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class ReviewAttestationError(ValueError):
    """Raised when an independent P27 review attestation is invalid."""


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ReviewAttestationError("duplicate JSON object keys are not permitted")
        result[key] = value
    return result


def _canonical(value: object) -> bytes:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"),
            ensure_ascii=True, allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ReviewAttestationError("review attestation is not canonical JSON data") from exc


def _read_external_file(path: str | Path, evidence_root: Path, label: str) -> bytes:
    candidate = Path(path)
    if candidate.is_symlink() or not candidate.is_file():
        raise ReviewAttestationError(f"{label} must be a regular non-symlink file")
    try:
        candidate.resolve().relative_to(evidence_root.resolve())
    except ValueError:
        pass
    else:
        raise ReviewAttestationError(f"{label} must be stored outside the evidence directory")
    try:
        return candidate.read_bytes()
    except OSError as exc:
        raise ReviewAttestationError(f"{label} could not be read") from exc


def verify_review_attestation(
    evidence_directory: str | Path,
    *,
    manifest_signature_path: str | Path,
    manifest_public_key_path: str | Path,
    expected_manifest_key_sha256: str,
    review_attestation_path: str | Path,
    review_signature_path: str | Path,
    reviewer_public_key_path: str | Path,
    expected_reviewer_key_sha256: str,
) -> dict[str, Any]:
    root = Path(evidence_directory)
    # Check detached review material locations before walking the evidence tree.
    # This gives a clear fail-closed error even when a misplaced sidecar is unlisted.
    attestation_bytes = _read_external_file(
        review_attestation_path, root, "review attestation"
    )
    signature_bytes = _read_external_file(
        review_signature_path, root, "review signature"
    )
    reviewer_key = _read_external_file(
        reviewer_public_key_path, root, "reviewer public key"
    )
    try:
        evidence = validate_evidence_directory(
            root,
            signature_path=manifest_signature_path,
            public_key_path=manifest_public_key_path,
            expected_key_sha256=expected_manifest_key_sha256,
        )
    except EvidenceValidationError as exc:
        raise ReviewAttestationError(f"evidence manifest validation failed: {exc}") from exc
    if evidence["authenticity"] != "VERIFIED_ED25519":
        raise ReviewAttestationError("evidence manifest signature is not verified")

    manifest_bytes = (root / "manifest.json").read_bytes()
    manifest_digest = hashlib.sha256(manifest_bytes).hexdigest()
    if type(expected_reviewer_key_sha256) is not str or not _SHA256.fullmatch(expected_reviewer_key_sha256):
        raise ReviewAttestationError("pinned reviewer public-key fingerprint is invalid")
    if len(attestation_bytes) > 64 * 1024:
        raise ReviewAttestationError("review attestation exceeds 64 KiB")
    if len(reviewer_key) != 32 or hashlib.sha256(reviewer_key).hexdigest() != expected_reviewer_key_sha256:
        raise ReviewAttestationError("reviewer public key does not match the independently pinned fingerprint")
    try:
        signature_text = signature_bytes.decode("ascii").strip()
        signature = base64.b64decode(signature_text, validate=True)
    except (UnicodeError, ValueError, binascii.Error) as exc:
        raise ReviewAttestationError("review signature is not canonical base64") from exc
    if len(signature) != 64 or base64.b64encode(signature).decode("ascii") != signature_text:
        raise ReviewAttestationError("review signature has invalid length or encoding")

    try:
        attestation = json.loads(
            attestation_bytes.decode("utf-8"), object_pairs_hook=_unique_object
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ReviewAttestationError("review attestation is not valid UTF-8 JSON") from exc
    if not isinstance(attestation, dict) or set(attestation) != _FIELDS:
        raise ReviewAttestationError("review attestation has missing or unknown fields")
    if type(attestation["schema_version"]) is not int or attestation["schema_version"] != 1:
        raise ReviewAttestationError("unsupported review attestation schema")
    reviewer_id = attestation["reviewer_id"]
    if type(reviewer_id) is not str or not reviewer_id.strip() or len(reviewer_id) > 256:
        raise ReviewAttestationError("reviewer_id must be a non-empty bounded string")
    if attestation["manifest_sha256"] != manifest_digest:
        raise ReviewAttestationError("review attestation is not bound to this exact manifest")
    if attestation["reviewer_key_sha256"] != expected_reviewer_key_sha256:
        raise ReviewAttestationError("attestation reviewer fingerprint does not match pinned key")
    disposition = attestation["disposition"]
    if type(disposition) is not str or disposition not in {"PASS", "FAIL", "BLOCKED"}:
        raise ReviewAttestationError("review disposition must be PASS, FAIL or BLOCKED")
    findings = attestation["findings"]
    if not isinstance(findings, list) or len(findings) > 100 or any(
        type(item) is not str or not item.strip() or len(item) > 2000 for item in findings
    ):
        raise ReviewAttestationError("review findings must be a bounded list of non-empty strings")
    if disposition == "PASS" and findings:
        raise ReviewAttestationError("PASS disposition cannot contain unresolved findings")

    timestamp = attestation["reviewed_at_utc"]
    if type(timestamp) is not str:
        raise ReviewAttestationError("reviewed_at_utc must be a UTC timestamp")
    try:
        reviewed_at = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ReviewAttestationError("reviewed_at_utc is not ISO-8601") from exc
    if reviewed_at.tzinfo is None or reviewed_at.utcoffset() != timezone.utc.utcoffset(reviewed_at):
        raise ReviewAttestationError("reviewed_at_utc must use UTC")
    if reviewed_at.timestamp() > datetime.now(timezone.utc).timestamp() + 300:
        raise ReviewAttestationError("review timestamp is too far in the future")

    try:
        Ed25519PublicKey.from_public_bytes(reviewer_key).verify(
            signature, _canonical(attestation)
        )
    except (ValueError, InvalidSignature) as exc:
        raise ReviewAttestationError("independent review signature verification failed") from exc

    return {
        "valid": True,
        "manifest_sha256": manifest_digest,
        "manifest_authenticity": "VERIFIED_ED25519",
        "review_attestation": "VERIFIED_ED25519",
        "reviewer_id": reviewer_id,
        "reviewer_identity": "OUT_OF_BAND_IDENTITY_CHECK_REQUIRED",
        "reviewer_independence": "OUT_OF_BAND_INDEPENDENCE_CHECK_REQUIRED",
        "disposition": disposition,
        "findings_count": len(findings),
        "qualification_approval": "NOT_GRANTED_BY_CRYPTOGRAPHIC_VERIFICATION",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify a signed independent APAA P27 review")
    parser.add_argument("evidence_directory", type=Path)
    parser.add_argument("--manifest-signature", type=Path, required=True)
    parser.add_argument("--manifest-public-key", type=Path, required=True)
    parser.add_argument("--manifest-key-sha256", required=True)
    parser.add_argument("--review-attestation", type=Path, required=True)
    parser.add_argument("--review-signature", type=Path, required=True)
    parser.add_argument("--review-public-key", type=Path, required=True)
    parser.add_argument("--review-key-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        result = verify_review_attestation(
            args.evidence_directory,
            manifest_signature_path=args.manifest_signature,
            manifest_public_key_path=args.manifest_public_key,
            expected_manifest_key_sha256=args.manifest_key_sha256,
            review_attestation_path=args.review_attestation,
            review_signature_path=args.review_signature,
            reviewer_public_key_path=args.review_public_key,
            expected_reviewer_key_sha256=args.review_key_sha256,
        )
    except (ReviewAttestationError, OSError) as exc:
        print(json.dumps({"valid": False, "error": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
