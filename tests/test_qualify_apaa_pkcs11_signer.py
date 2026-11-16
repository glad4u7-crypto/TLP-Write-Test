import json

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from scripts import qualify_apaa_pkcs11_signer as cli


class FakeSigner:
    key_id = "inspector:hardware-test"

    def public_key_bytes(self):
        return self._key.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw,
        )

    def __init__(self):
        self._key = Ed25519PrivateKey.generate()

    def sign(self, message):
        return self._key.sign(message)


def test_pkcs11_qualification_script_reports_self_test_not_hardware_attestation(monkeypatch, capsys):
    signer = FakeSigner()
    monkeypatch.setattr(cli.getpass, "getpass", lambda _prompt: "hidden-pin")
    monkeypatch.setattr(cli, "PKCS11Ed25519InspectorSigner", lambda **_kwargs: signer)
    assert cli.main(["--module", "/tmp/mock-pkcs11.so", "--token-label", "test", "--key-id", "test-001"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "TOKEN_SIGNER_SELF_TEST_PASS"
    assert result["token_hardware_identity"] == "NOT_INDEPENDENTLY_VERIFIED"
    assert result["backup_restore_qualification"] == "NOT_ASSESSED"
    assert "hidden-pin" not in json.dumps(result)


def test_pkcs11_qualification_script_fails_without_exposing_pin(monkeypatch, capsys):
    monkeypatch.setattr(cli.getpass, "getpass", lambda _prompt: "do-not-print-this")
    def fail(**_kwargs):
        raise cli.PKCS11SignerError("secret diagnostic")
    monkeypatch.setattr(cli, "PKCS11Ed25519InspectorSigner", fail)
    assert cli.main(["--module", "/tmp/mock-pkcs11.so", "--token-label", "test", "--key-id", "test-001"]) == 2
    output = capsys.readouterr()
    assert "do-not-print-this" not in output.out + output.err
    assert "secret diagnostic" not in output.err
