import os
import stat

import pytest

from core.attestation_keyring import AttestationKeyringError, FileEd25519Keyring


def make_keyring(tmp_path):
    directory = tmp_path / "keys"
    directory.mkdir(mode=0o700)
    os.chmod(directory, 0o700)
    return FileEd25519Keyring(directory), directory


def test_initial_key_creation_and_private_permissions(tmp_path):
    ring, directory = make_keyring(tmp_path)
    public = ring.create_initial("host-key-001")
    key = ring.signing_key()
    assert key.public_key().public_bytes_raw() == public
    assert ring.trusted_public_keys() == {"host-key-001": public}
    assert stat.S_IMODE((directory / "host-key-001.ed25519").stat().st_mode) == 0o600
    assert stat.S_IMODE((directory / "keyring.json").stat().st_mode) == 0o600


def test_rotation_keeps_retired_public_key_trusted_but_not_signable(tmp_path):
    ring, _ = make_keyring(tmp_path)
    old_public = ring.create_initial("host-key-001")
    new_public = ring.rotate("host-key-002")
    assert ring.status() == {
        "active_key_id": "host-key-002",
        "keys": {"host-key-001": "retired", "host-key-002": "active"},
    }
    assert ring.signing_key().public_key().public_bytes_raw() == new_public
    assert ring.trusted_public_keys() == {
        "host-key-001": old_public, "host-key-002": new_public,
    }
    with pytest.raises(AttestationKeyringError, match="not active"):
        ring.signing_key("host-key-001")


def test_revocation_removes_public_key_from_trust_set(tmp_path):
    ring, directory = make_keyring(tmp_path)
    old_public = ring.create_initial("host-key-001")
    new_public = ring.rotate("host-key-002")
    ring.revoke("host-key-001")
    assert not (directory / "host-key-001.ed25519").exists()
    assert ring.trusted_public_keys() == {"host-key-002": new_public}
    assert ring.status()["keys"]["host-key-001"] == "revoked"


def test_active_key_cannot_be_revoked_before_rotation(tmp_path):
    ring, _ = make_keyring(tmp_path)
    ring.create_initial("host-key-001")
    with pytest.raises(AttestationKeyringError, match="replacement key"):
        ring.revoke("host-key-001")


def test_keyring_rejects_world_readable_directory(tmp_path):
    directory = tmp_path / "unsafe"
    directory.mkdir(mode=0o700)
    os.chmod(directory, 0o755)
    with pytest.raises(ValueError, match="owner-only"):
        FileEd25519Keyring(directory)


def test_keyring_rejects_symlink_private_key(tmp_path):
    ring, directory = make_keyring(tmp_path)
    ring.create_initial("host-key-001")
    real = directory / "host-key-001.ed25519"
    moved = directory / "host-key-001.backup"
    real.rename(moved)
    real.symlink_to(moved)
    with pytest.raises(AttestationKeyringError, match="symlink"):
        ring.signing_key()


def test_keyring_rejects_private_public_key_mismatch(tmp_path):
    ring, directory = make_keyring(tmp_path)
    ring.create_initial("host-key-001")
    path = directory / "host-key-001.ed25519"
    path.write_bytes(b"x" * 32)
    os.chmod(path, 0o600)
    with pytest.raises(AttestationKeyringError, match="do not match"):
        ring.signing_key()
