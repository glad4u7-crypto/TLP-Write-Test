from pathlib import Path
import os

import pytest

from scripts.android_termux_setup import (
    REDIRECT_URI,
    build_secrets_text,
    write_private_secrets,
)


def test_build_android_owner_secrets_generates_strong_private_keys():
    text = build_secrets_text(
        client_id="owner-client",
        client_secret="private-client-secret",
        metadata_url="https://issuer.example/.well-known/openid-configuration",
    )
    assert "require_auth = true" in text
    assert f'redirect_uri = "{REDIRECT_URI}"' in text
    assert "approval_signing_secret_hex" in text
    assert "client-secret" not in text


@pytest.mark.parametrize("metadata", [
    "http://issuer.example/.well-known/openid-configuration",
    "https://user:pass@issuer.example/metadata",
    "https://issuer.example/metadata#fragment",
])
def test_build_android_owner_secrets_rejects_unsafe_oidc_metadata(metadata):
    with pytest.raises(ValueError):
        build_secrets_text(
            client_id="client", client_secret="secret", metadata_url=metadata
        )


def test_write_private_secrets_sets_private_permissions_and_refuses_overwrite(tmp_path):
    content = build_secrets_text(
        client_id="client",
        client_secret="secret-value",
        metadata_url="https://issuer.example/.well-known/openid-configuration",
    )
    path = write_private_secrets(tmp_path, content)
    assert path.is_file()
    assert path.parent.stat().st_mode & 0o777 == 0o700
    assert path.stat().st_mode & 0o777 == 0o600
    with pytest.raises(FileExistsError):
        write_private_secrets(tmp_path, content)


def test_write_private_secrets_rejects_streamlit_symlink(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (tmp_path / ".streamlit").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        write_private_secrets(tmp_path, "not used")
