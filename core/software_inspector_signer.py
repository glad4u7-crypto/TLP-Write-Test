"""Encrypted-at-rest software Ed25519 signer for local development only.

This provider implements InspectorSigningProvider without an export API.
It is NOT a TPM/HSM or equivalent hardware security boundary: the unlocked
private key exists in this process's memory and the passphrase is user-held.
Production host signing must use a separately reviewed protected signer.
"""
from __future__ import annotations

import base64
import binascii
import json
import os
from pathlib import Path
import re
import stat
from typing import Final

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

_SCHEMA: Final = 1
_SCRYPT_N: Final = 1 << 15
_SCRYPT_R: Final = 8
_SCRYPT_P: Final = 1
_MAX_FILE_BYTES: Final = 16_384
_MAX_MESSAGE_BYTES: Final = 1_048_576
_KEY_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{2,127}$")
_FIELDS = frozenset({"schema", "key_id", "kdf", "salt", "nonce", "ciphertext"})


class SoftwareSignerError(RuntimeError):
    """The software signer could not safely initialize, unlock or sign."""


def _passphrase_bytes(passphrase: str | bytes) -> bytes:
    if type(passphrase) is str:
        raw = passphrase.encode("utf-8")
    elif type(passphrase) is bytes:
        raw = passphrase
    else:
        raise TypeError("Passphrase must be supplied as text or bytes.")
    if len(raw) < 12 or len(raw) > 1024:
        raise SoftwareSignerError("Passphrase must contain 12 to 1024 UTF-8 bytes.")
    return raw


def _derive(passphrase: bytes, salt: bytes) -> bytes:
    return Scrypt(salt=salt, length=32, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P).derive(passphrase)


def _aad(key_id: str) -> bytes:
    return json.dumps(
        {"schema": _SCHEMA, "key_id": key_id, "kdf": "scrypt-32768-8-1"},
        sort_keys=True, separators=(",", ":"),
    ).encode("ascii")


def _safe_parent(path: Path) -> None:
    if not path.is_absolute() or not path.parent.is_dir() or path.parent.is_symlink():
        raise SoftwareSignerError("Signer path must be absolute with an existing non-symlink parent.")


def _check_stat(info: os.stat_result) -> None:
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise SoftwareSignerError("Signer file must be a single-link regular file.")
    if os.name == "posix" and stat.S_IMODE(info.st_mode) & 0o077:
        raise SoftwareSignerError("Signer file permissions must be private (0600 or stricter).")
    if info.st_size <= 0 or info.st_size > _MAX_FILE_BYTES:
        raise SoftwareSignerError("Signer file size is invalid.")


def _read_file(path: Path) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
        with os.fdopen(fd, "rb") as stream:
            _check_stat(os.fstat(stream.fileno()))
            raw = stream.read(_MAX_FILE_BYTES + 1)
    except OSError:
        raise SoftwareSignerError("Signer file is unavailable or unsafe.") from None
    if len(raw) > _MAX_FILE_BYTES:
        raise SoftwareSignerError("Signer file exceeds the size limit.")
    return raw


class EncryptedSoftwareEd25519Signer:
    """Local encrypted signer implementing the collector's sign/public-key API.

    Use create_new() once, then open_existing() on subsequent runs. There is
    deliberately no private-key export method. This is defense-in-depth for
    local development, not protection against a compromised/unlocked process,
    root, memory inspection, keylogger or passphrase theft.
    """

    def __init__(self, key_id: str, private_key: Ed25519PrivateKey) -> None:
        self._key_id = key_id
        self._private_key = private_key

    @property
    def key_id(self) -> str:
        return self._key_id

    @classmethod
    def create_new(
        cls, path: str | os.PathLike[str], *, key_id: str,
        passphrase: str | bytes,
    ) -> "EncryptedSoftwareEd25519Signer":
        if type(key_id) is not str or not _KEY_ID.fullmatch(key_id):
            raise SoftwareSignerError("Signer key ID is invalid.")
        secret = _passphrase_bytes(passphrase)
        target = Path(path).expanduser()
        _safe_parent(target)
        salt, nonce = os.urandom(16), os.urandom(12)
        private_key = Ed25519PrivateKey.generate()
        private_raw = private_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption(),
        )
        ciphertext = AESGCM(_derive(secret, salt)).encrypt(nonce, private_raw, _aad(key_id))
        envelope = {
            "schema": _SCHEMA, "key_id": key_id, "kdf": "scrypt-32768-8-1",
            "salt": base64.b64encode(salt).decode("ascii"),
            "nonce": base64.b64encode(nonce).decode("ascii"),
            "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
        }
        raw = json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode("ascii")
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        try:
            fd = os.open(target, flags, 0o600)
        except FileExistsError:
            raise SoftwareSignerError("Signer file already exists; refusing to overwrite or rotate it.") from None
        except OSError:
            raise SoftwareSignerError("Could not safely create signer file.") from None
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            if os.name == "posix":
                os.chmod(target, 0o600)
                dir_fd = os.open(target.parent, os.O_RDONLY)
                try:
                    os.fsync(dir_fd)
                finally:
                    os.close(dir_fd)
        except Exception:
            # Preserve any partially created file for explicit operator recovery;
            # never silently replace it on a subsequent invocation.
            raise SoftwareSignerError("Signer creation did not complete; inspect the file before retrying.") from None
        return cls(key_id, private_key)

    @classmethod
    def open_existing(
        cls, path: str | os.PathLike[str], *, passphrase: str | bytes,
    ) -> "EncryptedSoftwareEd25519Signer":
        secret = _passphrase_bytes(passphrase)
        target = Path(path).expanduser()
        _safe_parent(target)
        raw = _read_file(target)
        try:
            envelope = json.loads(raw.decode("ascii"))
            if not isinstance(envelope, dict) or set(envelope) != _FIELDS:
                raise ValueError("schema")
            key_id = envelope["key_id"]
            if (type(envelope["schema"]) is not int or envelope["schema"] != _SCHEMA
                    or type(key_id) is not str or not _KEY_ID.fullmatch(key_id)
                    or envelope["kdf"] != "scrypt-32768-8-1"):
                raise ValueError("metadata")
            salt = base64.b64decode(envelope["salt"], validate=True)
            nonce = base64.b64decode(envelope["nonce"], validate=True)
            ciphertext = base64.b64decode(envelope["ciphertext"], validate=True)
            if len(salt) != 16 or len(nonce) != 12 or len(ciphertext) != 48:
                raise ValueError("length")
            private_raw = AESGCM(_derive(secret, salt)).decrypt(
                nonce, ciphertext, _aad(key_id),
            )
            if len(private_raw) != 32:
                raise ValueError("private key length")
            private_key = Ed25519PrivateKey.from_private_bytes(private_raw)
        except (UnicodeError, json.JSONDecodeError, ValueError, TypeError, KeyError,
                binascii.Error, InvalidTag):
            raise SoftwareSignerError("Signer file is malformed or passphrase is incorrect.") from None
        return cls(key_id, private_key)

    def public_key_bytes(self) -> bytes:
        return self._private_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )

    def sign(self, message: bytes) -> bytes:
        if type(message) is not bytes or not 1 <= len(message) <= _MAX_MESSAGE_BYTES:
            raise SoftwareSignerError("Signing input must be 1 to 1048576 bytes.")
        try:
            return self._private_key.sign(message)
        except Exception:
            raise SoftwareSignerError("Signing operation failed closed.") from None
