"""Chunked authenticated encryption for portable APAA Personal Edition backups.

The format uses scrypt for passphrase-based key derivation and AES-256-GCM
per chunk. It avoids loading large Android backups into memory and authenticates
the header, chunk order, lengths and ciphertext. The caller owns private temp
files and must never log or persist the passphrase.
"""
from __future__ import annotations

import os
from pathlib import Path
import struct
import tempfile

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt


_MAGIC = b"APAAENC1"
_VERSION = 1
_CHUNK_SIZE = 1024 * 1024
_SALT_SIZE = 16
_NONCE_PREFIX_SIZE = 8
_TAG_SIZE = 16
_HEADER = struct.Struct(">8sB I 16s 8s")
_LENGTH = struct.Struct(">I")
_MAX_INPUT_BYTES = 512 * 1024 * 1024
_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1


class EncryptedBackupError(ValueError):
    """Raised when an encrypted APAA backup is invalid or cannot be processed."""


def _passphrase_bytes(passphrase: str) -> bytes:
    if not isinstance(passphrase, str) or len(passphrase) < 12 or len(passphrase) > 1024:
        raise EncryptedBackupError("Backup passphrase must contain 12–1024 characters.")
    try:
        encoded = passphrase.encode("utf-8", errors="strict")
    except UnicodeError as exc:
        raise EncryptedBackupError("Backup passphrase is invalid.") from exc
    if len(encoded) > 4096:
        raise EncryptedBackupError("Backup passphrase is too long.")
    return encoded


def _derive_key(passphrase: str, salt: bytes) -> bytes:
    return Scrypt(salt=salt, length=32, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P).derive(
        _passphrase_bytes(passphrase)
    )


def _private_regular_file(path: Path, *, label: str) -> os.stat_result:
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise EncryptedBackupError(f"{label} is unavailable.") from exc
    import stat
    if not stat.S_ISREG(metadata.st_mode) or path.is_symlink():
        raise EncryptedBackupError(f"{label} must be a regular non-symlink file.")
    if metadata.st_size <= 0 or metadata.st_size > _MAX_INPUT_BYTES:
        raise EncryptedBackupError(f"{label} size is outside the supported limit.")
    if os.name == "posix" and metadata.st_mode & 0o077:
        raise EncryptedBackupError(f"{label} must have owner-only permissions (0600).")
    return metadata


def encrypt_backup_file(source_path: str | Path, destination_path: str | Path, passphrase: str) -> Path:
    """Encrypt a private backup file atomically without buffering it all in RAM."""
    source = Path(source_path)
    destination = Path(destination_path)
    metadata = _private_regular_file(source, label="Backup source")
    if source.resolve() == destination.resolve(strict=False):
        raise EncryptedBackupError("Encrypted backup destination must differ from its source.")
    if destination.exists() or destination.is_symlink():
        raise EncryptedBackupError("Encrypted backup destination must not already exist.")
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name == "posix":
        os.chmod(destination.parent, 0o700)

    salt = os.urandom(_SALT_SIZE)
    nonce_prefix = os.urandom(_NONCE_PREFIX_SIZE)
    header = _HEADER.pack(_MAGIC, _VERSION, _CHUNK_SIZE, salt, nonce_prefix)
    cipher = AESGCM(_derive_key(passphrase, salt))
    fd, temporary_name = tempfile.mkstemp(prefix=".apaa-encrypt-", suffix=".tmp", dir=destination.parent)
    temporary = Path(temporary_name)
    os.fchmod(fd, 0o600)
    counter = 0
    total = 0
    try:
        with os.fdopen(fd, "wb") as output, source.open("rb") as input_stream:
            output.write(header)
            while True:
                chunk = input_stream.read(_CHUNK_SIZE)
                if not chunk:
                    break
                total += len(chunk)
                if total > _MAX_INPUT_BYTES or counter >= 2**32:
                    raise EncryptedBackupError("Backup exceeds the encryption format limits.")
                length = _LENGTH.pack(len(chunk))
                nonce = nonce_prefix + counter.to_bytes(4, "big")
                aad = header + counter.to_bytes(4, "big") + length
                output.write(length)
                output.write(cipher.encrypt(nonce, chunk, aad))
                counter += 1
            output.flush()
            os.fsync(output.fileno())
        if total != metadata.st_size:
            raise EncryptedBackupError("Backup source changed during encryption.")
        os.replace(temporary, destination)
        if os.name == "posix":
            os.chmod(destination, 0o600)
        return destination
    except Exception:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def decrypt_backup_file(source_path: str | Path, destination_path: str | Path, passphrase: str) -> Path:
    """Authenticate and decrypt an APAA backup to a new owner-only file."""
    source = Path(source_path)
    destination = Path(destination_path)
    _private_regular_file(source, label="Encrypted backup")
    if destination.exists() or destination.is_symlink():
        raise EncryptedBackupError("Decrypted backup destination must not already exist.")
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name == "posix":
        os.chmod(destination.parent, 0o700)

    fd, temporary_name = tempfile.mkstemp(prefix=".apaa-decrypt-", suffix=".tmp", dir=destination.parent)
    temporary = Path(temporary_name)
    os.fchmod(fd, 0o600)
    total = 0
    counter = 0
    try:
        with os.fdopen(fd, "wb") as output, source.open("rb") as input_stream:
            header = input_stream.read(_HEADER.size)
            if len(header) != _HEADER.size:
                raise EncryptedBackupError("Encrypted backup header is truncated.")
            magic, version, chunk_size, salt, nonce_prefix = _HEADER.unpack(header)
            if magic != _MAGIC or version != _VERSION or chunk_size != _CHUNK_SIZE:
                raise EncryptedBackupError("Encrypted backup format is unsupported.")
            cipher = AESGCM(_derive_key(passphrase, salt))
            while True:
                length_bytes = input_stream.read(_LENGTH.size)
                if not length_bytes:
                    break
                if len(length_bytes) != _LENGTH.size:
                    raise EncryptedBackupError("Encrypted backup chunk header is truncated.")
                (length,) = _LENGTH.unpack(length_bytes)
                if not 1 <= length <= _CHUNK_SIZE or counter >= 2**32:
                    raise EncryptedBackupError("Encrypted backup chunk length is invalid.")
                encrypted = input_stream.read(length + _TAG_SIZE)
                if len(encrypted) != length + _TAG_SIZE:
                    raise EncryptedBackupError("Encrypted backup chunk is truncated.")
                nonce = nonce_prefix + counter.to_bytes(4, "big")
                aad = header + counter.to_bytes(4, "big") + length_bytes
                try:
                    plaintext = cipher.decrypt(nonce, encrypted, aad)
                except Exception as exc:
                    raise EncryptedBackupError("Backup authentication failed; passphrase or data is invalid.") from exc
                total += len(plaintext)
                if total > _MAX_INPUT_BYTES:
                    raise EncryptedBackupError("Decrypted backup exceeds the supported size limit.")
                output.write(plaintext)
                counter += 1
                if length < _CHUNK_SIZE and input_stream.read(1):
                    raise EncryptedBackupError("Encrypted backup contains data after its final chunk.")
            if total == 0:
                raise EncryptedBackupError("Encrypted backup contains no data.")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, destination)
        if os.name == "posix":
            os.chmod(destination, 0o600)
        return destination
    except Exception:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise
