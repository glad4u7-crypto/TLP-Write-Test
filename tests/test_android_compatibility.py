import pytest

from core.android_compatibility import (
    assess_android_compatibility,
    validate_local_owner_bind,
)


def test_termux_is_supported_for_local_owner_ui_but_not_browser_worker():
    result = assess_android_compatibility(
        platform="linux",
        environ={
            "ANDROID_ROOT": "/system",
            "ANDROID_DATA": "/data",
            "PREFIX": "/data/data/com.termux/files/usr",
            "HOME": "/data/data/com.termux/files/home",
        },
    )
    assert result.android is True
    assert result.termux is True
    assert result.owner_ui_supported is True
    assert result.local_app_host == "127.0.0.1"
    assert result.owner_ui_origin.startswith("http://127.0.0.1:")
    assert result.browser_worker_supported is False
    assert result.physical_device_verified is False


def test_android_without_termux_marker_is_detected_but_owner_ui_is_not_supported():
    result = assess_android_compatibility(
        platform="linux", environ={"ANDROID_DATA": "/data"}
    )
    assert result.android is True
    assert result.termux is False
    assert result.owner_ui_supported is False
    assert result.owner_ui_origin == ""
    assert result.browser_worker_supported is False


def test_non_android_does_not_claim_browser_worker_qualification():
    result = assess_android_compatibility(platform="linux", environ={"HOME": "/tmp"})
    assert result.android is False
    assert result.browser_worker_supported is False
    assert result.physical_device_verified is False


@pytest.mark.parametrize("host", ["127.0.0.1", "::1", "localhost"])
def test_owner_ui_accepts_loopback_only(host):
    assert validate_local_owner_bind(host) is True


@pytest.mark.parametrize("host", ["0.0.0.0", "::", "192.168.1.10", "example.com", ""])
def test_owner_ui_rejects_non_loopback_bind(host):
    assert validate_local_owner_bind(host) is False
