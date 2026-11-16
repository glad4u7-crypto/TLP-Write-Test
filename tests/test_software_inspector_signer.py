import os
import stat

import pytest
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from core.software_inspector_signer import (
    EncryptedSoftwareEd25519Signer,
    SoftwareSignerError,
)


def test_create_unlock_and_sign_without_export_api(tmp_path):
    path = tmp_path / "inspector.key"
    signer = EncryptedSoftwareEd25519Signer.create_new(
        path, key_id="inspector:dev-001", passphrase="a sufficiently long passphrase",
    )
    assert signer.key_id == "inspector:dev-001"
    assert len(signer.public_key_bytes()) == 32
    assert len(signer.sign(b"APAA test evidence")) == 64
    assert not hasattr(signer, "private_key_bytes")
    reopened = EncryptedSoftwareEd25519Signer.open_existing(
        path, passphrase="a sufficiently long passphrase",
    )
    signature = reopened.sign(b"stable key after restart")
    Ed25519PublicKey.from_public_bytes(reopened.public_key_bytes()).verify(
        signature, b"stable key after restart",
    )
    assert reopened.public_key_bytes() == signer.public_key_bytes()


def test_wrong_passphrase_and_tampering_fail_closed(tmp_path):
    path = tmp_path / "inspector.key"
    EncryptedSoftwareEd25519Signer.create_new(
        path, key_id="inspector:dev-002", passphrase="correct horse battery staple",
    )
    with pytest.raises(SoftwareSignerError, match="malformed or passphrase"):
        EncryptedSoftwareEd25519Signer.open_existing(
            path, passphrase="incorrect horse battery staple",
        )
    raw = bytearray(path.read_bytes())
    raw[-3] = ord("A") if raw[-3] != ord("A") else ord("B")
    path.write_bytes(raw)
    os.chmod(path, 0o600)
    with pytest.raises(SoftwareSignerError):
        EncryptedSoftwareEd25519Signer.open_existing(
            path, passphrase="correct horse battery staple",
        )


def test_private_file_permissions_and_symlink_are_enforced(tmp_path):
    path = tmp_path / "inspector.key"
    EncryptedSoftwareEd25519Signer.create_new(
        path, key_id="inspector:dev-003", passphrase="another sufficiently long passphrase",
    )
    if os.name == "posix":
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
        os.chmod(path, 0o644)
        with pytest.raises(SoftwareSignerError, match="permissions"):
            EncryptedSoftwareEd25519Signer.open_existing(
                path, passphrase="another sufficiently long passphrase",
            )
        os.chmod(path, 0o600)
    link = tmp_path / "link.key"
    link.symlink_to(path)
    with pytest.raises(SoftwareSignerError):
        EncryptedSoftwareEd25519Signer.open_existing(
            link, passphrase="another sufficiently long passphrase",
        )


def test_existing_file_is_never_overwritten(tmp_path):
    path = tmp_path / "inspector.key"
    first = EncryptedSoftwareEd25519Signer.create_new(
        path, key_id="inspector:dev-004", passphrase="yet another sufficiently long passphrase",
    )
    original = path.read_bytes()
    with pytest.raises(SoftwareSignerError, match="already exists"):
        EncryptedSoftwareEd25519Signer.create_new(
            path, key_id="inspector:dev-005", passphrase="yet another sufficiently long passphrase",
        )
    assert path.read_bytes() == original
    assert first.key_id == "inspector:dev-004"


@pytest.mark.parametrize("key_id,passphrase", [
    ("x", "a sufficiently long passphrase"),
    ("inspector:dev-006", "short"),
])
def test_invalid_identity_or_short_passphrase_rejected(tmp_path, key_id, passphrase):
    with pytest.raises(SoftwareSignerError):
        EncryptedSoftwareEd25519Signer.create_new(
            tmp_path / "bad.key", key_id=key_id, passphrase=passphrase,
        )


def test_signing_input_is_bounded(tmp_path):
    signer = EncryptedSoftwareEd25519Signer.create_new(
        tmp_path / "inspector.key", key_id="inspector:dev-007",
        passphrase="long enough passphrase for signer",
    )
    for value in (b"", "text", b"x" * 1_048_577):
        with pytest.raises(SoftwareSignerError):
            signer.sign(value)
