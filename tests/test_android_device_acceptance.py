from pathlib import Path

from scripts.android_device_acceptance import run_diagnostics


def test_android_device_diagnostics_report_termux_and_private_auth_config(tmp_path):
    secrets = tmp_path / "secrets.toml"
    secrets.write_text("[apaa]\nrequire_auth = true\napproval_signing_secret_hex = \"abababababababababababababababababababababababababababababababab\"\n[auth]\nredirect_uri = \"http://localhost:8501/oauth2callback\"\ncookie_secret = \"cccccccccccccccccccccccccccccccccccccccc\"\nclient_id = \"test-client\"\nclient_secret = \"test-secret\"\nserver_metadata_url = \"https://issuer.example/.well-known/openid-configuration\"\n", encoding="utf-8")
    env = {
        "ANDROID_ROOT": "/system",
        "ANDROID_DATA": "/data",
        "PREFIX": "/data/data/com.termux/files/usr",
        "HOME": "/data/data/com.termux/files/home",
    }
    results = run_diagnostics(environ=env, secrets_path=secrets)
    assert [item["id"] for item in results] == ["D01", "D02", "D03", "D04", "D05", "D07", "D06"]
    assert results[0]["status"] == "PASS"
    assert results[1]["status"] == "PASS"
    assert results[4]["status"] == "PASS"
    assert results[5]["status"] == "PASS"
    assert results[6]["status"] == "PASS"


def test_android_device_diagnostics_do_not_accept_missing_owner_auth(tmp_path):
    results = run_diagnostics(
        environ={
            "ANDROID_ROOT": "/system",
            "PREFIX": "/data/data/com.termux/files/usr",
            "HOME": "/data/data/com.termux/files/home",
        },
        secrets_path=tmp_path / "missing.toml",
    )
    assert results[4]["status"] == "FAIL"
    assert results[5]["status"] == "FAIL"
    assert "secret values not displayed" in results[4]["detail"]
