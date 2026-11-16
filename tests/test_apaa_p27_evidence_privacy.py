import json
from pathlib import Path

import pytest

from scripts.check_apaa_p27_evidence_privacy import (
    PrivacyCheckError,
    check_evidence_privacy,
    main,
)

FILES = (
    "host-preflight.json", "identity.json", "trust.json", "lifecycle.json",
    "egress.json", "negative-tests.json", "failure-cleanup.json",
    "anchor-recovery.json", "review.json", "manifest.json",
)


def _pack(root: Path):
    root.mkdir()
    for name in FILES:
        (root / name).write_text(json.dumps({"result": "BLOCKED"}), encoding="utf-8")


def test_clean_pattern_scan_is_explicitly_not_a_privacy_guarantee(tmp_path):
    root = tmp_path / "evidence"
    _pack(root)
    result = check_evidence_privacy(root)
    assert result["result"] == "NO_KNOWN_PATTERN_MATCHES"
    assert result["assurance"] == "PATTERN_SCAN_ONLY_HUMAN_REVIEW_REQUIRED"
    assert result["files_scanned"] == 10


@pytest.mark.parametrize("payload,code", [
    ({"access_token": "placeholder"}, "SENSITIVE_FIELD_NAME"),
    ({"nested": [{"private_key": "redacted"}]}, "SENSITIVE_FIELD_NAME"),
    ({"log": "-----BEGIN PRIVATE KEY-----"}, "PEM_PRIVATE_KEY"),
    ({"header": "Bearer abcdefghijklmnop"}, "BEARER_CREDENTIAL"),
    ({"key": "AKIA1234567890ABCDEF"}, "AWS_ACCESS_KEY"),
    ({"value": "ghp_abcdefghijklmnopqrstuvwxyz123456"}, "GITHUB_TOKEN"),
])
def test_flags_common_secret_indicators(tmp_path, payload, code):
    root = tmp_path / "evidence"
    _pack(root)
    (root / "trust.json").write_text(json.dumps(payload), encoding="utf-8")
    result = check_evidence_privacy(root)
    assert result["result"] == "REVIEW_REQUIRED"
    assert code in {item["code"] for item in result["findings"]}


def test_refuses_symlinks_and_incomplete_inventory(tmp_path):
    root = tmp_path / "evidence"
    _pack(root)
    outside = tmp_path / "outside"
    outside.write_text("{}", encoding="utf-8")
    (root / "trust.json").unlink()
    (root / "trust.json").symlink_to(outside)
    with pytest.raises(PrivacyCheckError, match="regular non-symlink"):
        check_evidence_privacy(root)


def test_cli_exit_code_is_nonzero_on_findings(tmp_path, capsys):
    root = tmp_path / "evidence"
    _pack(root)
    (root / "identity.json").write_text(json.dumps({"password": "not-a-real-secret"}), encoding="utf-8")
    assert main([str(root)]) == 1
    output = json.loads(capsys.readouterr().out)
    assert output["finding_count"] == 1
