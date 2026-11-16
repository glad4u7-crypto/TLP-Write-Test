import os

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from core.pkcs11_ed25519_signer import PKCS11Ed25519InspectorSigner, PKCS11SignerError


class FakePKCS11:
    class ObjectClass:
        PUBLIC_KEY = "public"
        PRIVATE_KEY = "private"

    class KeyType:
        EC_EDWARDS = "edwards"

    class Attribute:
        EC_PARAMS = "params"
        EC_POINT = "point"
        SENSITIVE = "sensitive"
        EXTRACTABLE = "extractable"
        ALWAYS_SENSITIVE = "always_sensitive"
        NEVER_EXTRACTABLE = "never_extractable"
        SIGN = "sign"

    class Mechanism:
        EDDSA = "eddsa"

    def __init__(self, key):
        self.key = key

    def lib(self, _path):
        return self

    def get_token(self, *, token_label):
        assert token_label == "APAA-TEST"
        return self

    def open(self, *, user_pin):
        assert user_pin == b"test-pin-1234"
        return self

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def get_key(self, *, object_class, key_type, id):
        assert key_type == self.KeyType.EC_EDWARDS
        assert id == b"inspector-01"
        return FakeKey(self.key, object_class == self.ObjectClass.PUBLIC_KEY)


class FakeKey:
    def __init__(self, key, public):
        self.key, self.public = key, public

    def __getitem__(self, attr):
        if attr == FakePKCS11.Attribute.EC_PARAMS:
            return bytes.fromhex("06032b6570")
        if attr == FakePKCS11.Attribute.EC_POINT:
            raw = self.key.public_key().public_bytes(
                serialization.Encoding.Raw, serialization.PublicFormat.Raw,
            )
            return b"\x04\x22\x04\x20" + raw
        if attr == FakePKCS11.Attribute.SENSITIVE:
            return True
        if attr == FakePKCS11.Attribute.EXTRACTABLE:
            return False
        if attr == FakePKCS11.Attribute.ALWAYS_SENSITIVE:
            return True
        if attr == FakePKCS11.Attribute.NEVER_EXTRACTABLE:
            return True
        if attr == FakePKCS11.Attribute.SIGN:
            return True
        raise KeyError(attr)

    def sign(self, message, *, mechanism):
        assert mechanism == FakePKCS11.Mechanism.EDDSA
        return self.key.sign(message)


@pytest.fixture
def signer_fixture(tmp_path):
    module = tmp_path / "pkcs11.so"
    module.write_bytes(b"test module placeholder")
    key = Ed25519PrivateKey.generate()
    fake = FakePKCS11(key)
    signer = PKCS11Ed25519InspectorSigner(
        module_path=module, token_label="APAA-TEST", key_id="inspector-01",
        user_pin="test-pin-1234", pkcs11_loader=lambda _path: fake,
    )
    return signer, key


def test_pkcs11_provider_exposes_public_key_and_signs_without_export(signer_fixture):
    signer, key = signer_fixture
    assert signer.public_key_bytes() == key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw,
    )
    message = b"host evidence"
    signature = signer.sign(message)
    assert len(signature) == 64
    Ed25519PublicKey.from_public_bytes(signer.public_key_bytes()).verify(signature, message)
    assert not hasattr(signer, "private_key_bytes")


def test_pkcs11_provider_rejects_bad_input_and_unsafe_module_path(tmp_path, signer_fixture):
    signer, _ = signer_fixture
    for message in (b"", "not-bytes", b"x" * 1_048_577):
        with pytest.raises(PKCS11SignerError):
            signer.sign(message)
    with pytest.raises(PKCS11SignerError):
        PKCS11Ed25519InspectorSigner(
            module_path=tmp_path / "missing.so", token_label="APAA-TEST",
            key_id="inspector-01", user_pin="test-pin-1234",
        )


def test_pkcs11_provider_fails_closed_for_missing_token_key(tmp_path):
    module = tmp_path / "pkcs11.so"
    module.write_bytes(b"test")
    class BrokenLibrary:
        def get_token(self, **_kwargs):
            raise RuntimeError("no token")
    signer = PKCS11Ed25519InspectorSigner(
        module_path=module, token_label="APAA-TEST", key_id="inspector-01",
        user_pin="test-pin-1234", pkcs11_loader=lambda _path: BrokenLibrary(),
    )
    with pytest.raises(PKCS11SignerError, match="session"):
        signer.sign(b"message")

def test_pkcs11_provider_rejects_extractable_private_key(tmp_path):
    module = tmp_path / "pkcs11.so"
    module.write_bytes(b"test")
    class ExtractableKey(FakeKey):
        def __getitem__(self, attr):
            if attr == FakePKCS11.Attribute.EXTRACTABLE:
                return True
            return super().__getitem__(attr)
    class ExtractableLibrary(FakePKCS11):
        def get_key(self, *, object_class, key_type, id):
            if object_class == self.ObjectClass.PRIVATE_KEY:
                return ExtractableKey(self.key, False)
            return super().get_key(object_class=object_class, key_type=key_type, id=id)
    fake = ExtractableLibrary(Ed25519PrivateKey.generate())
    signer = PKCS11Ed25519InspectorSigner(
        module_path=module, token_label="APAA-TEST", key_id="inspector-01",
        user_pin="test-pin-1234", pkcs11_loader=lambda _path: fake,
    )
    with pytest.raises(PKCS11SignerError, match="non-extractable"):
        signer.sign(b"evidence")

