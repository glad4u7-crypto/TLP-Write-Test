from pathlib import Path

import pytest

from scripts.preflight_android_deployment import PreflightError, validate_settings


@pytest.fixture
def deployment_settings(tmp_path):
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    data = tmp_path / "private-data"
    data.mkdir()
    return checkout, {
        "auth": {
            "client_id": "test-client",
            "client_secret": "not-a-real-secret",
            "cookie_secret": "not-a-real-cookie-secret",
            "redirect_uri": "https://apaa.example.test/oauth2callback",
            "server_metadata_url": "https://identity.example.test/.well-known/openid-configuration",
        },
        "apaa": {
            "require_auth": True,
            "approval_signing_secret_hex": "ab" * 32,
            "security_db_path": str(data / "security.sqlite3"),
            "project_db_path": str(data / "projects.sqlite3"),
            "memory_db_path": str(data / "memory.sqlite3"),
        },
    }


def test_preflight_accepts_complete_private_deployment_configuration(deployment_settings):
    checkout, settings = deployment_settings
    results = validate_settings(settings, cwd=checkout)
    assert any("persistent storage" in item for item in results)


@pytest.mark.parametrize("bad_value", [False, "true", 1, None])
def test_preflight_requires_boolean_auth_true(deployment_settings, bad_value):
    checkout, settings = deployment_settings
    settings["apaa"]["require_auth"] = bad_value
    with pytest.raises(PreflightError, match="boolean true"):
        validate_settings(settings, cwd=checkout)


def test_preflight_rejects_missing_oidc_config(deployment_settings):
    checkout, settings = deployment_settings
    del settings["auth"]
    with pytest.raises(PreflightError, match="Missing \\[auth\\]"):
        validate_settings(settings, cwd=checkout)


@pytest.mark.parametrize("url", [
    "http://identity.example.test/config",
    "https://",
    "https://user:pass@identity.example.test/config",
    "https://identity.example.test/config#fragment",
    "https://identity example.test/config",
])
def test_preflight_rejects_unsafe_metadata_url(deployment_settings, url):
    checkout, settings = deployment_settings
    settings["auth"]["server_metadata_url"] = url
    with pytest.raises(PreflightError, match="HTTPS URL"):
        validate_settings(settings, cwd=checkout)


def test_preflight_rejects_short_or_malformed_signing_key(deployment_settings):
    checkout, settings = deployment_settings
    settings["apaa"]["approval_signing_secret_hex"] = "abcd"
    with pytest.raises(PreflightError, match="32 bytes"):
        validate_settings(settings, cwd=checkout)


def test_preflight_rejects_database_path_inside_checkout(deployment_settings):
    checkout, settings = deployment_settings
    settings["apaa"]["project_db_path"] = str(checkout / "projects.sqlite3")
    with pytest.raises(PreflightError, match="outside the application checkout"):
        validate_settings(settings, cwd=checkout)


def test_preflight_rejects_duplicate_database_paths(deployment_settings):
    checkout, settings = deployment_settings
    settings["apaa"]["memory_db_path"] = settings["apaa"]["project_db_path"]
    with pytest.raises(PreflightError, match="distinct paths"):
        validate_settings(settings, cwd=checkout)


def test_preflight_rejects_relative_database_paths(deployment_settings):
    checkout, settings = deployment_settings
    settings["apaa"]["security_db_path"] = "security.sqlite3"
    with pytest.raises(PreflightError, match="absolute path"):
        validate_settings(settings, cwd=checkout)


def test_preflight_rejects_missing_database_parent(deployment_settings):
    checkout, settings = deployment_settings
    settings["apaa"]["memory_db_path"] = str(checkout.parent / "missing" / "memory.sqlite3")
    with pytest.raises(PreflightError, match="must already exist"):
        validate_settings(settings, cwd=checkout)
