from pathlib import Path

import pytest

from scripts.android_owner_ui import owner_ui_command, validate_android_owner_config


TERMUX_ENV = {
    "ANDROID_ROOT": "/system",
    "ANDROID_DATA": "/data",
    "PREFIX": "/data/data/com.termux/files/usr",
    "HOME": "/data/data/com.termux/files/home",
}


def valid_secrets(*, redirect="http://localhost:8501/oauth2callback", metadata="https://issuer.example/.well-known/openid-configuration"):
    return (
        "[apaa]\nrequire_auth = true\n"
        "[auth]\n"
        f'redirect_uri = "{redirect}"\n'
        'cookie_secret = "cccccccccccccccccccccccccccccccc"\n'
        'client_id = "client"\n'
        'client_secret = "secret"\n'
        f'server_metadata_url = "{metadata}"\n'
    )


def test_owner_launcher_requires_android_termux(tmp_path):
    with pytest.raises(RuntimeError, match="Android/Termux"):
        validate_android_owner_config(environ={"HOME": "/home/test"}, secrets_path=tmp_path / "secrets.toml")


def test_owner_launcher_refuses_missing_auth_config(tmp_path):
    with pytest.raises(RuntimeError, match="secrets.toml"):
        validate_android_owner_config(environ=TERMUX_ENV, secrets_path=tmp_path / "missing.toml")


def test_owner_launcher_refuses_unauthenticated_prototype(tmp_path):
    secrets = tmp_path / "secrets.toml"
    secrets.write_text('[apaa]\nrequire_auth = false\n[auth]\n', encoding="utf-8")
    with pytest.raises(RuntimeError, match="require_auth"):
        validate_android_owner_config(environ=TERMUX_ENV, secrets_path=secrets)


def test_owner_launcher_requires_streamlit_oidc_config(tmp_path):
    secrets = tmp_path / "secrets.toml"
    secrets.write_text('[apaa]\nrequire_auth = true\n', encoding="utf-8")
    with pytest.raises(RuntimeError, match="OIDC"):
        validate_android_owner_config(environ=TERMUX_ENV, secrets_path=secrets)


def test_owner_launcher_accepts_valid_auth_required_config(tmp_path):
    secrets = tmp_path / "secrets.toml"
    secrets.write_text(valid_secrets(), encoding="utf-8")
    validate_android_owner_config(environ=TERMUX_ENV, secrets_path=secrets)


def test_owner_ui_command_binds_loopback_only():
    command = owner_ui_command(python_executable="python", app_path=Path("/app/app.py"))
    assert "--server.address=127.0.0.1" in command
    assert "--server.enableCORS=true" in command
    assert "--server.enableXsrfProtection=true" in command
    assert not any("0.0.0.0" in part or "--server.address=::" in part for part in command)


@pytest.mark.parametrize("port", [0, 80, 65536])
def test_owner_ui_rejects_unsafe_port(port):
    with pytest.raises(ValueError):
        owner_ui_command(python_executable="python", app_path=Path("/app/app.py"), port=port)


def test_owner_launcher_rejects_non_loopback_oidc_redirect(tmp_path):
    secrets = tmp_path / "secrets.toml"
    secrets.write_text(valid_secrets(redirect="http://192.168.1.5:8501/oauth2callback"), encoding="utf-8")
    with pytest.raises(RuntimeError, match="loopback"):
        validate_android_owner_config(environ=TERMUX_ENV, secrets_path=secrets)


def test_owner_launcher_rejects_http_oidc_metadata(tmp_path):
    secrets = tmp_path / "secrets.toml"
    secrets.write_text(valid_secrets(metadata="http://issuer.example/.well-known/openid-configuration"), encoding="utf-8")
    with pytest.raises(RuntimeError, match="HTTPS"):
        validate_android_owner_config(environ=TERMUX_ENV, secrets_path=secrets)
