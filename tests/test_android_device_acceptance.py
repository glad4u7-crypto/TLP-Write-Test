from pathlib import Path

from scripts.android_device_acceptance import run_diagnostics


def _write_private_secrets(path: Path) -> None:
    path.write_text(
        "[apaa]\nrequire_auth = true\napproval_signing_secret_hex = "
        "\"abababababababababababababababababababababababababababababababab\"\n"
        "[auth]\nredirect_uri = \"http://localhost:8501/oauth2callback\"\n"
        "cookie_secret = \"cccccccccccccccccccccccccccccccccccccccc\"\n"
        "client_id = \"test-client\"\nclient_secret = \"test-secret\"\n"
        "server_metadata_url = \"https://issuer.example/.well-known/openid-configuration\"\n",
        encoding="utf-8",
    )
    path.chmod(0o600)
    path.parent.chmod(0o700)


def test_android_device_diagnostics_report_termux_and_private_auth_config(tmp_path):
    secrets = tmp_path / ".streamlit" / "secrets.toml"
    secrets.parent.mkdir(mode=0o700)
    _write_private_secrets(secrets)
    env = {
        "ANDROID_ROOT": "/system",
        "ANDROID_DATA": "/data",
        "PREFIX": "/data/data/com.termux/files/usr",
        "HOME": "/data/data/com.termux/files/home",
    }
    results = run_diagnostics(environ=env, secrets_path=secrets)
    by_id = {item["id"]: item for item in results}
    assert set(by_id) == {"D01", "D02", "D03", "D04", "D05", "D06", "D07", "D08"}
    assert by_id["D01"]["status"] == "PASS"
    assert by_id["D02"]["status"] == "PASS"
    assert by_id["D05"]["status"] == "PASS"
    assert by_id["D07"]["status"] == "PASS"
    assert by_id["D08"]["status"] == "PASS"


def test_android_device_diagnostics_do_not_accept_missing_owner_auth(tmp_path):
    results = run_diagnostics(
        environ={
            "ANDROID_ROOT": "/system",
            "PREFIX": "/data/data/com.termux/files/usr",
            "HOME": "/data/data/com.termux/files/home",
        },
        secrets_path=tmp_path / ".streamlit" / "missing.toml",
    )
    by_id = {item["id"]: item for item in results}
    assert by_id["D05"]["status"] == "FAIL"
    assert by_id["D07"]["status"] == "FAIL"
    assert by_id["D08"]["status"] == "FAIL"
    assert "secret values not displayed" in by_id["D05"]["detail"]


def test_android_device_diagnostics_reject_group_or_world_readable_secrets(tmp_path):
    secrets = tmp_path / ".streamlit" / "secrets.toml"
    secrets.parent.mkdir(mode=0o700)
    _write_private_secrets(secrets)
    secrets.chmod(0o644)
    results = run_diagnostics(
        environ={"ANDROID_ROOT": "/system", "PREFIX": "/data/data/com.termux/files/usr"},
        secrets_path=secrets,
    )
    by_id = {item["id"]: item for item in results}
    assert by_id["D08"]["status"] == "FAIL"
    assert by_id["D05"]["status"] == "FAIL"


def test_android_device_diagnostics_reject_symlinked_secrets_file(tmp_path):
    secrets = tmp_path / ".streamlit" / "secrets.toml"
    secrets.parent.mkdir(mode=0o700)
    target = tmp_path / "outside.toml"
    _write_private_secrets(target)
    secrets.symlink_to(target)
    results = run_diagnostics(
        environ={"ANDROID_ROOT": "/system", "PREFIX": "/data/data/com.termux/files/usr"},
        secrets_path=secrets,
    )
    by_id = {item["id"]: item for item in results}
    assert by_id["D08"]["status"] == "FAIL"
    assert by_id["D05"]["status"] == "FAIL"


def test_android_device_diagnostics_reject_symlinked_streamlit_directory(tmp_path):
    target_dir = tmp_path / "real-streamlit"
    target_dir.mkdir(mode=0o700)
    secrets_target = target_dir / "secrets.toml"
    _write_private_secrets(secrets_target)
    link_dir = tmp_path / ".streamlit"
    link_dir.symlink_to(target_dir, target_is_directory=True)
    results = run_diagnostics(
        environ={"ANDROID_ROOT": "/system", "PREFIX": "/data/data/com.termux/files/usr"},
        secrets_path=link_dir / "secrets.toml",
    )
    by_id = {item["id"]: item for item in results}
    assert by_id["D08"]["status"] == "FAIL"
    assert by_id["D05"]["status"] == "FAIL"
