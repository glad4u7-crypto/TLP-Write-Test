from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from scripts import provision_apaa_pkcs11_signer as cli


class API:
    class Attribute:
        ID = "id"
        TOKEN = "token"
        VERIFY = "verify"
        EC_PARAMS = "ec_params"
        EC_POINT = "point"
        PRIVATE = "private"
        SENSITIVE = "sensitive"
        EXTRACTABLE = "extractable"
        SIGN = "sign"
        ALWAYS_SENSITIVE = "always_sensitive"
        NEVER_EXTRACTABLE = "never_extractable"

    class KeyType:
        EC_EDWARDS = "edwards"

    class Mechanism:
        EC_EDWARDS_KEY_PAIR_GEN = "edwards-keygen"
        EDDSA = "eddsa"

    class ObjectClass:
        PUBLIC_KEY = "public"
        PRIVATE_KEY = "private"

    class MechanismFlag:
        HW = 1

    class SlotFlag:
        HW_SLOT = 4

    def __init__(self):
        self.library = Library(self)

    def lib(self, _path):
        return self.library

    def get_token(self, *, token_label):
        return self.library.get_token(token_label=token_label)


class Library:
    def __init__(self, api):
        self.api = api
        self.session = Session(api)

    def get_token(self, *, token_label):
        assert token_label == "TEST-TOKEN"
        return self.session


class Session:
    def __init__(self, api):
        self.api = api
        self.key = None
        self.created = 0
        self.hardware = True
        self.slot = self

    @property
    def flags(self):
        return self.api.SlotFlag.HW_SLOT

    def get_mechanism_info(self, _mechanism):
        return type("MechanismInfo", (), {"flags": self.api.MechanismFlag.HW if self.hardware else 0})()

    def open(self, *, rw=False, user_pin):
        if rw:
            assert user_pin == b"hidden-pin"
        return self

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def get_objects(self, attrs):
        if self.key is not None and attrs.get(self.api.Attribute.ID) == b"test-key-01":
            return [self.key]
        return []

    def get_key(self, *, object_class, key_type, id):
        assert key_type == self.api.KeyType.EC_EDWARDS
        assert id == b"test-key-01"
        if object_class == self.api.ObjectClass.PUBLIC_KEY:
            return PublicKey(self.key.key, self.api)
        return self.key

    def generate_keypair(self, key_type, **kwargs):
        assert key_type == self.api.KeyType.EC_EDWARDS
        assert kwargs["mechanism"] == self.api.Mechanism.EC_EDWARDS_KEY_PAIR_GEN
        assert kwargs["private_template"][self.api.Attribute.SENSITIVE] is True
        assert kwargs["private_template"][self.api.Attribute.EXTRACTABLE] is False
        self.key = EdKey(Ed25519PrivateKey.generate(), self.api)
        self.created += 1
        return PublicKey(self.key.key, self.api), self.key


class EdKey:
    def __init__(self, key, api):
        self.key = key
        self.api = api

    def __getitem__(self, attr):
        values = {
            self.api.Attribute.SENSITIVE: True,
            self.api.Attribute.EXTRACTABLE: False,
            self.api.Attribute.ALWAYS_SENSITIVE: True,
            self.api.Attribute.NEVER_EXTRACTABLE: True,
            self.api.Attribute.SIGN: True,
        }
        if attr in values:
            return values[attr]
        if attr == self.api.Attribute.EC_PARAMS:
            return bytes.fromhex("06032b6570")
        raise KeyError(attr)

    def sign(self, message, *, mechanism):
        assert mechanism == self.api.Mechanism.EDDSA
        return self.key.sign(message)


class PublicKey:
    def __init__(self, private, api):
        self.private, self.api = private, api

    def __getitem__(self, attr):
        if attr == self.api.Attribute.EC_PARAMS:
            return bytes.fromhex("06032b6570")
        if attr == self.api.Attribute.EC_POINT:
            raw = self.private.public_key().public_bytes(
                serialization.Encoding.Raw, serialization.PublicFormat.Raw,
            )
            return b"\x04\x22\x04\x20" + raw
        raise KeyError(attr)


def test_provisioner_requires_explicit_confirmation_and_hidden_pin(tmp_path, capsys):
    module = tmp_path / "pkcs11.so"
    module.write_bytes(b"fake")
    api = API()
    assert cli.main(
        ["--module", str(module), "--token-label", "TEST-TOKEN", "--key-id", "test-key-01"],
        pkcs11_api_loader=lambda: api, pin_reader=lambda _prompt: "hidden-pin",
    ) == 2
    assert api.library.session.created == 0
    assert "Refusing" in capsys.readouterr().err


def test_provisioner_creates_nonextractable_key_once_and_self_tests(tmp_path):
    module = tmp_path / "pkcs11.so"
    module.write_bytes(b"fake")
    api = API()
    result = cli.provision_and_self_test(
        module_path=str(module), token_label="TEST-TOKEN", key_id="test-key-01",
        label="APAA Test", pin="hidden-pin", pkcs11_api=api,
    )
    assert result["status"] == "TOKEN_KEY_CREATED_AND_SELF_TEST_PASS"
    assert result["private_key_export"] == "NOT_REQUESTED"
    assert api.library.session.created == 1


def test_provisioner_refuses_existing_key_id(tmp_path):
    import pytest
    from scripts.provision_apaa_pkcs11_signer import PKCS11ProvisionError
    module = tmp_path / "pkcs11.so"
    module.write_bytes(b"fake")
    api = API()
    session = api.library.session
    session.key = EdKey(Ed25519PrivateKey.generate(), api)
    with pytest.raises(PKCS11ProvisionError, match="already exists"):
        cli.provision_and_self_test(
            module_path=str(module), token_label="TEST-TOKEN", key_id="test-key-01",
            label="APAA Test", pin="hidden-pin", pkcs11_api=api,
        )
    assert session.created == 0


def test_provisioner_refuses_token_without_hardware_eddsa_flag(tmp_path):
    import pytest
    from scripts.provision_apaa_pkcs11_signer import PKCS11ProvisionError
    module = tmp_path / "pkcs11.so"
    module.write_bytes(b"fake")
    api = API()
    api.library.session.hardware = False
    with pytest.raises(PKCS11ProvisionError, match="hardware-backed EdDSA"):
        cli.provision_and_self_test(
            module_path=str(module), token_label="TEST-TOKEN", key_id="test-key-02",
            label="APAA Test", pin="hidden-pin", pkcs11_api=api,
        )
    assert api.library.session.created == 0
