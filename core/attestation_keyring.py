"""Owner-local Ed25519 attestation key lifecycle.

This is a permission-hardened file keyring for single-host development and
controlled deployments. It is NOT an HSM, TPM, remote signer, or out-of-band
identity authority. Production hosts must protect the directory with OS-level
ownership, backups and independent key custody.
"""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import re
import secrets
import stat
import tempfile
import time
from typing import Mapping

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


class AttestationKeyringError(RuntimeError):
    """The signing-key store is invalid or cannot be safely updated."""


_KEY_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{2,127}$")
_SCHEMA = 1


class FileEd25519Keyring:
    """Private local key storage with explicit activation, rotation and revocation."""

    def __init__(self, directory: str | os.PathLike[str]):
        path = Path(directory)
        if not path.is_absolute() or path == Path("/") or ".." in path.parts:
            raise ValueError("keyring directory must be an absolute normalized path")
        if path.is_symlink() or not path.is_dir():
            raise ValueError("keyring directory must be an existing non-symlink directory")
        info = path.stat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid():
            raise ValueError("keyring directory must be owned by the current OS user")
        if stat.S_IMODE(info.st_mode) & 0o077:
            raise ValueError("keyring directory permissions must be owner-only (0700)")
        self.directory = path
        self._metadata_path = path / "keyring.json"

    @staticmethod
    def _private_bytes(key: Ed25519PrivateKey) -> bytes:
        return key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption(),
        )

    @staticmethod
    def _public_bytes(key: Ed25519PrivateKey) -> bytes:
        return key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )

    def _load(self) -> dict:
        if self._metadata_path.is_symlink():
            raise AttestationKeyringError("keyring metadata must not be a symlink")
        try:
            info = self._metadata_path.stat()
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) & 0o077:
                raise AttestationKeyringError("keyring metadata permissions or ownership are unsafe")
            raw = json.loads(self._metadata_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {"schema_version": _SCHEMA, "active_key_id": None, "keys": {}}
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise AttestationKeyringError("keyring metadata is unreadable or malformed") from exc
        if (not isinstance(raw, dict) or set(raw) != {"schema_version", "active_key_id", "keys"}
                or type(raw["schema_version"]) is not int or raw["schema_version"] != _SCHEMA
                or not isinstance(raw["keys"], dict)):
            raise AttestationKeyringError("keyring metadata schema is invalid")
        active = raw["active_key_id"]
        if active is not None and (type(active) is not str or active not in raw["keys"]):
            raise AttestationKeyringError("active key reference is invalid")
        for key_id, item in raw["keys"].items():
            if (type(key_id) is not str or not _KEY_ID.fullmatch(key_id)
                    or not isinstance(item, dict) or set(item) != {"public_key", "status", "created_at"}
                    or item["status"] not in {"active", "retired", "revoked"}
                    or type(item["created_at"]) is not int or item["created_at"] < 0):
                raise AttestationKeyringError("keyring entry is malformed")
            try:
                public = base64.b64decode(item["public_key"], validate=True)
            except (ValueError, TypeError) as exc:
                raise AttestationKeyringError("keyring public key encoding is invalid") from exc
            if len(public) != 32:
                raise AttestationKeyringError("keyring public key length is invalid")
        active_entries = [key for key, item in raw["keys"].items() if item["status"] == "active"]
        if (active is None and active_entries) or (active is not None and active_entries != [active]):
            raise AttestationKeyringError("keyring must contain exactly its declared active key")
        return raw

    def _atomic_write(self, path: Path, data: bytes) -> None:
        fd, temporary = tempfile.mkstemp(prefix=".apaa-key-", dir=self.directory)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "wb", closefd=True) as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
            directory_fd = os.open(self.directory, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except Exception:
            try:
                os.unlink(temporary)
            except OSError:
                pass
            raise

    def _write(self, metadata: dict) -> None:
        encoded = json.dumps(metadata, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        self._atomic_write(self._metadata_path, encoded)

    def create_initial(self, key_id: str) -> bytes:
        if type(key_id) is not str or not _KEY_ID.fullmatch(key_id):
            raise ValueError("key ID is invalid")
        metadata = self._load()
        if metadata["keys"]:
            raise AttestationKeyringError("initial key creation is allowed only for an empty keyring")
        key = Ed25519PrivateKey.generate()
        private_path = self.directory / (key_id + ".ed25519")
        if private_path.exists() or private_path.is_symlink():
            raise AttestationKeyringError("private key path already exists")
        self._atomic_write(private_path, self._private_bytes(key))
        metadata["active_key_id"] = key_id
        metadata["keys"][key_id] = {
            "public_key": base64.b64encode(self._public_bytes(key)).decode("ascii"),
            "status": "active",
            "created_at": int(time.time()),
        }
        try:
            self._write(metadata)
        except Exception:
            private_path.unlink(missing_ok=True)
            raise
        return self._public_bytes(key)

    def rotate(self, new_key_id: str) -> bytes:
        if type(new_key_id) is not str or not _KEY_ID.fullmatch(new_key_id):
            raise ValueError("key ID is invalid")
        metadata = self._load()
        if metadata["active_key_id"] is None:
            raise AttestationKeyringError("an active key is required before rotation")
        if new_key_id in metadata["keys"] or (self.directory / (new_key_id + ".ed25519")).exists():
            raise AttestationKeyringError("rotation key ID already exists")
        key = Ed25519PrivateKey.generate()
        private_path = self.directory / (new_key_id + ".ed25519")
        self._atomic_write(private_path, self._private_bytes(key))
        old = metadata["active_key_id"]
        metadata["keys"][old]["status"] = "retired"
        metadata["keys"][new_key_id] = {
            "public_key": base64.b64encode(self._public_bytes(key)).decode("ascii"),
            "status": "active",
            "created_at": int(time.time()),
        }
        metadata["active_key_id"] = new_key_id
        try:
            self._write(metadata)
        except Exception:
            private_path.unlink(missing_ok=True)
            raise
        return self._public_bytes(key)

    def revoke(self, key_id: str) -> None:
        metadata = self._load()
        if key_id not in metadata["keys"]:
            raise AttestationKeyringError("unknown key ID")
        if metadata["active_key_id"] == key_id:
            raise AttestationKeyringError("rotate to a replacement key before revoking the active key")
        if metadata["keys"][key_id]["status"] == "revoked":
            return
        metadata["keys"][key_id]["status"] = "revoked"
        self._write(metadata)

    def signing_key(self, key_id: str | None = None) -> Ed25519PrivateKey:
        metadata = self._load()
        selected = metadata["active_key_id"] if key_id is None else key_id
        if selected not in metadata["keys"] or metadata["keys"][selected]["status"] != "active":
            raise AttestationKeyringError("requested signing key is not active")
        path = self.directory / (selected + ".ed25519")
        if path.is_symlink():
            raise AttestationKeyringError("private key must not be a symlink")
        try:
            info = path.stat()
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                    or stat.S_IMODE(info.st_mode) & 0o077 or info.st_size != 32):
                raise AttestationKeyringError("private key file permissions or ownership are unsafe")
            key = Ed25519PrivateKey.from_private_bytes(path.read_bytes())
        except OSError as exc:
            raise AttestationKeyringError("private signing key is unavailable") from exc
        expected = base64.b64decode(metadata["keys"][selected]["public_key"], validate=True)
        if self._public_bytes(key) != expected:
            raise AttestationKeyringError("private and public signing key material do not match")
        return key

    def trusted_public_keys(self) -> Mapping[str, bytes]:
        metadata = self._load()
        result = {}
        for key_id, item in metadata["keys"].items():
            if item["status"] != "revoked":
                result[key_id] = base64.b64decode(item["public_key"], validate=True)
        return result

    def status(self) -> dict:
        metadata = self._load()
        return {
            "active_key_id": metadata["active_key_id"],
            "keys": {key_id: item["status"] for key_id, item in metadata["keys"].items()},
        }
