"""Read-only privacy preflight for APAA P27 JSON evidence artifacts.

This is a conservative, pattern-based check for common credential/private-key
material. A clean result is NOT proof that evidence contains no sensitive data.
Human review and the approved restricted evidence store remain mandatory.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

_REQUIRED = (
    "host-preflight.json", "identity.json", "trust.json", "lifecycle.json",
    "egress.json", "negative-tests.json", "failure-cleanup.json",
    "anchor-recovery.json", "review.json",
)
_SENSITIVE_KEY = re.compile(
    r"(?:^|[_-])(password|passwd|secret|token|api[_-]?key|access[_-]?key|"
    r"private[_-]?key|client[_-]?secret|authorization|cookie|credential)(?:$|[_-])",
    re.IGNORECASE,
)
_PATTERNS = (
    ("PEM_PRIVATE_KEY", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("BEARER_CREDENTIAL", re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{12,}")),
    ("AWS_ACCESS_KEY", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("GITHUB_TOKEN", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
    ("PRIVATE_KEY_ASSIGNMENT", re.compile(r"(?i)\b(?:private[_-]?key|client[_-]?secret)\s*[:=]\s*\S+")),
)


class PrivacyCheckError(ValueError):
    """Raised when the evidence directory cannot be safely checked."""


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Reject duplicate JSON keys instead of silently hiding earlier values."""
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise PrivacyCheckError("duplicate JSON object keys are not permitted")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    """Reject NaN and Infinity, which are not valid JSON values."""
    raise PrivacyCheckError("non-standard JSON constants are not permitted")


def _walk(value: Any, path: str, findings: list[dict[str, str]]) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key)
            child_path = f"{path}.{key_text}"
            if _SENSITIVE_KEY.search(key_text):
                findings.append({"code": "SENSITIVE_FIELD_NAME", "path": child_path})
            _walk(child, child_path, findings)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _walk(child, f"{path}[{index}]", findings)
    elif isinstance(value, str):
        for code, pattern in _PATTERNS:
            if pattern.search(value):
                findings.append({"code": code, "path": path})


def check_evidence_privacy(directory: str | Path) -> dict[str, Any]:
    root = Path(directory)
    if root.is_symlink() or not root.is_dir():
        raise PrivacyCheckError("evidence directory must be a real directory")
    expected = set(_REQUIRED) | {"manifest.json"}
    present = {entry.name for entry in root.iterdir()}
    if present != expected:
        raise PrivacyCheckError("evidence directory must contain manifest and exactly nine required JSON artifacts")
    findings: list[dict[str, str]] = []
    for name in sorted(expected):
        path = root / name
        if path.is_symlink() or not path.is_file():
            raise PrivacyCheckError(f"{name} must be a regular non-symlink file")
        if path.stat().st_size > 16 * 1024 * 1024:
            raise PrivacyCheckError(f"{name} exceeds the 16 MiB scan limit")
        try:
            payload = json.loads(
                path.read_text(encoding="utf-8"),
                object_pairs_hook=_unique_object,
                parse_constant=_reject_constant,
            )
        except (OSError, UnicodeError, json.JSONDecodeError, RecursionError, ValueError) as exc:
            raise PrivacyCheckError(f"{name} must contain valid UTF-8 JSON") from exc
        _walk(payload, name, findings)
    # Deduplicate stable path/code pairs while retaining deterministic order.
    unique = sorted({(item["code"], item["path"]) for item in findings})
    return {
        "checked": True,
        "files_scanned": len(expected),
        "result": "REVIEW_REQUIRED" if unique else "NO_KNOWN_PATTERN_MATCHES",
        "finding_count": len(unique),
        "findings": [{"code": code, "path": path} for code, path in unique],
        "assurance": "PATTERN_SCAN_ONLY_HUMAN_REVIEW_REQUIRED",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only APAA P27 evidence privacy preflight")
    parser.add_argument("evidence_directory", type=Path)
    args = parser.parse_args(argv)
    try:
        result = check_evidence_privacy(args.evidence_directory)
    except PrivacyCheckError as exc:
        print(json.dumps({"checked": False, "error": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 1 if result["finding_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
