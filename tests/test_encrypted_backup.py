from __future__ import annotations

import os

import pytest

from core.encrypted_backup import (
    EncryptedBackupError,
    decrypt_backup_file,
    encrypt_backup_file,
)


def _private_dir(tmp_path):
    directory = tmp_path / "private"
    directory.mkdir(mode=0o700)
    if os.name == "posix":
        directory.chmod(0o700)
    return directory


def test_chunked_encrypted_backup_round_trip(tmp_path):
    directory = _private_dir(tmp_path)
    source = directory / "source.zip"
    payload = (b"APAA private backup data\x00" * 90000)  # More than one AEAD chunk.
    source.write_bytes(payload)
    source.chmod(0o600)
    encrypted = encrypt_backup_file(source, directory / "backup.apaa.enc", "a long private backup passphrase")
    assert encrypted.read_bytes()[:8] == b"APAAENC1"
    assert encrypted.stat().st_mode & 0o077 == 0

    restored = decrypt_backup_file(encrypted, directory / "restored.zip", "a long private backup passphrase")
    assert restored.read_bytes() == payload
    assert restored.stat().st_mode & 0o077 == 0


def test_wrong_passphrase_fails_without_creating_output(tmp_path):
    directory = _private_dir(tmp_path)
    source = directory / "source.zip"
    source.write_bytes(b"private archive contents")
    source.chmod(0o600)
    encrypted = encrypt_backup_file(source, directory / "backup.apaa.enc", "correct horse battery staple")
    destination = directory / "restored.zip"

    with pytest.raises(EncryptedBackupError, match="authentication failed"):
        decrypt_backup_file(encrypted, destination, "incorrect horse battery staple")
    assert not destination.exists()


def test_ciphertext_tampering_is_rejected(tmp_path):
    directory = _private_dir(tmp_path)
    source = directory / "source.zip"
    source.write_bytes(b"private archive contents")
    source.chmod(0o600)
    encrypted = encrypt_backup_file(source, directory / "backup.apaa.enc", "correct horse battery staple")
    data = bytearray(encrypted.read_bytes())
    data[-1] ^= 0x01
    encrypted.write_bytes(data)
    encrypted.chmod(0o600)

    with pytest.raises(EncryptedBackupError, match="authentication failed"):
        decrypt_backup_file(encrypted, directory / "restored.zip", "correct horse battery staple")


@pytest.mark.parametrize("passphrase", ["short", "", "x" * 1025, None])
def test_weak_or_invalid_passphrase_is_rejected(tmp_path, passphrase):
    directory = _private_dir(tmp_path)
    source = directory / "source.zip"
    source.write_bytes(b"data")
    source.chmod(0o600)
    with pytest.raises(EncryptedBackupError):
        encrypt_backup_file(source, directory / "backup.apaa.enc", passphrase)


def test_backup_sources_must_be_private_regular_files(tmp_path):
    directory = _private_dir(tmp_path)
    source = directory / "source.zip"
    source.write_bytes(b"private")
    source.chmod(0o644)
    with pytest.raises(EncryptedBackupError, match="owner-only"):
        encrypt_backup_file(source, directory / "backup.apaa.enc", "correct horse battery staple")


def test_destination_must_be_in_private_directory(tmp_path):
    source_dir = _private_dir(tmp_path)
    source = source_dir / "source.zip"
    source.write_bytes(b"private")
    source.chmod(0o600)
    public_dir = tmp_path / "public"
    public_dir.mkdir(mode=0o755)
    with pytest.raises(EncryptedBackupError, match="private"):
        encrypt_backup_file(source, public_dir / "backup.apaa.enc", "correct horse battery staple")
