"""PKCS#11-backed Ed25519 inspector signer.

This adapter keeps private-key objects inside a PKCS#11 token and asks the
provider to sign. It requires a token/HSM that explicitly supports Ed25519
(CK_KEY_TYPE_EC_EDWARDS and CKM_EDDSA). It never creates or exports private
key material. A software token is useful for integration tests but is NOT
hardware protection; production qualification requires a physical protected
token, independently administered PIN custody and review.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
from typing import Callable

_KEY_ID = re.compile(r"^[A-Za-z0-9_.:-]{1,64}$")
_MAX_MESSAGE_BYTES = 1_048_576
_ED25519_OID = bytes.fromhex("06032b6570")


class PKCS11SignerError(RuntimeError):
    """PKCS#11 signer unavailable, misconfigured or rejected a request."""


def _der_octet_string(raw: bytes) -> bytes:
    # PKCS#11 EC_POINT is normally a DER OCTET STRING wrapping the point.
    if type(raw) is not bytes:
        raise PKCS11SignerError("PKCS#11 EC point attribute is not bytes.")
    if len(raw) == 32:
        return raw
    if len(raw) == 34 and raw[:2] == b"\x04\x20":
        return raw[2:]
    if len(raw) == 36 and raw[:4] == b"\x04\x22\x04\x20":
        return raw[4:]
    raise PKCS11SignerError("PKCS#11 Ed25519 public point has an unsupported DER encoding.")


class PKCS11Ed25519InspectorSigner:
    """Implements InspectorSigningProvider using a non-exportable PKCS#11 key.

    PINs are supplied explicitly by the caller, never read from environment or
    command-line arguments, and are not written to disk/logs. The provider
    object stores the PIN only for the lifetime of this Python object. For
    higher assurance, construct it per operation from a protected PIN broker.
    """

    def __init__(
        self, *, module_path: str | os.PathLike[str], token_label: str,
        key_id: str, user_pin: str | bytes,
        pkcs11_loader: Callable[[str], object] | None = None,
    ) -> None:
        path = Path(module_path).expanduser()
        if not path.is_absolute() or not path.is_file() or path.is_symlink():
            raise PKCS11SignerError("PKCS#11 module must be an absolute regular non-symlink file.")
        if type(token_label) is not str or not token_label or len(token_label) > 128:
            raise PKCS11SignerError("PKCS#11 token label is invalid.")
        if type(key_id) is not str or not _KEY_ID.fullmatch(key_id):
            raise PKCS11SignerError("PKCS#11 key ID is invalid.")
        if type(user_pin) is str:
            pin = user_pin.encode("utf-8")
        elif type(user_pin) is bytes:
            pin = user_pin
        else:
            raise TypeError("PKCS#11 user PIN must be text or bytes.")
        if not 4 <= len(pin) <= 128:
            raise PKCS11SignerError("PKCS#11 user PIN length is invalid.")
        self._module_path = str(path)
        self._token_label = token_label
        self._key_id = key_id.encode("ascii")
        self._pin = pin
        self._loader = pkcs11_loader

    @property
    def key_id(self) -> str:
        return self._key_id.decode("ascii")

    def _load(self):
        try:
            if self._loader is not None:
                loaded = self._loader(self._module_path)
                return loaded, loaded
            import pkcs11
            return pkcs11, pkcs11.lib(self._module_path)
        except Exception:
            raise PKCS11SignerError("PKCS#11 module could not be loaded.") from None

    def _token_session(self):
        try:
            pkcs11, library = self._load()
            token = library.get_token(token_label=self._token_label)
            return token.open(user_pin=self._pin), pkcs11
        except PKCS11SignerError:
            raise
        except Exception:
            raise PKCS11SignerError("PKCS#11 token session could not be opened.") from None

    def public_key_bytes(self) -> bytes:
        session_context, pkcs11 = self._token_session()
        try:
            with session_context as session:
                key = session.get_key(
                    object_class=pkcs11.ObjectClass.PUBLIC_KEY,
                    key_type=pkcs11.KeyType.EC_EDWARDS,
                    id=self._key_id,
                )
                params = bytes(key[pkcs11.Attribute.EC_PARAMS])
                if params != _ED25519_OID:
                    raise PKCS11SignerError("PKCS#11 public key is not Ed25519.")
                point = _der_octet_string(bytes(key[pkcs11.Attribute.EC_POINT]))
                if len(point) != 32:
                    raise PKCS11SignerError("PKCS#11 Ed25519 public key length is invalid.")
                return point
        except PKCS11SignerError:
            raise
        except Exception:
            raise PKCS11SignerError("PKCS#11 Ed25519 public key lookup failed.") from None

    def sign(self, message: bytes) -> bytes:
        if type(message) is not bytes or not 1 <= len(message) <= _MAX_MESSAGE_BYTES:
            raise PKCS11SignerError("Signing input must be 1 to 1048576 bytes.")
        session_context, pkcs11 = self._token_session()
        try:
            with session_context as session:
                key = session.get_key(
                    object_class=pkcs11.ObjectClass.PRIVATE_KEY,
                    key_type=pkcs11.KeyType.EC_EDWARDS,
                    id=self._key_id,
                )
                signature = bytes(key.sign(message, mechanism=pkcs11.Mechanism.EDDSA))
                if len(signature) != 64:
                    raise PKCS11SignerError("PKCS#11 returned an invalid Ed25519 signature length.")
                return signature
        except PKCS11SignerError:
            raise
        except Exception:
            raise PKCS11SignerError("PKCS#11 Ed25519 signing failed closed.") from None
