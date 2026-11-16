import json

from scripts import check_apaa_remote_anchor as cli
from core.offline_owner_recovery import AnchorState


class FakeAnchor:
    def __init__(self, **kwargs):
        assert kwargs["endpoint"].startswith("https://")
    def read(self):
        return AnchorState(4, "a" * 64, "owner-change-004")
    def read_sequence(self, issuer):
        assert issuer == "control:root-001"
        return 9


def test_remote_anchor_preflight_is_read_only_and_does_not_claim_qualification(monkeypatch, capsys):
    monkeypatch.setattr(cli, "HTTPSMonotonicAnchor", FakeAnchor)
    assert cli.main([
        "--endpoint", "https://anchor.example.test",
        "--ca-file", "/tmp/ca.pem", "--client-cert", "/tmp/client.pem",
        "--client-key", "/tmp/client.key", "--anchor-id", "owner:primary",
        "--issuer-id", "control:root-001",
    ]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "SERVICE_REACHABLE_SCHEMA_VALID"
    assert result["owner_anchor"]["revision"] == 4
    assert result["trust_bundle_sequence"] == 9
    assert result["write_test"] == "NOT_RUN"
    assert result["production_qualification"] == "NOT_QUALIFIED"


def test_remote_anchor_preflight_failure_is_sanitized(monkeypatch, capsys):
    def fail(**_kwargs):
        raise cli.RemoteAnchorError("secret transport detail")
    monkeypatch.setattr(cli, "HTTPSMonotonicAnchor", fail)
    assert cli.main([
        "--endpoint", "https://anchor.example.test",
        "--ca-file", "/tmp/ca.pem", "--client-cert", "/tmp/client.pem",
        "--client-key", "/tmp/client.key", "--anchor-id", "owner:primary",
        "--issuer-id", "control:root-001",
    ]) == 2
    output = capsys.readouterr()
    assert "secret transport detail" not in output.err
